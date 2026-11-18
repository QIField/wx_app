<script setup>
/** 右栏快捷报价处理台（拓展栏重做）：注册表驱动 4 视图切换壳。
 *
 * 视图（新增拓展页在 VIEWS 加一行即自动入列）：
 *   自动报价（AI 开关 + 新消息触发流）/ 手动报价（查询·AI 对话·比价·历史）
 *   报价分析（日/月 KPI 趋势）/ 设置。
 * 各视图自管数据与轮询；切换即卸载组件，不悬挂请求。
 */
import { computed, ref } from 'vue'
import AutoFeedView from './right/AutoFeedView.vue'
import ManualView from './right/ManualView.vue'
import AnalysisView from './right/AnalysisView.vue'
import SettingsView from './right/SettingsView.vue'

const VIEWS = [
  { key: 'auto', label: '自动报价', comp: AutoFeedView },
  { key: 'manual', label: '手动报价', comp: ManualView },
  { key: 'analysis', label: '报价分析', comp: AnalysisView },
  { key: 'settings', label: '设置', comp: SettingsView },
]

const active = ref('auto')
const current = computed(() => (VIEWS.find((v) => v.key === active.value) || VIEWS[0]).comp)
</script>

<template>
  <div class="qq">
    <div class="head">
      <div class="row1">
        <span class="title">快捷报价</span>
        <span class="ver num">QQ v1.1</span>
      </div>
      <div class="menu-wrap">
        <div class="menu">
          <button
            v-for="v in VIEWS" :key="v.key"
            class="m" :class="{ on: active === v.key }"
            @click="active = v.key"
          >{{ v.label }}</button>
        </div>
      </div>
    </div>
    <div class="body">
      <component :is="current" />
    </div>
  </div>
</template>

<style scoped>
.qq { display: flex; flex-direction: column; height: 100%; }

.head {
  flex: none;
  padding: 10px 12px 0;
  background: linear-gradient(180deg, #f6f8fc, #eef1f8);
  border-bottom: 1px solid var(--c-border);
}
.row1 { display: flex; align-items: center; gap: 8px; padding-bottom: 8px; }
.title { font-weight: 700; font-size: 13px; }
.ver {
  font: 10px/1 var(--f-num); color: var(--c-text-sub);
  background: var(--c-bg); padding: 3px 6px;
  border-radius: var(--r-sm); border: 1px solid var(--c-border);
}

/* 菜单：视图多时横向滚动，两侧渐隐提示（与原型同款） */
.menu-wrap { position: relative; min-width: 0; }
.menu-wrap::before,
.menu-wrap::after {
  content: '';
  position: absolute; top: 0; bottom: 0; width: 16px;
  pointer-events: none; opacity: 0; transition: opacity 0.15s; z-index: 1;
}
.menu-wrap::before { left: 0; background: linear-gradient(90deg, var(--c-panel), rgba(255, 255, 255, 0)); }
.menu-wrap::after { right: 0; background: linear-gradient(270deg, var(--c-panel), rgba(255, 255, 255, 0)); }
.menu { display: flex; gap: 2px; overflow-x: auto; scrollbar-width: none; }
.menu::-webkit-scrollbar { display: none; }

.m {
  flex: 1 0 auto;
  white-space: nowrap; text-align: center;
  padding: 8px 10px 9px;
  font-size: 12px; color: var(--c-text-sub);
  cursor: pointer; user-select: none;
  border-bottom: 2px solid transparent;
  transition: color 0.15s, border-color 0.15s;
}
.m:hover { color: var(--c-text); }
.m.on { color: var(--c-primary); font-weight: 600; border-bottom-color: var(--c-primary); }

.body { flex: 1; overflow-y: auto; padding: 10px 10px 14px; }
.body > :deep(*) { animation: view-in 0.22s ease both; }
@keyframes view-in {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: none; }
}
</style>
