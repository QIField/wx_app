/** 后端接口封装：所有调后端的代码只写在这。 */
import axios from 'axios'

const TOKEN_KEY = 'wxcs_token'

export const getToken = () => localStorage.getItem(TOKEN_KEY) || ''
export const setToken = (t) =>
  t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY)

const http = axios.create({ baseURL: '/api', timeout: 10000 })

// 请求拦截：自动带登录令牌
http.interceptors.request.use((cfg) => {
  const token = getToken()
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

// 统一拆包：后端返回 {code, msg, data}，code!=0 视为业务错误
http.interceptors.response.use(
  (resp) => {
    const body = resp.data
    if (body && body.code !== 0) return Promise.reject(new Error(body.msg))
    return body ? body.data : null
  },
  (err) => {
    const data = err.response?.data
    // 初始密码强制改密：广播给 App.vue 弹窗（改密接口与 /me 自身不受拦）
    if (err.response?.status === 403 && data?.err === 'PASSWORD_CHANGE_REQUIRED') {
      window.dispatchEvent(new CustomEvent('need-change-password'))
      return Promise.reject(
        Object.assign(new Error(data.msg || '请先修改初始密码'), { code: 'PASSWORD_CHANGE_REQUIRED' })
      )
    }
    // 令牌失效：清掉回登录页（/auth/me、/auth/login 交给调用方自己处理：
    // 前者避免刷新循环，后者是账号密码错误，必须在登录页内提示而非跳页）
    if (
      err.response?.status === 401 &&
      !['/auth/me', '/auth/login'].includes(err.config?.url)
    ) {
      setToken('')
      location.replace('/')
      return new Promise(() => {})
    }
    return Promise.reject(new Error(data?.msg || err.message))
  }
)

/* ===== 认证 ===== */

export const apiLogin = (username, password) =>
  http.post('/auth/login', { username, password })

export const fetchMe = () => http.get('/auth/me')

/** 自助修改密码（初始密码账号的强制改密也走这里）。 */
export const apiChangePassword = (oldPassword, newPassword) =>
  http.put('/auth/password', { old_password: oldPassword, new_password: newPassword })

/* ===== 账号管理 ===== */

export const fetchAccounts = () => http.get('/accounts')

export const createAccount = (payload) => http.post('/accounts', payload)

export const updateAccount = (id, payload) => http.put(`/accounts/${id}`, payload)

export const toggleAccountStatus = (id, status) =>
  http.put(`/accounts/${id}/status`, { status })

export const resetAccountPassword = (id) => http.put(`/accounts/${id}/password`)

/* ===== 组织字典 ===== */

/** 启用中的组织：账号表单等使用处的下拉数据源（每次实时查询）。 */
export const fetchOrgs = () => http.get('/orgs')

/** 全量组织（含已删除）：组织管理表格数据源。 */
export const fetchAllOrgs = () => http.get('/orgs/all')

export const createOrg = (name) => http.post('/orgs', { name })

/** 组织状态：0=软删除（行保留，可恢复）1=启用。 */
export const updateOrgStatus = (id, status) => http.put(`/orgs/${id}/status`, { status })

/* ===== 设备字典管理（developer/admin 可读，developer 可写） ===== */

/** 设备列表：附组织名与关联账号 bound_users（可多个，跨组织）。 */
export const fetchAdminDevices = (params) => http.get('/admin/devices', { params })

/** 入库新设备 {openid, name, org_id}；openid 全局唯一（重复 409）。 */
export const createAdminDevice = (payload) => http.post('/admin/devices', payload)

/** 编辑设备 {name, org_id}；openid 录入后不可改（body 里的 openid 被忽略）。 */
export const updateAdminDevice = (id, payload) => http.put(`/admin/devices/${id}`, payload)

/** 删除设备：仍被账号关联时 409，需先在账号管理解除关联。 */
export const deleteAdminDevice = (id) => http.delete(`/admin/devices/${id}`)

/** 从回收站恢复设备（软删除反向操作，原 id 与关联不变）。 */
export const restoreAdminDevice = (id) => http.post(`/admin/devices/${id}/restore`)

/* ===== 审计日志 / 总览 ===== */

export const fetchAuditLogs = (keyword) =>
  http.get('/audit-logs', { params: keyword ? { keyword } : {} })

export const fetchAdminStats = () => http.get('/admin/stats')

/* ===== 工作台（多账号：openid 选当前查看的聊天账号，缺省=第一个绑定） ===== */

export const fetchDevices = () => http.get('/devices')

/** 点击账号卡片即时查一次在线状态（调中间方 check_online 并回写）。 */
export const checkDeviceOnline = (openid) =>
  http.post(`/devices/${openid}/online-check`)

export const fetchConversations = (openid) =>
  http.get('/conversations', { params: { openid: openid || undefined } })

/** 主动发起会话：按 contact_id 建/取会话（chat_type: 1好友 2群），不传 wxid（脱敏契约）。 */
export const openConversation = (contactId, chatType, openid) =>
  http.post('/conversations', { contact_id: contactId, chat_type: chatType }, { params: { openid: openid || undefined } })

/** 会话操作：置顶（{pinned:0|1}）/ 清未读（{read:true}）。 */
export const updateConversation = (convId, payload) =>
  http.patch(`/conversations/${convId}`, payload)

/** 清零未读数（落库）：避免重拉列表时旧未读数把红点又盖回来。 */
export const markConversationRead = (convId) =>
  updateConversation(convId, { read: true })

export const fetchMessages = (convId, beforeId) =>
  http.get(`/conversations/${convId}/messages`, {
    params: beforeId ? { before_id: beforeId } : {},
    timeout: 30000, // 消息拉取可能含多图/附件，比默认 10s 放宽
  })

/** 群成员名册：@提及选择器数据源（附全拼/首字母，前端本地过滤）。 */
export const fetchConversationMembers = (convId) =>
  http.get(`/conversations/${convId}/members`)

export const sendTextMessage = (convId, content, payload = {}) =>
  http.post(`/conversations/${convId}/messages`, {
    msg_type: 1,
    content,
    payload,
  })

/** 上传任意文件：返回 {url(中间方可下载的绝对地址), path(本地预览相对路径), file_name, size}。 */
export const uploadFile = (file) => {
  const form = new FormData()
  form.append('file', file)
  return http.post('/uploads', form, { timeout: 60000 }) // 大文件放宽超时
}

/* ===== 自定义铃声 ===== */

/** 当前登录人的自定义铃声列表：[{id, name, file_name, url, size, fmt, created_at}]。 */
export const fetchRingtones = () => http.get('/ringtones')

/** 上传自定义铃声（MP3/M4A/WAV/OGG，≤5MB）：返回新建行的同列表结构。 */
export const uploadRingtone = (file) => {
  const form = new FormData()
  form.append('file', file)
  return http.post('/ringtones', form, { timeout: 60000 })
}

/** 删除自定义铃声（后端软删除）；若删除的是当前铃声，前端需回退默认。 */
export const deleteRingtone = (id) => http.delete(`/ringtones/${id}`)

/** 发媒体消息：msgType 2图片 3文件 4视频 5链接卡片，payload 按类型给对应 url 字段。 */
export const sendMediaMessage = (convId, msgType, content, payload) =>
  http.post(`/conversations/${convId}/messages`, { msg_type: msgType, content, payload })

/** 撤回自己发的消息（微信限制发出 2 分钟内）：成功后 WS 广播 message_revoked 换灰条。 */
export const revokeMessage = (messageId) => http.post(`/messages/${messageId}/revoke`)

/** 转发消息：{conv_id 源会话, msg_ids, target_ids, mode: 'single'|'merge'}。
 *  single=逐条真实下发（普通气泡，非本人消息带原发送者前缀）；
 *  merge=合并转发（目标会话各落一张本地卡片 msg_type=9 + 快照回看）。 */
export const forwardMessages = (payload) => http.post('/messages/forward', payload)

/** 历史消息搜索：跨会话/单会话，支持关键词+日期+类型+方向+发送人筛选。 */
export const searchMessages = (params) =>
  http.get('/messages/search', { params })

/** 消息日期元数据：返回有消息的年份/月份/日期集合，供日历组件渲染。 */
export const fetchMessageDateMeta = (convId) =>
  http.get('/messages/date-meta', { params: convId ? { conv_id: convId } : {} })

/** 合并转发卡片回看：{title, count, items:[{seq, sender_name, content, create_time}]}。 */
export const fetchForwardSnapshot = (messageId) => http.get(`/messages/${messageId}/forward-snapshot`)

/** 最近转发目标（选择器置顶区）：[{conversation_id, name, chat_type}]。 */
export const fetchForwardRecent = () => http.get('/forwards/recent')

/** 通讯录：好友/群列表（type: friends | groups，keyword 可选）。 */
export const fetchContacts = (type, keyword, openid) =>
  http.get('/contacts', {
    params: { type, keyword: keyword || undefined, openid: openid || undefined },
  })

/** 发送日志：谁·何时·用哪个聊天账号·发给谁（当前账号全部绑定设备）。 */
export const fetchSendLogs = (openid) =>
  http.get('/send-logs', { params: { openid: openid || undefined } })

/** 统一备注配置（业务自建，按条目 id，好友→用户级/群→群级；不传 wxid）。
 *  用户级配置私聊与所有群聊全局共用——同一目标全场景读同一行。 */
export const fetchRemarkConfig = (contactId) => http.get(`/contacts/${contactId}/remark-config`)

export const saveRemarkConfig = (contactId, payload) =>
  http.put(`/contacts/${contactId}/remark-config`, payload)

/** 群成员备注入口：定位该成员的用户级配置（与私聊/其他群同源）。 */
export const fetchMemberRemarkConfig = (contactId, memberAlias) =>
  http.get(`/groups/${contactId}/members/${memberAlias}/remark-config`)

export const saveMemberRemarkConfig = (contactId, memberAlias, payload) =>
  http.put(`/groups/${contactId}/members/${memberAlias}/remark-config`, payload)

/* ===== 报价处理台（阶段 6） ===== */

/** 询价列表：{status: 0-4, conversation_id, page, limit} 可选，id 倒序。 */
export const fetchQuoteInquiries = (params) => http.get('/quote/inquiries', { params })

/** 人工发送报价（预览流动作）：price 可选改价（后端话术联动重建），图前文后发出。
 *  已报价 409 / 发送未启用 403 / 下发失败 502（询价转人工 review）。 */
export const sendQuoteInquiry = (id, price) =>
  http.post(`/quote/inquiries/${id}/send`, price != null && price !== '' ? { price } : {})

/** 人工忽略询价：置 ignored；已报价 409。 */
export const ignoreQuoteInquiry = (id) => http.post(`/quote/inquiries/${id}/ignore`)

/** 快捷报价配置（global 行）：配件黑名单/价格系数/AI 开关/报价模式。 */
export const fetchQuoteConfig = () => http.get('/quote/config')

/** 保存报价配置：body 任意子集，仅 admin/developer 可写（客服 403，前端 toast）。 */
export const saveQuoteConfig = (payload) => http.put('/quote/config', payload)

/* ===== 快捷报价查询/统计（拓展栏重做 · 手动报价与报价分析数据源） ===== */

/** 手动查询链式搜索：{q, part_name?} → {type, car, product, partImagesList, chain}。上游串行多跳，超时放宽 60s。 */
export const qqManualSearch = (q, partName) =>
  http.post('/quote/query/manual-search', { q, part_name: partName || undefined }, { timeout: 60000 })

/** AI 询价要素提取（AI 对话子 tab）：{text} → 场景 list。 */
export const qqExtractParts = (text) =>
  http.post('/quote/query/extract-parts', { text }, { timeout: 60000 })

/** 兆配云全网比价（中文键名列表原样透传）。 */
export const qqZpy = (number) => http.post('/quote/query/zpy', { number }, { timeout: 60000 })

/** 机汽人平台竞价：{jy_data, xj_data}。 */
export const qqJqr = (number) => http.post('/quote/query/jqr', { number }, { timeout: 60000 })

/** 采购历史：后端默认 limit=9999 一次拉全；{total:{purchase_quantity,totalprice}, list:{total,current_page,last_page,data}}。 */
export const qqPurchaseHistory = (number, page = 1, limit = null) => {
  const body = { number, page }
  if (limit !== null) body.limit = limit
  return http.post('/quote/query/purchase-history', body, { timeout: 60000 })
}

/** 报价分析统计：period=day|month → {kpi, prev, trend, days, series, top}。 */
export const fetchQuoteStats = (period) => http.get('/quote/stats', { params: { period } })

/** WebSocket 订阅：收到推送回调 onEvent(event, data)，断线重连成功触发一次 onReopen。
 * 返回 {ws, stop()}——视图卸载必须 stop()，否则断线重连闭包会永久泄漏。 */
export function connectWs(onEvent, onReopen) {
  let sock = null
  let stopped = false
  let reopened = false

  function open() {
    if (stopped) return
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    sock = new WebSocket(`${proto}://${location.host}/ws`)
    sock.onopen = () => {
      if (reopened && onReopen) onReopen()
      reopened = true
    }
    sock.onmessage = (e) => {
      try {
        const { event, data } = JSON.parse(e.data)
        if (event && event !== 'ping') onEvent(event, data)
      } catch { /* 心跳/坏包忽略 */ }
    }
    sock.onclose = () => {
      if (!stopped) setTimeout(open, 2000) // 断线重连
    }
    sock.onerror = () => sock.close()
  }

  open()
  return {
    get ws() { return sock },
    stop() {
      stopped = true
      if (sock) {
        sock.onclose = null
        sock.close()
      }
    },
  }
}
