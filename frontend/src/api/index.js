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
export const fetchAdminDevices = () => http.get('/admin/devices')

/** 入库新设备 {openid, name, org_id}；openid 全局唯一（重复 409）。 */
export const createAdminDevice = (payload) => http.post('/admin/devices', payload)

/** 编辑设备 {name, org_id}；openid 录入后不可改（body 里的 openid 被忽略）。 */
export const updateAdminDevice = (id, payload) => http.put(`/admin/devices/${id}`, payload)

/** 删除设备：仍被账号关联时 409，需先在账号管理解除关联。 */
export const deleteAdminDevice = (id) => http.delete(`/admin/devices/${id}`)

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
  })

export const sendTextMessage = (convId, content) =>
  http.post(`/conversations/${convId}/messages`, {
    msg_type: 1,
    content,
    payload: {},
  })

/** 通讯录：好友/群列表（type: friends | groups，keyword 可选）。 */
export const fetchContacts = (type, keyword, openid) =>
  http.get('/contacts', {
    params: { type, keyword: keyword || undefined, openid: openid || undefined },
  })

/** 发送日志：谁·何时·用哪个聊天账号·发给谁（当前账号全部绑定设备）。 */
export const fetchSendLogs = (openid) =>
  http.get('/send-logs', { params: { openid: openid || undefined } })

/** 联系人档案：备注/标签（业务自建，按通讯录行 id，好友与群通用；不传 wxid）。 */
export const fetchContactProfile = (contactId) => http.get(`/contacts/${contactId}/profile`)

export const saveContactProfile = (contactId, payload) =>
  http.put(`/contacts/${contactId}/profile`, payload)

/** WebSocket 长连接：收到推送回调 onEvent(event, data)；断线重连成功后触发一次
 * onReopen（首次连接不触发），供调用方补拉断连期间错过的数据。 */
export function connectWs(onEvent, onReopen) {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const ws = new WebSocket(`${proto}://${location.host}/ws`)
  let reopened = false

  ws.onopen = () => {
    if (reopened && onReopen) onReopen()
    reopened = true
  }
  ws.onmessage = (e) => {
    try {
      const { event, data } = JSON.parse(e.data)
      if (event && event !== 'ping') onEvent(event, data)
    } catch { /* 心跳/坏包忽略 */ }
  }
  ws.onclose = () => setTimeout(() => connectWs(onEvent, onReopen), 2000) // 断线重连
  return ws
}
