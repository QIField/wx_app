/* ===== useBoundaryResize.js · 面板边界拖拽调宽（无可见拖拽条） =====
 *
 * 悬停面板右缘 ±EDGE_ZONE 触发区显示 col-resize 光标，按住左键拖动实时调宽，
 * 松开把宽度持久化到 localStorage。纯边界坐标监听实现交互，不渲染任何拖拽条 DOM。
 * 光标经 body 类全局强制：列表项、按钮等自带 cursor 的子元素会盖掉继承光标，
 * 不加 !important 无法保证触发区内统一显示拖拽箭头。
 */

import { onBeforeUnmount, ref } from 'vue'

const EDGE_ZONE = 5 // 边界左右各 5px 触发区

export function useBoundaryResize({ initial = 264, min = 220, max = 420, storageKey } = {}) {
  const width = ref(clamp(readSaved()))

  let panel = null      // 被调宽的元素（函数 ref 注入）
  let hovering = false  // 是否悬停在触发区内（状态变化才切 class，避免每帧写 DOM）
  let drag = null       // { startX, startW }

  function clamp(w) {
    return Math.min(max, Math.max(min, w))
  }

  function readSaved() {
    try {
      const saved = Number(localStorage.getItem(storageKey))
      if (Number.isFinite(saved) && saved > 0) return saved
    } catch { /* 隐私模式等场景忽略 */ }
    return initial
  }

  function save() {
    try { localStorage.setItem(storageKey, String(width.value)) } catch { /* 忽略 */ }
  }

  /** 鼠标是否落在面板右缘 ±EDGE_ZONE 触发区 */
  function inZone(clientX) {
    if (!panel) return false
    const right = panel.getBoundingClientRect().right
    return clientX >= right - EDGE_ZONE && clientX <= right + EDGE_ZONE
  }

  function toggleHover(on) {
    if (hovering === on) return
    hovering = on
    document.body.classList.toggle('edge-resize-hover', on)
  }

  /* 悬停检测：只管光标，不参与拖拽 */
  function onHoverMove(e) {
    if (drag) return // 拖拽中光标由 edge-resizing 全局接管
    toggleHover(inZone(e.clientX))
  }

  function onDown(e) {
    if (drag || e.button !== 0 || !inZone(e.clientX)) return
    e.preventDefault() // 阻止选中文字 / 原生拖拽等默认行为
    drag = { startX: e.clientX, startW: width.value }
    toggleHover(false)
    document.body.classList.add('edge-resizing')
    document.body.style.userSelect = 'none'
    window.addEventListener('mousemove', onDragMove)
    window.addEventListener('mouseup', onUp)
  }

  function onDragMove(e) {
    if (!drag) return
    e.preventDefault()
    // 实时调宽：col-main 为 flex 弹性区自动跟随，无需手动同步其他区域
    width.value = clamp(drag.startW + (e.clientX - drag.startX))
  }

  function onUp() {
    window.removeEventListener('mousemove', onDragMove)
    window.removeEventListener('mouseup', onUp)
    drag = null
    document.body.classList.remove('edge-resizing')
    document.body.style.userSelect = ''
    save() // 拖拽结束后持久化
  }

  /** 函数 ref：挂在被调宽的元素上（卸载时 Vue 会回调 null） */
  function bind(el) { panel = el }

  window.addEventListener('mousemove', onHoverMove)
  window.addEventListener('mousedown', onDown)
  onBeforeUnmount(() => {
    window.removeEventListener('mousemove', onHoverMove)
    window.removeEventListener('mousedown', onDown)
    if (drag) onUp()
    else toggleHover(false)
  })

  return { width, bind }
}
