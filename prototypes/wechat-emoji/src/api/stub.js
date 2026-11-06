/** API 桩层：签名与 wx_app 真实接口一致，接入时仅需替换实现。
 *
 * 真实接口（wx_app 现状，零后端改动即可发表情码）：
 *   POST /conversations/{convId}/messages
 *   body: { msg_type: 1, content, payload: {} }
 *   返回: data.message_id + status(0 发送中，等 WS 推最终结果)
 */
const delay = (ms) => new Promise((r) => setTimeout(r, ms))

let seq = 1000

export async function sendTextMessage(convId, content) {
  await delay(300) // 模拟网络延迟，让"发送中"状态可见
  // TODO: replace with http.post(`/conversations/${convId}/messages`, { msg_type: 1, content, payload: {} })
  return { message_id: ++seq, status: 1 }
}
