<script setup>
/** 右栏：报价处理台（阶段 6 前端接入）。
 *
 * 数据源 GET /quote/inquiries（绑定设备口径，id 倒序），15s 轮询保持新鲜，
 * 动作（发送/忽略）由 QuoteCard 处理后 emit refresh 即时刷新。
 * tab 口径：待处理=pending+review（含发送失败转人工）、已报价=sent、已忽略=ignored+blocked。
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { fetchQuoteInquiries } from '../api'
import QuoteCard from './QuoteCard.vue'
import QuoteSettings from './QuoteSettings.vue'

const POLL_MS = 15000
const FETCH_LIMIT = 200 // V1 一次拉前 200 条（id 倒序），前端按状态分 tab

const TABS = [
  { key: 'pending', label: '待处理', statuses: [0, 1] },
  { key: 'sent', label: '已报价', statuses: [3] },
  { key: 'ignored', label: '已忽略', statuses: [2, 4] },
]

const active = ref('pending')
const view = ref('list') // list | settings
const rows = ref([])
const loading = ref(false)
const loaded = ref(false)
let timer = null

const visible = computed(() => {
  const st = TABS.find((t) => t.key === active.value)
  return rows.value.filter((r) => st.statuses.includes(r.status))
})
const count = (key) => {
  const st = TABS.find((t) => t.key === key)
  return rows.value.filter((r) => st.statuses.includes(r.status)).length
}

async function fetchRows(silent = false) {
  if (!silent) loading.value = true
  try {
    // 出参为分页对象 {total, page, limit, list}，询价行在 list 里
    const res = await fetchQuoteInquiries({ limit: FETCH_LIMIT })
    rows.value = res?.list || []
    loaded.value = true
  } catch {
    /* 轮询失败不打断页面，下个周期再试 */
  } finally {
    loading.value = false
  }
}

function refresh() {
  fetchRows(true)
}

onMounted(() => {
  fetchRows()
  timer = setInterval(refresh, POLL_MS)
})
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <div class="desk">
    <div class="tabs">
      <span class="tab on">报价</span>
      <span class="tab dim">聊天管理</span>
      <span class="tab dim">客户画像</span>
    </div>

    <div class="filter-row">
      <template v-if="view === 'list'">
        <div class="status-tabs">
          <span
            v-for="t in TABS" :key="t.key"
            class="st" :class="{ on: active === t.key }"
            @click="active = t.key"
          >{{ t.label }} <em class="num">{{ count(t.key) }}</em></span>
        </div>
        <button class="gear" title="报价设置" @click="view = 'settings'">
          <svg viewBox="0 0 24 24" width="13" height="13">
            <path d="M12 15.5A3.5 3.5 0 1 0 12 8.5a3.5 3.5 0 0 0 0 7zm7.4-2.6l1.8 1.1-1.5 2.6-2-.7a7 7 0 0 1-1.6 1l-.4 2.1h-3l-.4-2.1a7 7 0 0 1-1.6-1l-2 .7-1.5-2.6 1.8-1.1a7 7 0 0 1 0-1.8L4.2 9.8l1.5-2.6 2 .7a7 7 0 0 1 1.6-1l.4-2.1h3l.4 2.1a7 7 0 0 1 1.6 1l2-.7 1.5 2.6-1.8 1.1a7 7 0 0 1 0 1.8z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>
          </svg>
        </button>
      </template>
      <template v-else>
        <span class="set-back" @click="view = 'list'">
          <svg viewBox="0 0 24 24" width="12" height="12">
            <path d="M15 6l-6 6 6 6" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          返回列表
        </span>
        <span class="set-title">报价设置</span>
      </template>
    </div>

    <el-scrollbar v-if="view === 'list'" class="scroll" v-loading="loading && !loaded">
      <div v-if="visible.length" class="cards">
        <QuoteCard
          v-for="(q, i) in visible" :key="q.id"
          :inquiry="q" :style="{ animationDelay: i * 45 + 'ms' }"
          @refresh="refresh"
        />
      </div>
      <div v-else-if="loaded" class="empty">暂无{{ TABS.find(t => t.key === active).label }}询价</div>
      <div class="footnote">每 {{ POLL_MS / 1000 }} 秒自动刷新 · 新询价由 AI 守门自动分流</div>
    </el-scrollbar>

    <el-scrollbar v-else class="scroll">
      <QuoteSettings />
    </el-scrollbar>
  </div>
</template>

<style scoped>
.desk { display: flex; flex-direction: column; height: 100%; }

.tabs {
  display: flex; gap: 2px; padding: 8px 10px 0;
  border-bottom: 1px solid var(--c-border);
}
.tab {
  padding: 6px 10px; font-size: 13px; cursor: pointer;
  border-radius: var(--r-sm) var(--r-sm) 0 0;
}
.tab.on {
  font-weight: 600; color: var(--c-primary);
  background: var(--c-primary-soft);
  box-shadow: inset 0 2px 0 var(--c-primary);
}
.tab.dim { color: var(--c-text-sub); }
.tab.dim:hover { color: var(--c-text); }

.filter-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 7px 10px;
  border-bottom: 1px solid var(--c-border);
  background: #fafbfd;
}
.status-tabs { display: flex; gap: 4px; }
.st {
  font-size: 12px; color: var(--c-text-sub);
  padding: 3px 9px; border-radius: 3px; cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.15s;
}
.st:hover { color: var(--c-text); }
.st.on {
  color: var(--c-primary); font-weight: 600;
  background: var(--c-primary-soft);
  border-color: #b9d0ff;
}
.st em { font-style: normal; font-size: 11px; opacity: 0.75; margin-left: 1px; }

.gear {
  border: none; background: none; padding: 3px;
  color: var(--c-text-sub); cursor: pointer;
  display: flex; align-items: center;
  border-radius: var(--r-sm);
}
.gear:hover { color: var(--c-primary); background: var(--c-primary-soft); }

.set-back {
  display: flex; align-items: center; gap: 3px;
  font-size: 12px; color: var(--c-primary); cursor: pointer;
}
.set-back:hover { text-decoration: underline; }
.set-title { font-size: 12px; font-weight: 600; color: var(--c-text); }

.scroll { flex: 1; }
.cards { padding: 4px 10px; }

.empty {
  text-align: center; font-size: 12px; color: var(--c-text-sub);
  padding: 40px 0 20px;
}
.footnote {
  text-align: center; font-size: 10px; color: var(--c-border-strong);
  padding: 8px 0 10px;
}
</style>
