/** 聊天共享状态（Pinia）：会话列表、当前会话、消息、WebSocket 事件分发。 */
import { defineStore } from 'pinia'
import { connectWs, fetchConversations, fetchMessages, openConversation, sendTextMessage } from '../api'

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
      const conv = this.conversations.find((c) => c.id === id)
      if (conv) conv.unread_count = 0 // 打开即清未读

      this.loadingMessages = true
      try {
        const data = await fetchMessages(id)
        this.currentMessages = data.messages
        this.hasMore = !!data.next_before_id
      } finally {
        this.loadingMessages = false
      }
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
      if (conv) conv.last_msg = content
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
        if (d.conversation_id !== this.currentId) conv.unread_count += 1
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
