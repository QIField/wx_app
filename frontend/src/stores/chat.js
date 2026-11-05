/** 聊天共享状态（Pinia）：多设备绑定、会话列表、当前会话、消息、WebSocket 事件分发。 */
import { defineStore } from 'pinia'
import { nextTick } from 'vue'
import {
  checkDeviceOnline, connectWs, fetchConversations, fetchDevices, fetchMessages,
  markConversationRead, openConversation, sendTextMessage, updateConversation,
} from '../api'
import { prewarmThumbs } from '../utils/media'
import { convCacheGet, convCachePut } from '../utils/convCache'

/** 本地时间戳（与后端 last_msg_at 同格式），发消息后用于即时重排。 */
function nowStamp() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} `
    + `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

/** 会话摘要兜底：WS 推送优先用后端算好的 d.summary；缺失时（旧后端）
 * 未识别的微信 XML 显示 [系统消息]，系统灰条自带可读文案直接用。 */
function summaryOf(d) {
  if (d.summary) return d.summary
  const isXml = typeof d.content === 'string' && d.content.trimStart().startsWith('<')
  if (isXml) return '[系统消息]'
  if (d.payload?.system) return d.content || '[系统消息]'
  return d.content || ''
}

/** 设备卡片在线状态轮询定时器（模块级：Pinia store 单例共享）。 */
let devPollTimer = null

/** 消息列表请求序号（模块级）：切会话/切账号时递增，迟到的旧响应凭序号丢弃。
 *  修复快速切换会话时旧会话消息串进新会话窗口的竞态（标题与内容对不上）。 */
let msgListSeq = 0

export const useChatStore = defineStore('chat', {
  state: () => ({
    conversations: [],   // 当前设备下的左栏列表
    currentId: null,     // 当前选中的会话 id
    currentMessages: [], // 当前会话的聊天记录（时间正序）
    loadingMessages: false,
    hasMore: false,      // 还有更早的记录可翻
    loadingMore: false,
    devices: [],         // 绑定的聊天账号卡片 [{openid, remark, display_name, online, unread}]
    activeOpenid: '',    // 当前查看的聊天账号（缺省=第一个绑定）
    operatorName: '',    // 当前登录人姓名：本地乐观气泡直接显示操作人
  }),

  getters: {
    currentConv: (s) => s.conversations.find((c) => c.id === s.currentId) || null,

    /** 找回我的某台绑定设备卡片（找不到说明消息属于别人的设备）。 */
    myDevice: (s) => (openid) => s.devices.find((d) => d.openid === openid) || null,

    activeDevice() {
      return this.myDevice(this.activeOpenid)
    },

    /** 统一未读模块：当前账号按会话列表实时求和，其他账号用设备快照计数。
     *  侧栏「会话」红点与顶栏账号卡片红点必须都从这里取数，保证两处始终同步。 */
    unreadOf() {
      return (openid) => {
        if (openid === this.activeOpenid) {
          return this.conversations.reduce((n, c) => n + (c.unread_count || 0), 0)
        }
        return this.myDevice(openid)?.unread || 0
      }
    },

    /** 当前账号总未读（侧栏「会话」按钮红点）。 */
    totalUnread() {
      return this.unreadOf(this.activeOpenid)
    },
  },

  actions: {
    /** 绑定设备卡片：首次载入默认选第一个；之后重拉即同步未读/在线状态。 */
    async loadDevices(selectFirst = false) {
      this.devices = await fetchDevices()
      if ((selectFirst || !this.activeOpenid) && this.devices.length) {
        this.activeOpenid = this.devices[0].openid
      }
    },

    /** 设备卡片轮询：后端定时任务回写 online（默认 10 分钟一轮），前端定时重拉展示最新结果。 */
    startDevicePolling(intervalMs = 60000) {
      if (devPollTimer) return
      devPollTimer = setInterval(() => { this.loadDevices() }, intervalMs)
    },

    stopDevicePolling() {
      if (devPollTimer) { clearInterval(devPollTimer); devPollTimer = null }
    },

    /** 点击账号卡片：先即时查一次在线状态刷新圆点；非当前卡片则切换会话视图。 */
    clickDevice(openid) {
      this.refreshDeviceOnline(openid) // 不等待：检测结果回来就地更新卡片圆点
      if (openid === this.activeOpenid) return
      return this.switchDevice(openid)
    },

    /** 即时在线检测：只更新对应卡片的圆点，失败保持原状。 */
    async refreshDeviceOnline(openid) {
      try {
        const data = await checkDeviceOnline(openid)
        const dev = this.myDevice(openid)
        if (dev) dev.online = data.online
      } catch { /* 检测失败不改状态，等定时检测纠正 */ }
    },

    /** 切换聊天账号：清当前会话并重拉列表（通讯录由页面监听 activeOpenid 重拉）。 */
    async switchDevice(openid) {
      if (openid === this.activeOpenid) return
      this.activeOpenid = openid
      this.currentId = null
      this.currentMessages = []
      this.hasMore = false
      await Promise.all([this.loadDevices(), this.loadConversations()])
    },

    async loadConversations() {
      // 未读一律以后端为准：不因"正在打开"而清除，只有用户点击会话窗口内容才算已读
      this.conversations = await fetchConversations(this.activeOpenid)
    },

    /** 从通讯录发起会话：按 contact_id 建/取（contact 行自带 conversation_id 时本地直进；不传 wxid——脱敏契约）。 */
    async openWithContact(contactId, chatType, convId) {
      let id = convId || null
      if (!id) {
        const conv = await openConversation(contactId, chatType, this.activeOpenid)
        id = conv.id
        await this.loadConversations()
      }
      await this.selectConversation(id)
    },

    /** 拉取会话消息并整体替换视图（整表拉取唯一入口）。
     *  每次调用递增 msgListSeq：响应回来若已切走（别的会话/账号）或已有
     *  更新一轮请求，直接丢弃——根治快速切换会话时旧响应串窗的竞态。 */
    async loadMessages(id) {
      const seq = ++msgListSeq
      const tApi = performance.now()
      try {
        const data = await fetchMessages(id)
        const apiMs = performance.now() - tApi
        if (seq !== msgListSeq || this.currentId !== id) return
        this.currentMessages = data.messages
        this.hasMore = !!data.next_before_id
        convCachePut(this.activeOpenid, id, this.currentMessages, this.hasMore) // A方案：刷新快照
        prewarmThumbs(data.messages) // B方案：后台预取缩略图（fire-and-forget）
        // [perf] 打开会话全链路计时：接口耗时 + 渲染收尾（点开瞬间记录 _perfT0 才输出）
        if (this._perfT0 != null) {
          const total = performance.now() - this._perfT0
          this._perfT0 = null
          await nextTick()
          console.info(`[perf] 打开会话#${id}: 接口=${apiMs.toFixed(0)}ms 合计=${total.toFixed(0)}ms 消息数=${data.messages.length}`)
        }
      } finally {
        // 仅最新一轮负责骨架屏收尾：被作废的旧请求不许关掉新一轮的骨架屏
        if (seq === msgListSeq) this.loadingMessages = false
      }
    },

    async selectConversation(id) {
      this._perfT0 = performance.now() // [perf] 点击会话瞬间
      this.currentId = id
      // 点列表选择会话也标记已读：红点立即消失并落库（点击会话窗口内容同样清零）
      this.markCurrentRead()

      // A方案：点过的会话先渲染快照（点击即显示、无骨架屏），随后后台静默刷新纠正
      const cached = convCacheGet(this.activeOpenid, id)
      this.currentMessages = cached ? cached.messages : []
      this.hasMore = cached ? cached.hasMore : false
      this.loadingMessages = !cached
      await this.loadMessages(id)
    },

    /** 用户点击了会话窗口范围内的内容：当前会话才算已读（本地清零并落库）。 */
    markCurrentRead() {
      const conv = this.currentConv
      if (!conv || !conv.unread_count) return
      conv.unread_count = 0
      markConversationRead(conv.id).catch(() => {})
    },

    /** 右键菜单会话操作：乐观更新本地 → PATCH 落库（{pinned|read|muted}）→ 按后端返回校正并重排；失败回滚并抛错由调用方提示。 */
    async patchConversation(conv, patch) {
      const snap = { pinned: conv.pinned, muted: conv.muted, unread_count: conv.unread_count }
      if ('pinned' in patch) conv.pinned = patch.pinned
      if ('muted' in patch) conv.muted = patch.muted
      if ('read' in patch) conv.unread_count = patch.read ? 0 : 1 // true清未读 / false标为未读(记1)
      try {
        const data = await updateConversation(conv.id, patch)
        conv.pinned = data.pinned
        conv.muted = data.muted
        conv.unread_count = data.unread_count
      } catch (e) {
        Object.assign(conv, snap)
        throw e
      } finally {
        this.sortConversations() // 乐观/校正/回滚三种结局统一重排
      }
    },

    /** 往前翻更早的记录（滚动到顶时调）。 */
    async loadOlderMessages() {
      if (!this.currentId || !this.hasMore || this.loadingMore) return
      const convId = this.currentId
      this.loadingMore = true
      try {
        const oldest = this.currentMessages[0]?.id
        const data = await fetchMessages(convId, oldest)
        // 等待期间切了会话：旧会话的翻页不得前插进新会话
        if (this.currentId !== convId) return
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
          operator_name: this.operatorName || '客服',
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

    /** 连接 WebSocket 并按 data.openid 分发推送。 */
    connect() {
      // 断线重连成功后补拉一次：后端重启/网络闪断期间错过的推送（未读红点、
      // 新消息气泡）靠这里找回来，不用手动刷新页面
      const resync = () => {
        this.loadConversations()
        if (this.currentId) this.loadMessages(this.currentId).catch(() => {})
      }
      connectWs((event, data) => {
        // 路由规则：本账号 → 正常处理；我的其他账号 → 卡片未读+1；别人的 → 忽略。
        // 旧事件不带 openid 时保持原行为（进当前视图）。
        if (data?.openid && data.openid !== this.activeOpenid) {
          if (event === 'new_message' && this.myDevice(data.openid)) this.onCrossMessage(data)
          return
        }
        if (event === 'new_message') this.onNewMessage(data)
        else if (event === 'send_result') this.onSendResult(data)
        else if (event === 'conv_updated') this.onConvUpdated(data)
        else if (event === 'message_revoked') this.onMessageRevoked(data)
      }, resync)
    },

    /** 其他绑定账号来消息：对应卡片未读 +1（不弹框；红点由 unreadOf 统一派生）。 */
    onCrossMessage(d) {
      const dev = this.myDevice(d.openid)
      if (!dev) return
      if (d.direction === 1) dev.unread = (dev.unread || 0) + 1
    },

    /** 资料解析完成后推送：重拉列表；当前会话重拉消息（昵称/头像补齐即刷新）。 */
    async onConvUpdated() {
      await this.loadConversations()
      if (this.currentId) await this.loadMessages(this.currentId)
    },

    onNewMessage(d) {
      const conv = this.conversations.find((c) => c.id === d.conversation_id)
      if (conv) {
        // 系统灰条直接用原文；残留的微信 XML（未识别类型）不进会话摘要
        conv.last_msg = summaryOf(d)
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
