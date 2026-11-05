/* ===== media.js · 媒体地址统一生成 ===== */

/** 媒体地址：<img>/<audio>/<video> 带不了 Authorization 头，统一走 ?token= 兜底；
 *  imgType 仅图片消息有效（1高清 2常规 3缩略图），引用块缩略图用 3、看大图用 2。 */
import { getToken } from '../api'

export function mediaUrlOf(m, imgType) {
  const token = `token=${encodeURIComponent(getToken())}`
  return imgType
    ? `/api/messages/${m.id}/media?img_type=${imgType}&${token}`
    : `/api/messages/${m.id}/media?${token}`
}
