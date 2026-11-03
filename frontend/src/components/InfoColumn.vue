<script setup>
/** 右侧扩展栏：内嵌报价处理台，左缘可拖拽调宽（260~480px），可整体收起/展开。 */
import { ref } from 'vue'
import InfoPanel from './InfoPanel.vue'

const open = ref(true)
const width = ref(316)

/* 左边缘拖拽调宽：向左拖=变宽 */
let rz = null
function onResizeDown(e) {
  rz = { x: e.clientX, w: width.value }
  window.addEventListener('mousemove', onResizeMove)
  window.addEventListener('mouseup', onResizeUp)
}
function onResizeMove(e) {
  width.value = Math.min(480, Math.max(260, rz.w - (e.clientX - rz.x)))
}
function onResizeUp() {
  window.removeEventListener('mousemove', onResizeMove)
  window.removeEventListener('mouseup', onResizeUp)
  rz = null
}
</script>

<template>
  <aside v-if="open" class="col-info" :style="{ width: width + 'px' }">
    <div class="info-resizer" title="拖拽调整宽度" @mousedown.prevent="onResizeDown"><i></i></div>
    <InfoPanel />
    <button class="info-toggle" title="收起扩展栏" @click="open = false">
      <svg viewBox="0 0 24 24" width="12" height="12">
        <path d="M9 6l6 6-6 6" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </button>
  </aside>
  <button v-else class="info-toggle outside" title="展开扩展栏" @click="open = true">
    <svg viewBox="0 0 24 24" width="12" height="12">
      <path d="M15 6l-6 6 6 6" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
  </button>
</template>

<style scoped>
.col-info {
  position: relative;
  background: var(--c-panel);
  border-radius: var(--r-md);
  box-shadow: var(--shadow-card);
  overflow: visible;
  flex-shrink: 0;
  transition: width 0.12s ease-out;
}

/* 把手与按钮都嵌在右栏内部，不占外面空间 */
.info-resizer {
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 10px;
  z-index: 5;
  cursor: col-resize;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--r-md) 0 0 var(--r-md);
  transition: background 0.15s;
}
.info-resizer i {
  width: 3px; height: 28px;
  border-radius: 2px;
  background: var(--c-border-strong);
  transition: background 0.15s, height 0.15s;
}
.info-resizer:hover { background: #f0f4fb; }
.info-resizer:hover i { background: var(--c-primary); height: 44px; }

.info-toggle {
  position: absolute;
  right: 0; top: 50%;
  transform: translateY(-50%);
  width: 14px; height: 52px;
  z-index: 5;
  border: 1px solid var(--c-border);
  border-right: none;
  border-radius: var(--r-sm) 0 0 var(--r-sm);
  background: var(--c-panel);
  color: var(--c-text-sub);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  transition: all 0.15s;
}
.info-toggle:hover {
  color: var(--c-primary);
  border-color: var(--c-primary);
  background: var(--c-primary-soft);
}
.info-toggle.outside {
  position: static;
  transform: none;
  align-self: stretch;
  height: auto;
  width: 16px;
  border: 1px solid var(--c-border);
  border-radius: var(--r-sm);
  box-shadow: var(--shadow-card);
}
</style>
