/* ===== media.js · 媒体地址统一生成 ===== */

/** 媒体地址：<img>/<audio>/<video> 带不了 Authorization 头，统一走 ?token= 兜底；
 *  imgType 仅图片消息有效：后端会把中间方 1/2/3 三档全部下载并按像素比较，
 *  再以 img_type=1/2/3 暴露清晰度名次（1 最清、3 缩略图，不传默认 3）。
 *  气泡/引用用 IMG_THUMB 省流量，点开预览与复制用 IMG_BIG。 */
import { getToken } from '../api'

/** 图片档位唯一事实来源（语义见文件头注释；改这里即可全局生效）。 */
export const IMG_BIG = 1 // 最清（点开预览、复制图片）
export const IMG_THUMB = 3 // 缩略图（气泡与引用块）

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
      img.src = mediaUrlOf(m, IMG_THUMB)
    })
}
