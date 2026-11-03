<script setup>
/** 滑块拼图验证（拖动验证）：Canvas 星空拼图 + 轨迹人机校验。
    纯前端门禁组件：验证通过 emit('verified')，登录失败由父组件调用 reset() 重开一局。 */
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { renderSlideScene } from '../utils/slideScene'

const emit = defineEmits(['verified'])

const S = 44        // 拼图边长
const PAD = 10      // 拼图画布内边距（容纳右侧凸起）
const TOL = 8       // 对准容差（px）：宽松一点，差一丝丝也算通过
const HANDLE = 44   // 滑块手柄宽度（与拼图同宽，行程一致）
const STAGE_H = 120 // 图层高度

const stageRef = ref(null)
const bgRef = ref(null)
const pieceRef = ref(null)
const handleRef = ref(null)

const stageW = ref(316)
const dragX = ref(0)
const gap = ref({ x: 0, y: 0 })
const status = ref('idle') // idle | drag | pass | fail
const dragging = ref(false)

let points = [] // 轨迹采样 [{t, x}]
let grabDx = HANDLE / 2 // 按下点相对滑块左缘的偏移（保证跟手不跳变）
let resizeObs = null

const maxX = computed(() => Math.max(0, stageW.value - S))
const fillW = computed(() => Math.min(dragX.value + HANDLE, stageW.value))
const pieceStyle = computed(() => ({
  left: `${dragX.value - PAD}px`,
  top: `${gap.value.y - PAD}px`,
}))
const hintText = computed(() => ({
  idle: '按住滑块，拖动拼图完成验证',
  drag: '对准缺口后松开',
  pass: '验证通过',
  fail: '未通过，已更换拼图',
}[status.value]))

function clamp(v, lo, hi) {
  return Math.min(hi, Math.max(lo, v))
}

function randGap() {
  return {
    x: Math.round(60 + Math.random() * Math.max(10, stageW.value - S - 90)),
    y: Math.round(20 + Math.random() * (STAGE_H - S - 40)),
  }
}

/* ===== Canvas 绘制（委托 utils/slideScene） ===== */

/** 重绘一局：组件只提供几何参数，绘制交给 slideScene 工具 */
function redraw() {
  if (!bgRef.value || !pieceRef.value) return // 已卸载（延迟重置兜底）
  renderSlideScene({
    bgCanvas: bgRef.value,
    pieceCanvas: pieceRef.value,
    width: stageW.value,
    height: STAGE_H,
    gapX: gap.value.x,
    gapY: gap.value.y,
    pieceSize: S,
    pad: PAD,
  })
}

/* ===== 交互 ===== */

function onDown(e) {
  if (status.value === 'pass') return
  dragging.value = true
  status.value = 'drag'
  points = [{ t: performance.now(), x: dragX.value }]
  const left = stageRef.value.getBoundingClientRect().left
  grabDx = clamp(e.clientX - left - dragX.value, 0, HANDLE)
  handleRef.value?.setPointerCapture?.(e.pointerId)
}

function onMove(e) {
  if (!dragging.value) return
  const left = stageRef.value.getBoundingClientRect().left
  dragX.value = clamp(e.clientX - left - grabDx, 0, maxX.value)
  points.push({ t: performance.now(), x: dragX.value })
}

function onUp() {
  if (!dragging.value) return
  dragging.value = false
  points.push({ t: performance.now(), x: dragX.value })
  verify()
}

function onKey(e) {
  if (status.value === 'pass') return
  const step = e.shiftKey ? 12 : 3
  const map = {
    ArrowRight: () => clamp(dragX.value + step, 0, maxX.value),
    ArrowLeft: () => clamp(dragX.value - step, 0, maxX.value),
    Home: () => 0,
    End: () => maxX.value,
  }
  if (map[e.key]) {
    e.preventDefault()
    if (status.value === 'idle') status.value = 'drag'
    dragX.value = map[e.key]()
    points.push({ t: performance.now(), x: dragX.value })
  } else if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault()
    points.push({ t: performance.now(), x: dragX.value })
    verify()
  }
}

function verify() {
  const aligned = Math.abs(dragX.value - gap.value.x) <= TOL
  if (aligned && looksHuman()) {
    dragX.value = gap.value.x
    status.value = 'pass'
    emit('verified')
  } else {
    status.value = 'fail'
    setTimeout(reset, 500)
  }
}

/** 轨迹人机校验：有效时长、采样点数、单步位移上限（拦截瞬移脚本） */
function looksHuman() {
  if (points.length < 5) return false
  if (points[points.length - 1].t - points[0].t < 150) return false
  for (let i = 1; i < points.length; i++) {
    if (Math.abs(points[i].x - points[i - 1].x) > 60) return false
  }
  return true
}

function reset() {
  status.value = 'idle'
  dragging.value = false
  dragX.value = 0
  points = []
  gap.value = randGap()
  redraw()
}

defineExpose({ reset })

onMounted(() => {
  stageW.value = Math.round(stageRef.value.clientWidth) || stageW.value
  gap.value = randGap()
  redraw()
  resizeObs = new ResizeObserver(() => {
    const w = Math.round(stageRef.value.clientWidth)
    if (w && Math.abs(w - stageW.value) > 1) {
      stageW.value = w
      gap.value = randGap()
      redraw()
    }
  })
  resizeObs.observe(stageRef.value)
})

onBeforeUnmount(() => resizeObs?.disconnect())
</script>

<template>
  <div class="slide-captcha">
    <div ref="stageRef" class="sc-stage" :class="{ 'is-pass': status === 'pass' }">
      <canvas ref="bgRef"></canvas>
      <canvas
        ref="pieceRef"
        class="sc-piece"
        :class="{ 'is-drag': dragging }"
        :style="pieceStyle"
      ></canvas>
      <span v-if="status === 'pass'" class="sc-badge">
        <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
        通过
      </span>
    </div>

    <div
      class="sc-track"
      :class="{ 'is-pass': status === 'pass', 'is-fail': status === 'fail' }"
    >
      <div class="sc-fill" :style="{ width: `${fillW}px` }"></div>
      <span class="sc-hint" aria-live="polite">{{ hintText }}</span>
      <button
        ref="handleRef"
        type="button"
        class="sc-handle"
        :style="{ transform: `translateX(${dragX}px)` }"
        role="slider"
        aria-label="拖动滑块完成拼图验证"
        :aria-valuemin="0"
        :aria-valuemax="maxX"
        :aria-valuenow="Math.round(dragX)"
        :disabled="status === 'pass'"
        @pointerdown="onDown"
        @pointermove="onMove"
        @pointerup="onUp"
        @pointercancel="onUp"
        @keydown="onKey"
      >
        <svg v-if="status === 'pass'" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
        <svg v-else xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 17 5-5-5-5"/><path d="m13 17 5-5-5-5"/></svg>
      </button>
    </div>
  </div>
</template>

<style scoped>
.slide-captcha {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.sc-stage {
  position: relative;
  height: 120px;
  border-radius: var(--r-md);
  overflow: hidden;
  border: 1px solid var(--c-border-strong);
  background: #0e1c3c;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.sc-stage.is-pass {
  border-color: var(--c-ok);
  box-shadow: 0 0 0 1px var(--c-ok) inset;
}
.sc-stage canvas {
  position: absolute;
  inset: 0;
}
.sc-piece {
  pointer-events: none;
  touch-action: none;
  filter: drop-shadow(0 4px 8px rgba(4, 12, 32, 0.5));
}
.sc-piece.is-drag {
  filter: drop-shadow(0 6px 12px rgba(4, 12, 32, 0.55));
}
.sc-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 9px;
  border-radius: 999px;
  font-size: 11px;
  color: #fff;
  background: rgba(24, 160, 88, 0.92);
}
.sc-track {
  position: relative;
  height: 38px;
  border-radius: var(--r-md);
  overflow: hidden;
  border: 1px solid var(--c-border-strong);
  background: var(--c-bg);
  user-select: none;
  transition: border-color 0.2s, background 0.2s;
}
.sc-track.is-pass {
  border-color: var(--c-ok);
  background: var(--c-ok-soft);
}
.sc-track.is-fail {
  border-color: var(--c-danger);
  animation: sc-shake 0.36s;
}
@keyframes sc-shake {
  20% { transform: translateX(-4px); }
  40% { transform: translateX(4px); }
  60% { transform: translateX(-3px); }
  80% { transform: translateX(3px); }
}
.sc-fill {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  background: var(--c-primary-soft);
  transition: background 0.2s;
}
.sc-track.is-pass .sc-fill {
  background: var(--c-ok-soft);
}
.sc-hint {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  font-size: 12px;
  letter-spacing: 0.5px;
  color: var(--c-text-sub);
  user-select: none;
  pointer-events: none;
}
.sc-track.is-fail .sc-hint {
  color: var(--c-danger);
}
.sc-track.is-pass .sc-hint {
  color: var(--c-ok);
}
.sc-handle {
  position: absolute;
  top: 0;
  left: 0;
  width: 44px;
  height: 100%;
  display: grid;
  place-items: center;
  background: var(--c-panel);
  border: none;
  border-right: 1px solid var(--c-border-strong);
  border-radius: 0;
  color: var(--c-primary);
  cursor: grab;
  touch-action: none;
  box-shadow: 2px 0 6px rgba(23, 35, 58, 0.08);
}
.sc-handle:active {
  cursor: grabbing;
}
.sc-handle:disabled {
  cursor: default;
  color: var(--c-ok);
}
.sc-handle:focus-visible {
  outline: 2px solid var(--c-primary);
  outline-offset: -2px;
}
</style>
