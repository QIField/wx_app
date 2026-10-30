/** 后端接口封装：所有调后端的代码只写在这。 */
import axios from 'axios'

const http = axios.create({ baseURL: '/api', timeout: 10000 })

// 统一拆包：后端返回 {code, msg, data}，code!=0 视为业务错误
http.interceptors.response.use(
  (resp) => {
    const body = resp.data
    if (body && body.code !== 0) return Promise.reject(new Error(body.msg))
    return body ? body.data : null
  },
  (err) => Promise.reject(new Error(err.response?.data?.msg || err.message))
)

export const fetchConversations = () => http.get('/conversations')

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
export const fetchContacts = (type, keyword) =>
  http.get('/contacts', { params: { type, keyword: keyword || undefined } })

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
