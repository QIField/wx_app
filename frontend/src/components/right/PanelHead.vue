<script setup>
/** 拓展栏头部：品牌行 + 注册表驱动的导航按钮组（六态交互）。
 *
 * 数据：views 来自 panelViews.js 注册表（key/label/icon/badge/disabled），
 * 本组件不感知具体业务视图 —— 新增拓展页无需改动这里。
 * 交互：click/Enter 激活 emit update:modelValue；方向键环绕移焦跳过禁用项
 * （roving tabindex，仅选中项可 Tab）；溢出横向滚动 + 两侧渐隐；
 * badge 红点支持布尔或函数（动态数据）；actions 插槽预留品牌行右侧全局控件位。
 * 响应式：容器由 InfoPanel 的 .qq（container: qqpanel）提供，断点见样式底部。
 */
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { PANEL_META } from './panelViews.js'
import { moveMenuFocus } from './panelNav.js'

const props = defineProps({
  /** 注册表快照：{ key, label, icon?, badge?, disabled?, ... } */
  views: { type: Array, required: true },
  modelValue: { type: String, required: true },
})
const emit = defineEmits(['update:modelValue'])

const isBadged = (v) => (typeof v.badge === 'function' ? !!v.badge() : !!v.badge)

function onActivate(v) {
  if (!v.disabled) emit('update:modelValue', v.key)
}

/* ---------- 键盘导航：在全部按钮表上跑 moveMenuFocus，禁用态交给算法跳过 ---------- */
const menuEl = ref(null)

function onKeydown(e) {
  const els = [...(menuEl.value?.querySelectorAll('.m') || [])]
  const idx = els.indexOf(document.activeElement)
  if (idx < 0) return
  const next = moveMenuFocus(e.key, idx, els.length, (i) => els[i].disabled)
  if (next === idx) return
  e.preventDefault()
  els[next]?.focus()
}

/* ---------- 溢出渐隐：可视区两侧仍有内容时点亮对应遮罩 ---------- */
const canL = ref(false)
const canR = ref(false)
let ro = null

function updateFade() {
  const el = menuEl.value
  if (!el) return
  canL.value = el.scrollLeft > 1
  canR.value = el.scrollLeft + el.clientWidth < el.scrollWidth - 1
}

onMounted(() => {
  updateFade()
  ro = new ResizeObserver(updateFade)
  ro.observe(menuEl.value)
})
onBeforeUnmount(() => ro?.disconnect())
watch(() => props.views.length, () => nextTick(updateFade))
</script>

<template>
  <header class="head">
    <div class="brand">
      <span class="mark" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="13" height="13">
          <path d="M13 2 4.5 13.5H11L9.8 22 19 10h-6.5L13 2z" fill="currentColor" />
        </svg>
      </span>
      <span class="title">{{ PANEL_META.title }}</span>
      <span class="ver num">{{ PANEL_META.version }}</span>
      <!-- 预留：品牌行右侧全局控件位（如模式徽标、更多菜单），新增功能直接挂插槽 -->
      <div class="acts"><slot name="actions" /></div>
    </div>

    <div class="menu-wrap" :class="{ 'can-l': canL, 'can-r': canR }">
      <div
        ref="menuEl"
        class="menu"
        role="tablist"
        :aria-label="`${PANEL_META.title}功能导航`"
        @keydown="onKeydown"
      >
        <button
          v-for="v in views"
          :key="v.key"
          class="m"
          :class="{ on: v.key === modelValue }"
          type="button"
          role="tab"
          :aria-selected="v.key === modelValue"
          :title="v.disabled ? `${v.label}（待后端支持）` : v.label"
          :disabled="v.disabled || undefined"
          :tabindex="v.key === modelValue ? 0 : -1"
          @click="onActivate(v)"
        >
          <svg v-if="v.icon" class="ic" viewBox="0 0 24 24" aria-hidden="true" v-html="v.icon" />
          <span class="lb">{{ v.label }}</span>
          <i v-if="isBadged(v)" class="dot" aria-label="新功能" />
        </button>
      </div>
    </div>
  </header>
</template>

<style scoped>
/* ===== 品牌行：白底 + 红色方块标 + 右上淡红晕提层次 ===== */
.head {
  flex: none;
  padding: 10px 12px;
  background:
    radial-gradient(260px 88px at 100% 0%, rgba(232, 32, 22, 0.05), transparent 72%),
    var(--c-panel);
  border-bottom: 1px solid var(--c-border);
}
.brand {
  display: flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
  margin-bottom: 9px;
}
.mark {
  width: 24px;
  height: 24px;
  flex: none;
  display: grid;
  place-items: center;
  border-radius: 7px;
  background: linear-gradient(145deg, #f2594e, var(--c-primary));
  color: #fff;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.28),
    0 2px 6px rgba(232, 32, 22, 0.3);
}
.title {
  font-weight: 800;
  font-size: 14px;
  letter-spacing: 0.5px;
  color: var(--c-text);
  white-space: nowrap;
}
.ver {
  font: 10px/1 var(--f-num);
  color: var(--c-text-sub);
  background: var(--c-bg);
  padding: 3px 8px;
  border-radius: 999px;
  border: 1px solid var(--c-border);
  white-space: nowrap;
}
.acts {
  margin-left: auto;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 6px;
}
.acts:empty {
  display: none;
}

/* ===== 导航：内凹胶囊槽（docking 感）+ 溢出横向滚动 + 两侧渐隐 ===== */
.menu-wrap {
  position: relative;
  min-width: 0;
}
.menu-wrap::before,
.menu-wrap::after {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  width: 16px;
  z-index: 1;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.15s;
}
.menu-wrap::before {
  left: 0;
  border-radius: 999px 0 0 999px;
  background: linear-gradient(90deg, var(--c-bg), rgba(244, 246, 250, 0));
}
.menu-wrap::after {
  right: 0;
  border-radius: 0 999px 999px 0;
  background: linear-gradient(270deg, var(--c-bg), rgba(244, 246, 250, 0));
}
.menu-wrap.can-l::before {
  opacity: 1;
}
.menu-wrap.can-r::after {
  opacity: 1;
}
.menu {
  display: flex;
  gap: 3px;
  padding: 3px;
  background: var(--c-bg);
  border-radius: 999px;
  box-shadow: inset 0 1px 2px rgba(31, 45, 61, 0.06);
  overflow-x: auto;
  scrollbar-width: none;
}
.menu::-webkit-scrollbar {
  display: none;
}

/* ===== 按钮：六态（default / hover / pressed / selected / focus / disabled） ===== */
.m {
  flex: 1 0 auto; /* 放得下时均分填满；放不下保持自然宽度出滚动 */
  position: relative;
  min-width: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  white-space: nowrap;
  padding: 6px 10px 7px;
  font-size: 12px;
  font-weight: 500;
  color: var(--c-text-sub);
  border-radius: 999px;
  cursor: pointer;
  user-select: none;
  transition:
    color 0.16s,
    background-color 0.16s,
    box-shadow 0.16s,
    transform 0.16s;
}
.m:hover:not(:disabled):not(.on) {
  color: var(--c-primary);
  background: var(--c-panel);
  box-shadow: 0 1px 4px rgba(31, 45, 61, 0.08);
  transform: translateY(-1px);
}
.m:active:not(:disabled) {
  transform: translateY(0) scale(0.96);
  transition-duration: 0.05s;
}
.m.on {
  color: #fff;
  font-weight: 600;
  background: linear-gradient(145deg, #f2594e, var(--c-primary));
  box-shadow:
    0 2px 6px rgba(232, 32, 22, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.25);
}
.m.on:hover:not(:disabled) {
  background: linear-gradient(145deg, #f2594e, var(--c-primary-deep));
}
.m:focus-visible {
  outline: 2px solid rgba(232, 32, 22, 0.4);
  outline-offset: 2px;
}
.m:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.ic {
  width: 14px;
  height: 14px;
  flex: none;
}
/* v-html 注入的 SVG 元素需 :deep 穿透着色（线性 stroke 风格统一） */
.ic:deep(path),
.ic:deep(circle),
.ic:deep(line) {
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.dot {
  position: absolute;
  top: 4px;
  right: 5px;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--c-danger);
  box-shadow: 0 0 0 2px var(--c-panel);
}

/* ===== 响应式：容器查询（面板可拖宽，媒体查询不可靠） =====
   ≥360px 图标+文字；<360px 仅文字；<300px 收紧字号，再窄交给横向滚动渐隐 */
@container qqpanel (max-width: 359px) {
  .ic {
    display: none;
  }
  .m {
    padding: 6px 9px 7px;
  }
}
@container qqpanel (max-width: 299px) {
  .m {
    font-size: 11px;
    padding: 5px 8px 6px;
  }
  .title {
    font-size: 13px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .m,
  .menu-wrap::before,
  .menu-wrap::after {
    transition: none;
  }
}
</style>
