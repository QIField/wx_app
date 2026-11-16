/** 聊天骨架屏：进会话先给呼吸占位，行数按聊天区高度铺满（ChatPanel 用）。
 *
 * 旧行数固定 6 行挤在顶部，下面大片空白，观感像"没加载完"。
 * 改为：实测聊天区高度 → 按行高换算行数铺满整个区域；内容按「in 连发成簇 /
 * out 回应 / 簇间时间胶囊」的对话节奏排布，宽高错落，各行 shimmer 相位错开。
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'

const SK_GAP = 16 // 行间距（与 CSS .sk-row margin-bottom 一致）
const SK_TIME_H = 36 // 时间胶囊行高估算（胶囊 + 上下间距）
/* 一个「对话周期」：in 连发成簇 → out 回应 → 时间胶囊，宽高错落；循环填充直到铺满 */
const SK_CYCLE = [
  { w: 168, h: 34, dir: 'in' }, { w: 214, h: 34, dir: 'in' }, { w: 150, h: 58, dir: 'in' }, 'time',
  { w: 124, h: 34, dir: 'out' }, { w: 226, h: 34, dir: 'out' }, { w: 178, h: 58, dir: 'out' }, 'time',
  { w: 190, h: 34, dir: 'in' }, { w: 208, h: 72, dir: 'in' }, 'time',
  { w: 158, h: 34, dir: 'out' }, { w: 232, h: 58, dir: 'out' }, { w: 118, h: 34, dir: 'out' }, 'time',
  { w: 184, h: 34, dir: 'in' }, { w: 144, h: 58, dir: 'in' }, { w: 216, h: 34, dir: 'in' }, 'time',
  { w: 170, h: 34, dir: 'out' }, { w: 198, h: 58, dir: 'out' }, 'time',
  { w: 156, h: 34, dir: 'in' }, { w: 204, h: 34, dir: 'in' }, { w: 138, h: 58, dir: 'in' },
]

/** scroller：聊天滚动区 ref（挂载后实测 clientHeight，窗口缩放跟随）。 */
export function useChatSkeleton(scroller) {
  const paneH = ref(0)
  let offResize = null
  onMounted(() => {
    const measure = () => { paneH.value = scroller.value?.$el?.clientHeight || 0 }
    measure()
    window.addEventListener('resize', measure)
    offResize = () => window.removeEventListener('resize', measure)
  })
  onUnmounted(() => offResize?.())

  const skeletonRows = computed(() => {
    const target = paneH.value || 560 // 首帧未量到高度时按常见窗格高度兜底
    const rows = []
    let used = 0
    let k = 0
    while (used < target && k < 120) {
      const item = SK_CYCLE[k % SK_CYCLE.length]
      if (item === 'time') {
        rows.push({ time: true })
        used += SK_TIME_H
      } else {
        rows.push(item)
        used += item.h + SK_GAP
      }
      k++
    }
    return rows
  })

  return { skeletonRows }
}
