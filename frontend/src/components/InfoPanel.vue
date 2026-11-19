<script setup>
/** 右栏快捷报价处理台（拓展栏壳）：注册表驱动视图切换。
 *
 * 头部 = PanelHead（品牌行 + 注册表导航，六态交互）；视图增删只改 panelViews.js。
 * 视觉：汽配红柜台风 —— token 在 .qq 根上局部覆盖，子组件经 CSS 变量级联取色，
 * 工作台主体仍保持工业配价蓝不受影响；.qq 同时是 qqpanel 容器查询锚点，
 * 头部响应式断点随拖拽宽度（1/3 ~ 1/2 视口）生效。
 * 各视图自管数据与轮询；切换即卸载组件，不悬挂请求。
 */
import { computed, ref } from 'vue'
import PanelHead from './right/PanelHead.vue'
import { PANEL_VIEWS } from './right/panelViews.js'

const active = ref(PANEL_VIEWS[0]?.key || '')
const current = computed(() => (PANEL_VIEWS.find((v) => v.key === active.value) || PANEL_VIEWS[0]).comp)
</script>

<template>
  <div class="qq">
    <PanelHead v-model="active" :views="PANEL_VIEWS" />
    <div class="body">
      <component :is="current" />
    </div>
  </div>
</template>

<style scoped>
/* ===== 汽配红柜台 token 局部覆盖：只作用于拓展栏子树 ===== */
.qq {
  --c-bg: #f4f6fa;
  --c-primary: #e82016;
  --c-primary-deep: #c31a0e;
  --c-primary-soft: #fdebea;
  --c-text: #1f2d3d;
  --c-text-sub: #8a97a6;
  --c-border: #eaf1f7;
  --c-border-strong: #d9e2ec;
  --r-sm: 6px;
  --r-md: 8px;
  --r-lg: 12px;

  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--c-panel);
  /* 头部容器查询锚点：断点跟随拖拽宽度而非视口 */
  container: qqpanel / inline-size;
}

/* ===== 视图画布：浅灰蓝 + 顶部淡红晕，卡片由各视图自绘 ===== */
.body {
  flex: 1;
  overflow-y: auto;
  padding: 12px 10px 14px;
  background:
    radial-gradient(420px 180px at 100% -40px, rgba(232, 32, 22, 0.045), transparent 70%),
    var(--c-bg);
}
.body > :deep(*) {
  animation: view-in 0.22s ease both;
}
@keyframes view-in {
  from {
    opacity: 0;
    transform: translateY(4px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}
</style>
