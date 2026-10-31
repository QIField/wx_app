/** 聊天共享状态（Pinia）：会话列表、当前会话、消息、WebSocket 事件分发。 */
import { defineStore } from 'pinia'
import { connectWs, fetchConversations, fetchMessages, markConversationRead, openConversation, sendTextMessage } from '../api'

/** 本地时间戳（与后端 last_msg_at 同格式），发消息后用于即时重排。 */
function nowStamp() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} `
    + `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

export const useChatStore = defineStore('chat', {
  state: () => ({
    conversations: [],   // 左栏列表
    currentId: null,     // 当前选中的会话 id
    currentMessages: [], // 当前会话的聊天记录（时间正序）
    loadingMessages: false,
    hasMore: false,      // 还有更早的记录可翻
    loadingMore: false,
  }),

  getters: {
    currentConv: (s) => s.conversations.find((c) => c.id === s.currentId) || null,
  },

  actions: {
    async loadConversations() {
      // 未读一律以后端为准：不因"正在打开"而清除，只有用户点击会话窗口内容才算已读
      this.conversations = await fetchConversations()
    },

    /** 从通讯录发起会话：已有会话直接进，没有就建一个再进。 */
    async openWithContact(wxid, chatType) {
      const local = this.conversations.find(
        (c) => c.wxid === wxid && c.chat_type === chatType)
      let convId = local?.id
      if (!convId) {
        const conv = await openConversation(wxid, chatType)
        convId = conv.id
        await this.loadConversations()
      }
      await this.selectConversation(convId)
    },

    async selectConversation(id) {
      this.currentId = id
      // 点列表选择会话也标记已读：红点立即消失并落库（点击会话窗口内容同样清零）
      this.markCurrentRead()

      // 先清残留再拉数据：面板立刻切骨架屏，避免旧会话消息撑到新数据到达才被替换
      this.currentMessages = []
      this.hasMore = false

      this.loadingMessages = true
      try {
        const data = await fetchMessages(id)
        this.currentMessages = data.messages
        this.hasMore = !!data.next_before_id
      } finally {
        this.loadingMessages = false
      }
    },

    /** 用户点击了会话窗口范围内的内容：当前会话才算已读（本地清零并落库）。 */
    markCurrentRead() {
      const conv = this.currentConv
      if (!conv || !conv.unread_count) return
      conv.unread_count = 0
      markConversationRead(conv.id).catch(() => {})
    },

    /** 往前翻更早的记录（滚动到顶时调）。 */
    async loadOlderMessages() {
      if (!this.currentId || !this.hasMore || this.loadingMore) return
      this.loadingMore = true
      try {
        const oldest = this.currentMessages[0]?.id
        const data = await fetchMessages(this.currentId, oldest)
        this.currentMessages = [...data.messages, ...this.currentMessages]
        this.hasMore = !!data.next_before_id
      } finally {
        this.loadingMore = false
      }
    },

    /** 发文本消息：先本地加"发送中"气泡，等 WS 推最终状态。 */
    async sendText(content) {
      if (!this.currentId || !content.trim()) return
      const convId = this.currentId
      const data = await sendTextMessage(convId, content)

      // 若期间切了会话就不追加
      if (this.currentId === convId) {
        this.currentMessages.push({
          id: data.message_id,
          msg_type: 1,
          direction: 2,
          sender_name: '客服',
          content,
          payload: {},
          status: data.status,
          create_time: new Date().toLocaleString('zh-CN', { hour12: false }),
        })
      }
      const conv = this.conversations.find((c) => c.id === convId)
      if (conv) {
        conv.last_msg = content
        conv.last_msg_at = nowStamp() // 自己发的消息也按最后消息时间置顶
        this.sortConversations()
      }
    },

    /** 按后端同一规则重排：置顶优先，其余按最后消息时间倒序（无时间排最后）。 */
    sortConversations() {
      this.conversations.sort((a, b) => {
        const pa = a.pinned || 0
        const pb = b.pinned || 0
        if (pa !== pb) return pb - pa
        const ta = a.last_msg_at || ''
        const tb = b.last_msg_at || ''
        return ta < tb ? 1 : ta > tb ? -1 : 0
      })
    },

    /** 连接 WebSocket 并分发推送。 */
    connect() {
      connectWs((event, data) => {
        if (event === 'new_message') this.onNewMessage(data)
        else if (event === 'send_result') this.onSendResult(data)
        else if (event === 'conv_updated') this.onConvUpdated(data)
        else if (event === 'message_revoked') this.onMessageRevoked(data)
      })
    },

    /** 资料解析完成后推送：重拉列表；当前会话重拉消息（昵称/头像补齐即刷新）。 */
    async onConvUpdated() {
      await this.loadConversations()
      if (this.currentId) {
        const data = await fetchMessages(this.currentId)
        this.currentMessages = data.messages
        this.hasMore = !!data.next_before_id
      }
    },

    onNewMessage(d) {
      const conv = this.conversations.find((c) => c.id === d.conversation_id)
      if (conv) {
        // 系统灰条直接用原文；残留的微信 XML（未识别类型）不进会话摘要
        const isXml = typeof d.content === 'string' && d.content.trimStart().startsWith('<')
        conv.last_msg = d.payload?.system || isXml ? '[系统消息]' : d.content
        conv.last_msg_at = d.create_time
        // 打开着的会话同样累计未读：只有用户点击会话窗口内容才清零
        if (d.direction === 1) conv.unread_count = (conv.unread_count || 0) + 1
        this.sortConversations() // 新消息必须置顶（置顶会话除外，按时间倒序）
      } else {
        this.loadConversations() // 新联系人的会话不在列表里，重拉
      }

      if (d.conversation_id === this.currentId) {
        this.currentMessages.push({ ...d, direction: d.direction, status: 1 })
      }
    },

    onSendResult(d) {
      const msg = this.currentMessages.find((m) => m.id === d.message_id)
      if (msg) msg.status = d.status
    },

    /** 自己发的消息撤回成功：打标记，气泡变"已撤回"。 */
    onMessageRevoked(d) {
      const msg = this.currentMessages.find((m) => m.id === d.message_id)
      if (msg) msg.payload = { ...(msg.payload || {}), revoked: true }
    },
  },
})
