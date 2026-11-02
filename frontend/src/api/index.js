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
    // 令牌失效：清掉回登录页（/auth/me 交给启动流程自己处理，避免刷新循环）
    if (err.response?.status === 401 && err.config?.url !== '/auth/me') {
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

export const fetchOrgs = () => http.get('/orgs')

/* ===== 审计日志 / 总览 ===== */

export const fetchAuditLogs = (keyword) =>
  http.get('/audit-logs', { params: keyword ? { keyword } : {} })

export const fetchAdminStats = () => http.get('/admin/stats')

/* ===== 工作台（多账号：openid 选当前查看的聊天账号，缺省=第一个绑定） ===== */

export const fetchDevices = () => http.get('/devices')

export const fetchConversations = (openid) =>
  http.get('/conversations', { params: { openid: openid || undefined } })

/** 主动发起会话：按 wxid 建/取会话（chat_type: 1好友 2群），联系人须在通讯录里。 */
export const openConversation = (wxid, chatType, openid) =>
  http.post('/conversations', { wxid, chat_type: chatType }, { params: { openid: openid || undefined } })

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

/** 联系人档案：备注/标签（业务自建，按 wxid，好友与群通用）。 */
export const fetchContactProfile = (wxid) => http.get(`/contacts/${wxid}/profile`)

export const saveContactProfile = (wxid, payload) =>
  http.put(`/contacts/${wxid}/profile`, payload)

/** WebSocket 长连接：收到推送回调 onEvent(event, data)。 */
export function connectWs(onEvent) {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const ws = new WebSocket(`${proto}://${location.host}/ws`)

  ws.onmessage = (e) => {
    try {
      const { event, data } = JSON.parse(e.data)
      if (event && event !== 'ping') onEvent(event, data)
    } catch { /* 心跳/坏包忽略 */ }
  }
  ws.onclose = () => setTimeout(() => connectWs(onEvent), 2000) // 断线重连
  return ws
}
