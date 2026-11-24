<script setup>
/** 右侧拓展栏：
 *  - 拖拽调宽：useBoundaryResize.bindEdge 直接绑在可见 edge 元素上（左缘整列），
 *    宽度范围由视口动态决定 [屏宽 * 1/3, 屏宽 * 50%]，localStorage 持久化。
 *  - 收起/展开：独立状态机 + 优雅动画。展开恢复上次宽度，收起缓存宽度。
 *    toggle 按钮贴右缘绝对定位，z-index 高于 InfoPanel 滚动容器，零碰撞。 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useBoundaryResize } from '../composables/useBoundaryResize.js'
import InfoPanel from './InfoPanel.vue'

/* ---------- 宽度动态约束（视口比例） ---------- */
const getMinW = () => Math.floor(window.innerWidth / 3)
const getMaxW = () => Math.floor(window.innerWidth * 0.5)

const { width, isDragging, bindEdge } = useBoundaryResize({
  initial: 316,
  min: getMinW,
  max: getMaxW,
  storageKey: 'wb.infoWidth.v1',
  edgeSide: 'left',
})

/* ---------- 收起/展开 ---------- */
const open = ref(true)
const lastWidth = ref(width.value)
// v-show 而非 v-if：收起/展开只是 CSS 隐藏，InfoPanel 常驻内存，
// 里面 keep-alive 的子组件（ManualView / ThirdParty 等）缓存不丢
const contentMounted = ref(true)
const COLLAPSED_WIDTH = 0
let unmountTimer = null

function toggle() {
  if (open.value) {
    lastWidth.value = width.value
    open.value = false
    clearTimeout(unmountTimer)
    unmountTimer = setTimeout(() => { if (!open.value) contentMounted.value = false }, 320)
  } else {
    clearTimeout(unmountTimer)
    contentMounted.value = true
    width.value = lastWidth.value
    open.value = true
  }
}

/* 内容层宽度：展开态跟随 width（拖拽实时回流）；收起动画期间冻结在 lastWidth（零回流） */
const innerStyle = computed(() => ({
  width: (open.value ? width.value : lastWidth.value) + 'px',
}))

/* 窗口 resize：当前宽度重新 clamp 到 [min, max] */
function onWinResize() {
  const min = getMinW(), max = getMaxW()
  if (open.value) {
    if (width.value > max) width.value = max
    else if (width.value < min) width.value = min
  }
}

const colInfoStyle = computed(() => ({
  width: (open.value ? width.value : COLLAPSED_WIDTH) + 'px',
}))

/* 拖拽触发条：标准模板 ref 拿到 DOM，onMounted 时再绑事件。
 * 注意不能用静态 ref="fn" —— Vue 3 静态字符串 ref 只做赋值不调用函数，
 * 必须走 ref 对象或动态 :ref，否则监听永远不会挂上。 */
const edgeEl = ref(null)
let cleanupEdge = null
onMounted(() => {
  window.addEventListener('resize', onWinResize)
  if (edgeEl.value) cleanupEdge = bindEdge(edgeEl.value)
})
onBeforeUnmount(() => {
  cleanupEdge?.()
  clearTimeout(unmountTimer)
  window.removeEventListener('resize', onWinResize)
})
</script>

<template>
  <aside
    class="col-info"
    :class="{ collapsed: !open, dragging: isDragging }"
    :style="colInfoStyle"
  >
    <!-- 裁剪层：负责圆角裁剪与收起/展开的逐帧揭示；骑缝按钮在它外面不受裁剪 -->
    <div class="col-info-clip">
      <div ref="edgeEl" class="col-info-edge" aria-hidden="true"></div>
      <!-- 内容层：绝对定位右缘锚定，动画期间宽度冻结，零回流 -->
      <!-- v-show 而非 v-if：收起/展开只是 CSS 隐藏，InfoPanel 常驻内存，keep-alive 内的子组件缓存不丢 -->
      <div v-show="contentMounted" class="col-info-inner" :style="innerStyle">
        <InfoPanel />
      </div>
    </div>

    <!-- 收起/展开 toggle：骑缝在面板左缘（聊天区接缝处），彻底避开右侧滚动条 -->
    <button
      class="col-info-toggle"
      :title="open ? '收起拓展栏' : '展开拓展栏'"
      aria-label="切换拓展栏"
      @mousedown.stop
      @click="toggle"
    >
      <svg class="chev" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
        <path d="M9 6l6 6-6 6"/>
      </svg>
    </button>
  </aside>
</template>

<style scoped>
/* ========== 外框 ========== */
.col-info {
  position: relative;
  flex-shrink: 0;
  /* 纯布局盒子：白底/圆角/阴影全部下放给 clip 层承担并统一淡出——
   * 收起末帧宽度趋零时，面板自身不再被挤成一条可见细条（残影根源） */
  overflow: visible;
  /* 丝滑缓动（easeOutQuint 类曲线：快起缓停）；拖拽中由 .dragging 类关闭 */
  transition: width 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}
/* 拖拽中（isDragging 确定性驱动）：关闭宽度过渡，鼠标动多少宽多少，1:1 跟手 */
.col-info.dragging {
  transition: none;
}

/* ========== edge 拖拽触发条 ========== */
.col-info-edge {
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 12px;            /* 显式 edge 覆盖，鼠标按下必命中 */
  z-index: 30;            /* 高于内部滚动容器，低于 toggle(35) */
  cursor: col-resize;
  border-radius: var(--r-md) 0 0 var(--r-md); /* 与面板圆角贴合 */
  background: transparent;
  transition: background 0.16s;
}
.col-info-edge:hover {
  background: linear-gradient(90deg, rgba(29,93,228,0.22), transparent 75%);
}
.col-info.dragging .col-info-edge {
  background: linear-gradient(90deg, rgba(29,93,228,0.36), transparent 75%);
}
/* 收起态 edge 让位给 toggle */
.col-info.collapsed .col-info-edge {
  display: none;
}

/* ========== 裁剪层：面板的全部视觉外观（白底/圆角/阴影）都在这一层 ========== */
/* 收起/展开时整卡统一淡入淡出：宽度趋零之前就已完全透明，
 * 面板盒不可能被挤成可见细条，从物理上杜绝"长条残影" */
.col-info-clip {
  position: absolute;
  left: 0; top: 0; right: 0; bottom: 0;
  overflow: hidden;
  border-radius: var(--r-md);
  background: var(--c-panel);
  box-shadow: var(--shadow-card);
  transition: opacity 0.18s ease-out;
}
.col-info.collapsed .col-info-clip {
  opacity: 0;
}

/* ========== 内容层：绝对定位右缘锚定，动画期间宽度冻结（零回流） ========== */
.col-info-inner {
  position: absolute;
  top: 0; right: 0; bottom: 0;
  overflow: hidden;
  min-width: 0;
  /* 内容的隐去由 clip 层整卡淡出统一负责，自身无需再做透明度过渡 */
  /* 宽度由 innerStyle 绑定：展开=跟随 width，收起动画期间=冻结在 lastWidth */
  /* 给 edge 留出 12px 的点击区，避免被它遮住首列内容 */
  padding-left: 12px;
  box-sizing: border-box;
}

/* ========== toggle 按钮（收起/展开）：骑缝在面板左缘 ========== */
.col-info-toggle {
  position: absolute;
  left: -9px;             /* 骑缝：一半探出面板左缘，落在聊天区接缝上 */
  top: 50%;
  transform: translateY(-50%);
  width: 18px;
  height: 48px;
  z-index: 35;            /* 高于拖拽触发条(30)，按钮区域优先响应点击 */
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 1px solid var(--c-border);
  border-radius: 999px;   /* 胶囊形 */
  background: var(--c-panel);
  color: var(--c-text-sub);
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(23, 35, 58, 0.14);
  transition: color 0.18s, border-color 0.18s, background 0.18s;
}
.col-info-toggle:hover {
  color: var(--c-primary);
  border-color: var(--c-primary);
  background: var(--c-primary-soft);
}
/* 箭头方向：展开态朝右（点击=向右收起），收起态旋转朝左（点击=向左展开） */
.col-info-toggle .chev {
  transition: transform 0.22s;
}
.col-info.collapsed .col-info-toggle .chev {
  transform: rotate(180deg);
}
/* 收起态（面板宽度归零）：按钮整体收进视口内，
 * 否则 left:-9px 会让按钮右缘探出视口 1px，触发文档横向滚动条 */
.col-info.collapsed .col-info-toggle {
  left: -17px;
  transition: left 0.3s cubic-bezier(0.22, 1, 0.36, 1), color 0.18s, border-color 0.18s, background 0.18s;
}
</style>
