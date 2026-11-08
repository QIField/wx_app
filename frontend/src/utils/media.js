/* ===== media.js · 媒体地址统一生成 ===== */

/** 媒体地址：<img>/<audio>/<video> 带不了 Authorization 头，统一走 ?token= 兜底。
 *  图片在服务端按 1→2→3 档降级下载，每条消息只保存一张，聊天展示与放大预览
 *  共用同一个地址，不再区分缩略图/高清档。 */
import { getToken } from '../api'

export function mediaUrlOf(m) {
  const token = `token=${encodeURIComponent(getToken())}`
  return `/api/messages/${m.id}/media?${token}`
}

/** B方案：打开会话后后台预取图片（媒体接口 max-age=86400，进浏览器磁盘缓存），
 *  之后滑动历史时秒出。静默失败、fire-and-forget，不阻塞任何交互。 */
export function prewarmThumbs(messages, limit = 30) {
  if (!Array.isArray(messages)) return
  messages
    .filter((m) => m && m.msg_type === 2)
    .slice(0, limit)
    .forEach((m) => {
      const img = new Image()
      img.src = mediaUrlOf(m)
    })
}
