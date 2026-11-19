/** 消息媒体加载辅助：尺寸预占位 / 加载状态 / 失败自动重试（MessageRow 与 QuoteBlock 共用）。 */
import { computed, ref, watch } from 'vue'

/** 尺寸换算：按显示上限等比缩到盒子（无宽高返回 null，交由 natural 兜底）。 */
function fitBox(w, h, maxW, maxH) {
  const nw = Number(w)
  const nh = Number(h)
  if (!nw || !nh) return null
  const s = Math.min(1, maxW / nw, maxH / nh)
  return { width: `${Math.round(nw * s)}px`, height: `${Math.round(nh * s)}px` }
}

/** S2 尺寸预占位：后端下发缩略图宽高（payload.w/h，与原图同比例），按显示上限
 * 换算最终盒子，占位与加载后同尺寸 → 高度零突变。历史消息无宽高则在 @load 后
 * 用自然尺寸补盒子（否则骨架屏 min-height 大于图片高度，图下会露一条灰底）。
 * onReady 在首次加载完成时回调（撤 shimmer 占位 / 通知父层重新锚定）。 */
export function useImgBox(sizeOf, maxW, maxH, onReady) {
  const natural = ref(null)
  const box = computed(() => fitBox(sizeOf()?.w, sizeOf()?.h, maxW, maxH) || natural.value)
  function onLoad(e) {
    if (!natural.value) {
      natural.value = fitBox(e?.target?.naturalWidth, e?.target?.naturalHeight, maxW, maxH)
    }
    onReady?.()
  }
  return { box, onLoad }
}

/** 媒体加载状态：加载前 shimmer 占位块，加载完淡入（组件按消息 id 复用，状态不串行）；
 * 首次就绪时 emit mediaload 通知父层贴底锚定。坏图也走就绪收尾，避免永远闪 shimmer。 */
export function useMediaLoad(emit) {
  const loaded = ref(false)
  function onMediaOk() {
    if (!loaded.value) {
      loaded.value = true
      emit('mediaload')
    }
  }
  return { loaded, onMediaOk }
}

/** 图片加载失败自动重试一次：中间方下载瞬时失败（后端 502）实测 2~3 秒内自愈，
 * 拼 cache-bust 参数强制浏览器重新请求，免去用户"切走再切回来"手动触发重试；
 * 重试仍失败调 giveUp（撤占位进入撕裂态）。withBust 给展示地址拼重试参数
 * （媒体接口 URL 已带 ?token=，本地 path 无查询串，按有无 ? 选连接符）。 */
export function useImgRetry() {
  const imgRetried = ref(false)
  const imgBust = ref('')
  function withBust(base) {
    return imgBust.value
      ? `${base}${base.includes('?') ? '&' : '?'}rt=${imgBust.value}`
      : base
  }
  function onImgError(giveUp) {
    if (!imgRetried.value) {
      imgRetried.value = true
      setTimeout(() => { imgBust.value = Date.now() }, 1500)
      return
    }
    giveUp?.()
  }
  return { withBust, onImgError }
}

/** 图片加载失败降级：微信 qlogo 等外链头像会过期返回 404，浏览器一定会打红字，
 *  但我们可以在 @error 触发后切换 UI —— 源 URL 变化时自动重置（避免旧失败粘住新图）。
 *  返回 { failed, onError }，模板 v-if="src && !failed" + @error="onError" 即可。 */
export function useImageFallback(source) {
  const failed = ref(false)
  watch(source, () => { failed.value = false })
  function onError() { failed.value = true }
  return { failed, onError }
}
