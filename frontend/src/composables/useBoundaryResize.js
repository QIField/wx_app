/* ===== useBoundaryResize.js · 面板边界拖拽调宽 =====
 *
 * 两种模式：
 *   1) 无 edge 元素（列表类场景）：调用 bind(el) 后启用全局 window 监听，
 *      悬停面板边界 ±edgeZone 触发区显示 col-resize 光标，按下拖动实时调宽。
 *   2) 有 edge 元素（拓展栏场景）：bindEdge(el) 在显式 DOM 上绑事件，无触发区错位问题。
 *
 * 松开把宽度持久化到 localStorage。
 *
 * 性能要点：
 *   - 拖拽更新按 requestAnimationFrame 节流：高频鼠标（125~1000Hz）下每显示帧只回流一次
 *   - 悬停判定缓存面板 rect（resize / 拖拽结束时失效），避免每次 mousemove 强制重排
 *   - 全局监听懒注册：只有真正用到模式 A 的实例才挂 window 监听
 */

import { onBeforeUnmount, ref } from 'vue'

// 模块级共享：任一实例拖拽中时，其余实例的悬停检测全部让位。
// 列表与拓展栏两个实例共用同一组 body 光标类（edge-resize-hover / edge-resizing），
// 不加互斥的话，A 实例拖拽中 B 实例的 mousemove 会把 dragging 类清掉，
// 导致宽度过渡动画重新生效（拖拽跟手感丧失）与光标回退。
let activeDrag = false

/**
 * @param {Object} opts
 * @param {number} opts.initial
 * @param {number|() => number} opts.min
 * @param {number|() => number} opts.max
 * @param {string} opts.storageKey
 * @param {'left'|'right'} [opts.edgeSide='right'] 鼠标方向与宽度增减的正负关系
 *   - 'right': 鼠标 x 增加 → 宽度增加（左面板右缘）
 *   - 'left':  鼠标 x 增加 → 宽度减小（右面板左缘）
 * @param {number} [opts.edgeZone=5] 全局监听模式的边界触发区 ±px
 */
export function useBoundaryResize({
  initial = 264,
  min = 220,
  max = 420,
  storageKey,
  edgeSide = 'right',
  edgeZone = 5,
} = {}) {
  /* ---------- 宽度存取 ---------- */

  const resolveMin = () => (typeof min === 'function' ? min() : min)
  const resolveMax = () => (typeof max === 'function' ? max() : max)
  const clamp = (w) => Math.min(resolveMax(), Math.max(resolveMin(), w))

  function readSaved() {
    try {
      const saved = Number(localStorage.getItem(storageKey))
      if (Number.isFinite(saved) && saved > 0) return saved
    } catch { /* 隐私模式等场景忽略 */ }
    return initial
  }

  const width = ref(clamp(readSaved()))

  /* 拖拽中标记：组件用它确定性关闭宽度过渡（比 body 全局类更可靠） */
  const isDragging = ref(false)

  function save() {
    try { localStorage.setItem(storageKey, String(width.value)) } catch { /* 忽略 */ }
  }

  /* ---------- 光标状态机 ---------- */
  let cursor = 'default'
  function setCursor(next) {
    if (cursor === next) return
    cursor = next
    document.body.classList.toggle('edge-resize-hover', next === 'hover')
    document.body.classList.toggle('edge-resizing', next === 'dragging')
  }

  /* ---------- 核心拖拽流程（rAF 节流：每显示帧最多回流一次） ---------- */
  let drag = null   // { startX, startW }
  let rafId = 0     // 待执行的 applyDrag 帧句柄
  let pendingX = 0  // 最近一次 mousemove 的 clientX

  function startDrag(clientX) {
    if (activeDrag) return // 已有实例在拖拽：拒绝并发
    activeDrag = true
    isDragging.value = true
    drag = { startX: clientX, startW: width.value }
    pendingX = clientX
    setCursor('dragging')
    document.body.style.userSelect = 'none'
    window.addEventListener('mousemove', onDragMove, { passive: false })
    window.addEventListener('mouseup', endDrag)
  }

  function onDragMove(e) {
    if (!drag) return
    e.preventDefault()
    pendingX = e.clientX
    if (!rafId) rafId = requestAnimationFrame(applyDrag)
  }

  function applyDrag() {
    rafId = 0
    if (!drag) return
    const sign = edgeSide === 'right' ? 1 : -1
    width.value = clamp(drag.startW + sign * (pendingX - drag.startX))
  }

  function endDrag() {
    window.removeEventListener('mousemove', onDragMove)
    window.removeEventListener('mouseup', endDrag)
    if (rafId) { cancelAnimationFrame(rafId); rafId = 0 }
    drag = null
    activeDrag = false
    isDragging.value = false
    setCursor('default')
    document.body.style.userSelect = ''
    invalidateRect() // 宽度已变：悬停 rect 缓存失效
    save()
  }

  /* ---------- 模式 A：全局 window 监听（列表类无显式 edge 元素） ---------- */

  let panel = null
  let rect = null // 面板 rect 缓存：悬停判定高频使用，避免每次 mousemove 强制重排

  function invalidateRect() { rect = null }

  function inZone(clientX) {
    if (!panel) return false
    if (!rect) rect = panel.getBoundingClientRect()
    const r = rect
    if (edgeSide === 'right') {
      return clientX >= r.right - edgeZone && clientX <= r.right + edgeZone
    } else {
      return clientX >= r.left - edgeZone && clientX <= r.left + edgeZone
    }
  }

  function onHoverMove(e) {
    if (drag || activeDrag) return // 自己或别的实例在拖拽：不动光标状态
    setCursor(inZone(e.clientX) ? 'hover' : 'default')
  }

  function onWindowDown(e) {
    if (drag || activeDrag || e.button !== 0 || !inZone(e.clientX)) return
    e.preventDefault()
    startDrag(e.clientX)
  }

  function onWinResize() { invalidateRect() }

  let globalBound = false
  function enableGlobal() {
    if (globalBound) return
    globalBound = true
    window.addEventListener('mousemove', onHoverMove)
    window.addEventListener('mousedown', onWindowDown)
    window.addEventListener('resize', onWinResize)
  }

  /** 函数 ref：挂在被调宽的元素上（卸载时 Vue 会回调 null） */
  function bind(el) {
    panel = el
    invalidateRect()
    if (el) enableGlobal() // 懒注册：真正用到模式 A 才挂全局监听
  }

  onBeforeUnmount(() => {
    if (globalBound) {
      window.removeEventListener('mousemove', onHoverMove)
      window.removeEventListener('mousedown', onWindowDown)
      window.removeEventListener('resize', onWinResize)
    }
    if (drag) endDrag()
    else setCursor('default')
  })

  /* ---------- 模式 B：显式 edge 元素绑定（拓展栏类有可见 edge） ---------- */

  /** 直接绑在 edge DOM 上：mouseenter → hover，mousedown → startDrag。
   *  返回清理函数，组件在 onBeforeUnmount 自行调用。 */
  function bindEdge(el) {
    if (!el) return
    const onEnter = () => { if (!drag && !activeDrag) setCursor('hover') }
    const onLeave = () => { if (!drag) setCursor('default') }
    const onDown = (e) => {
      if (e.button !== 0) return
      e.preventDefault()
      startDrag(e.clientX)
    }
    el.addEventListener('mouseenter', onEnter)
    el.addEventListener('mouseleave', onLeave)
    el.addEventListener('mousedown', onDown)
    return () => {
      el.removeEventListener('mouseenter', onEnter)
      el.removeEventListener('mouseleave', onLeave)
      el.removeEventListener('mousedown', onDown)
    }
  }

  return { width, isDragging, bind, bindEdge }
}
