/* ===== media.js · 媒体地址统一生成 ===== */

/** 媒体地址：<img>/<audio>/<video> 带不了 Authorization 头，统一走 ?token= 兜底；
 *  imgType 仅图片消息有效（实测中间方语义：2=大图/高清，1 与 3 均返回缩略图）——
 *  气泡/引用缩略图用 3 省流量，点开大图用 2。 */
import { getToken } from '../api'

export function mediaUrlOf(m, imgType) {
  const token = `token=${encodeURIComponent(getToken())}`
  return imgType
    ? `/api/messages/${m.id}/media?img_type=${imgType}&${token}`
    : `/api/messages/${m.id}/media?${token}`
}

/** B方案：打开会话后后台预取图片缩略图（媒体接口带 max-age=86400，进浏览器磁盘缓存），
 *  之后上翻历史缩略图层秒出。静默失败、fire-and-forget，不阻塞任何交互。 */
export function prewarmThumbs(messages, limit = 30) {
  if (!Array.isArray(messages)) return
  messages
    .filter((m) => m && m.msg_type === 2)
    .slice(0, limit)
    .forEach((m) => {
      const img = new Image()
      img.src = mediaUrlOf(m, 3)
    })
}
