<script setup>
/**
 * CustomDatePicker —— 轻量日期选择器（单选）
 * 核心特性：
 *   - 只显示后端返回的"有消息的年月"（years / months）
 *   - 日历网格只高亮"有消息的日期"（availableDates）
 *   - 单选，无 range，无 hover 预览 → 快
 * 数据流：
 *   v-model = 'YYYY-MM-DD' | null
 *   props.years     = [2025, 2026]              // 有消息的年份
 *   props.months    = { 2026: [10, 11], ... }   // 每年有消息的月份
 *   props.dateSet   = Set<string>               // 有消息的日期集合（YYYY-MM-DD）
 */
import { computed, onMounted, onBeforeUnmount, ref, watch, nextTick } from 'vue'
import { useZIndex } from 'element-plus'

const { nextZIndex } = useZIndex()

const props = defineProps({
  modelValue: { type: String, default: null },
  years: { type: Array, default: () => [] },
  monthsByYear: { type: Object, default: () => ({}) },
  dateSet: { type: Object, default: () => new Set() },
})

const emit = defineEmits(['update:modelValue', 'change'])

// ------- 面板状态 -------
const triggerRef = ref(null)
const open = ref(false)
const panelStyle = ref({})
const viewYear = ref(new Date().getFullYear())
const viewMonth = ref(new Date().getMonth() + 1)

const WEEK_LABELS = ['一', '二', '三', '四', '五', '六', '日']
const TODAY = new Date()  // 今天不变，缓存一次

// ------- 计算属性 -------

const effectiveYear = computed(() => {
  if (props.years.includes(viewYear.value)) return viewYear.value
  return props.years[props.years.length - 1] || TODAY.getFullYear()
})

const availableMonths = computed(() => {
  return [...(props.monthsByYear[effectiveYear.value] || [])].sort((a, b) => a - b)
})

const effectiveMonth = computed(() => {
  if (availableMonths.value.includes(viewMonth.value)) return viewMonth.value
  return availableMonths.value[availableMonths.value.length - 1] || (TODAY.getMonth() + 1)
})

/** 6×7 日历网格，null = 占位 */
const grid = computed(() => {
  const y = effectiveYear.value
  const m = effectiveMonth.value
  const firstDay = new Date(y, m - 1, 1)
  const leadingBlank = (firstDay.getDay() + 6) % 7  // JS 0=周日 → 0=周一
  const daysInMonth = new Date(y, m, 0).getDate()

  const cells = Array(leadingBlank).fill(null)
  for (let d = 1; d <= daysInMonth; d++) cells.push(d)
  while (cells.length < 42) cells.push(null)
  return cells
})

/** 每个 cell 的视觉状态 */
function cellState(day) {
  if (day === null) return 'blank'
  const key = `${effectiveYear.value}-${pad(effectiveMonth.value)}-${pad(day)}`
  const hasMsg = props.dateSet.has(key)
  if (!hasMsg) return 'disabled'
  if (props.modelValue === key) return 'selected'
  if (TODAY.getFullYear() === effectiveYear.value
    && TODAY.getMonth() + 1 === effectiveMonth.value
    && TODAY.getDate() === day) return 'today'
  return 'available'
}

function pad(n) { return String(n).padStart(2, '0') }
function formatKey(y, m, d) { return `${y}-${pad(m)}-${pad(d)}` }

// ------- 事件处理 -------

function onYearChange(y) {
  viewYear.value = y
  const months = props.monthsByYear[y] || []
  if (months.length) viewMonth.value = [...months].sort((a, b) => a - b).pop()
}

function onMonthChange(m) { viewMonth.value = m }

function onCellClick(day) {
  if (day === null) return
  const state = cellState(day)
  if (state === 'disabled' || state === 'blank') return
  const key = formatKey(effectiveYear.value, effectiveMonth.value, day)
  emit('update:modelValue', key)
  emit('change', key)
  closePanel()
}

function closePanel() { open.value = false }

function togglePanel() {
  if (open.value) { open.value = false; return }

  open.value = true
  nextTick(() => positionPanel())
}

/** 把面板定位到触发按钮正下方，自动处理边界溢出 */
function positionPanel() {
  const trigger = triggerRef.value
  if (!trigger) return
  const r = trigger.getBoundingClientRect()
  const panelW = 260, panelH = 340
  let left = r.left, top = r.bottom + 4

  if (left + panelW > window.innerWidth - 8) left = window.innerWidth - panelW - 8
  if (top + panelH > window.innerHeight - 8) top = r.top - panelH - 4
  if (left < 8) left = 8
  if (top < 8) top = r.bottom + 4

  panelStyle.value = {
    zIndex: nextZIndex(),
    top: top + 'px',
    left: left + 'px',
  }
}

function clearValue(e) {
  e.stopPropagation()
  emit('update:modelValue', null)
  emit('change', null)
}

// ------- 点外部关闭 -------

function onDocClick(e) {
  if (!open.value) return
  // trigger 在 .cdp-wrap 里，panel 在 body 里（Teleport），都要排除
  if (e.target.closest('.cdp-wrap') || e.target.closest('.cdp-panel')) return
  open.value = false
}
onMounted(() => document.addEventListener('click', onDocClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocClick))

// ------- 同步 modelValue → 面板视图 -------
watch(() => props.modelValue, (v) => {
  if (v && /^\d{4}-\d{2}-\d{2}$/.test(v)) {
    const [y, m] = v.split('-').map(Number)
    if (props.years.includes(y)) viewYear.value = y
    viewMonth.value = m
  }
}, { immediate: true })
</script>

<template>
  <div class="cdp-wrap">
    <!-- 触发按钮 -->
    <button ref="triggerRef" class="cdp-trigger" type="button" :class="{ 'cdp-trigger-open': open }" @click="togglePanel">
      <svg class="cdp-icon" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect x="1.5" y="3" width="13" height="11" rx="2" stroke="currentColor" stroke-width="1.2"/>
        <path d="M4.5 1.5V4M11.5 1.5V4M1.5 6h13" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
        <circle v-for="d in 3" :key="d" :cx="4 + d * 2" cy="9.5" r="0.8" fill="currentColor"/>
      </svg>
      <span v-if="modelValue" class="cdp-value">{{ modelValue }}</span>
      <span v-else class="cdp-placeholder">选择发送日期</span>
      <button v-if="modelValue" class="cdp-clear" type="button" @click="clearValue" title="清除">✕</button>
      <svg class="cdp-caret" :class="{ 'cdp-caret-open': open }" viewBox="0 0 10 6" fill="none">
        <path d="M1 1l4 4 4-4" stroke="currentColor" stroke-width="1.5"/>
      </svg>
    </button>

    <!-- 面板 -->
    <Teleport to="body">
      <transition name="cdp-pop">
        <div v-if="open" class="cdp-panel" :style="panelStyle">
          <!-- 年份 / 月份 下拉 -->
          <div class="cdp-head">
            <select class="cdp-select" :value="effectiveYear" @change="onYearChange(+($event.target.value))">
              <option v-for="y in years" :key="y" :value="y">{{ y }}年</option>
            </select>
            <select class="cdp-select" :value="effectiveMonth" @change="onMonthChange(+($event.target.value))">
              <option v-for="m in availableMonths" :key="m" :value="m">{{ m }}月</option>
            </select>
          </div>

          <!-- 星期 -->
          <div class="cdp-week">
            <div v-for="w in WEEK_LABELS" :key="w" class="cdp-week-cell">{{ w }}</div>
          </div>

          <!-- 日期网格 -->
          <div class="cdp-grid">
            <div
              v-for="(day, i) in grid"
              :key="i"
              class="cdp-cell"
              :class="{
                'cdp-cell-blank': day === null,
                'cdp-cell-disabled': day !== null && cellState(day) === 'disabled',
                'cdp-cell-available': day !== null && (cellState(day) === 'available' || cellState(day) === 'today'),
                'cdp-cell-selected': day !== null && cellState(day) === 'selected',
                'cdp-cell-today': day !== null && cellState(day) === 'today',
              }"
              @click="onCellClick(day)"
            >
              <span v-if="day !== null">{{ day }}</span>
            </div>
          </div>

          <!-- 底部 -->
          <div class="cdp-foot">
            <button class="cdp-btn cdp-btn-ghost" type="button" @click="closePanel">取消</button>
          </div>
        </div>
      </transition>
    </Teleport>
  </div>
</template>

<style scoped>
/* ====== 触发按钮 ====== */
.cdp-wrap { position: relative; display: inline-block; }
.cdp-trigger {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 30px;
  padding: 0 10px;
  border: 1px solid #dbe3ef;
  border-radius: 6px;
  background: #fff;
  font-size: 12px;
  color: #17233a;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
  min-width: 160px;
  box-sizing: border-box;
}
.cdp-trigger:hover { border-color: #1d5de4; }
.cdp-trigger-open { border-color: #1d5de4; box-shadow: 0 0 0 2px rgba(29, 93, 228, 0.15); }

.cdp-icon { width: 14px; height: 14px; color: #8a96ab; flex-shrink: 0; }
.cdp-value { color: #17233a; }
.cdp-placeholder { color: #8a96ab; }
.cdp-clear {
  margin-left: auto;
  width: 18px; height: 18px;
  border-radius: 50%;
  border: none;
  background: transparent;
  color: #8a96ab;
  font-size: 11px;
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
}
.cdp-clear:hover { background: #eef1f7; color: #17233a; }
.cdp-caret { width: 10px; height: 6px; color: #8a96ab; transition: transform 0.15s; flex-shrink: 0; }
.cdp-caret-open { transform: rotate(180deg); }

/* ====== 面板 ====== */
.cdp-panel {
  position: fixed;
  width: 260px;
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 8px 30px rgba(15, 30, 68, 0.18);
  border: 1px solid #e8edf5;
  padding: 14px;
  user-select: none;
}

/* 标题：年 + 月 下拉 */
.cdp-head {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.cdp-select {
  flex: 1;
  height: 30px;
  border: 1px solid #dbe3ef;
  border-radius: 6px;
  padding: 0 8px;
  font-size: 12px;
  color: #17233a;
  background: #fff;
  outline: none;
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath d='M1 1l4 4 4-4' fill='none' stroke='%238a96ab' stroke-width='1.5'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 8px center;
  padding-right: 24px;
}
.cdp-select:focus { border-color: #1d5de4; }

/* 星期 */
.cdp-week {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  margin-bottom: 4px;
}
.cdp-week-cell {
  text-align: center;
  font-size: 11px;
  color: #8a96ab;
  padding: 6px 0;
}

/* 网格 */
.cdp-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 2px;
}
.cdp-cell {
  aspect-ratio: 1 / 1;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: #17233a;
  border-radius: 5px;
  cursor: default;
  transition: background 0.1s, color 0.1s;
}
.cdp-cell-blank { background: transparent; }
.cdp-cell-disabled { color: #c5cddb; cursor: not-allowed; }
.cdp-cell-available { cursor: pointer; }
.cdp-cell-available:hover { background: #eef4ff; color: #1d5de4; }
.cdp-cell-today { border: 1px solid #1d5de4; font-weight: 600; color: #1d5de4; }
.cdp-cell-selected {
  background: #1d5de4;
  color: #fff;
  font-weight: 600;
  cursor: pointer;
}
.cdp-cell-selected:hover { background: #0f3da8; }

/* 底部 */
.cdp-foot {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
  gap: 8px;
}
.cdp-btn {
  height: 28px;
  padding: 0 12px;
  border-radius: 5px;
  font-size: 11px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.15s;
}
.cdp-btn-ghost {
  background: #fff;
  border-color: #dbe3ef;
  color: #6b7a93;
}
.cdp-btn-ghost:hover { border-color: #1d5de4; color: #1d5de4; }

/* ====== 动画 ====== */
.cdp-pop-enter-active, .cdp-pop-leave-active { transition: opacity 0.15s ease, transform 0.15s ease; }
.cdp-pop-enter-from, .cdp-pop-leave-to { opacity: 0; transform: translateY(-4px) scale(0.98); }
</style>
