<script setup>
/** 右栏快捷报价处理台（拓展栏重做）：注册表驱动 4 视图切换壳。
 *
 * 视觉：汽配红柜台风（参照车车安乘配后台）——token 在 .qq 根上局部覆盖，
 * 子组件经 CSS 变量级联自动换色，工作台主体仍保持工业配价蓝不受影响。
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
      <div class="brand">
        <span class="mark">
          <svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true">
            <path d="M13 2 4.5 13.5H11L9.8 22 19 10h-6.5L13 2z" fill="currentColor"/>
          </svg>
        </span>
        <span class="title">快捷报价</span>
        <span class="ver num">v1.1</span>
      </div>
      <div class="menu" role="tablist">
        <button
          v-for="v in VIEWS" :key="v.key"
          class="m" :class="{ on: active === v.key }"
          role="tab" :aria-selected="active === v.key"
          @click="active = v.key"
        >{{ v.label }}</button>
      </div>
    </div>
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

  display: flex; flex-direction: column; height: 100%;
  background: var(--c-panel);
}

/* ===== 品牌头：白底 + 红色方块标 + DIN 版本胶囊 ===== */
.head {
  flex: none;
  padding: 10px 12px 9px;
  background: var(--c-panel);
  border-bottom: 1px solid var(--c-border);
}
.brand { display: flex; align-items: center; gap: 7px; margin-bottom: 9px; }
.mark {
  width: 22px; height: 22px; flex: none;
  display: grid; place-items: center;
  border-radius: 7px;
  background: linear-gradient(145deg, #f2594e, var(--c-primary));
  color: #fff;
  box-shadow: 0 2px 5px rgba(232, 32, 22, 0.32);
}
.title { font-weight: 800; font-size: 14px; letter-spacing: 0.5px; color: var(--c-text); }
.ver {
  font: 10px/1 var(--f-num);
  color: var(--c-text-sub);
  background: var(--c-bg);
  padding: 3px 8px;
  border-radius: 999px;
  border: 1px solid var(--c-border);
}

/* ===== 分段式 pill 菜单：贴合一行的紧凑 padding，极窄时允许换行 ===== */
.menu {
  display: flex; flex-wrap: wrap; gap: 3px;
  padding: 3px;
  background: var(--c-bg);
  border-radius: 999px;
}
.m {
  flex: 1 0 auto;
  white-space: nowrap; text-align: center;
  padding: 6px 8px 7px;
  font-size: 12px; color: var(--c-text-sub);
  border-radius: 999px;
  cursor: pointer; user-select: none;
  transition: color 0.15s, background 0.15s, box-shadow 0.15s;
}
.m:hover { color: var(--c-primary); background: var(--c-panel); }
.m.on {
  color: #fff; font-weight: 600;
  background: linear-gradient(145deg, #f2594e, var(--c-primary));
  box-shadow: 0 2px 6px rgba(232, 32, 22, 0.3);
}

/* ===== 视图画布：浅灰蓝 + 顶部淡红晕，卡片由各视图自绘 ===== */
.body {
  flex: 1; overflow-y: auto;
  padding: 12px 10px 14px;
  background:
    radial-gradient(420px 180px at 100% -40px, rgba(232, 32, 22, 0.045), transparent 70%),
    var(--c-bg);
}
.body > :deep(*) { animation: view-in 0.22s ease both; }
@keyframes view-in {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: none; }
}
</style>
