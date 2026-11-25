<script setup>
/** 自动报价 Feed —— 重构版（按 prototype-quote-panel.html 设计稿）。
 *
 * 顶栏：AI 自动报价开关 + 今日统计 + 筛选 chips。
 * 列表：纯分隔线列表，QuoteCard 单卡承载 VIN/OE 双行收起 + 3 种展开模板。
 * 数据：GET /quote/inquiries + 15s 轮询 + WS quote_inquiry_changed 静默刷新。
 */
import { computed, onActivated, onDeactivated, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { connectWs, fetchQuoteInquiries, saveQuoteConfig } from '../../api'
import { useQuoteConfig } from '../../composables/useQuoteConfig'
import { useChatStore } from '../../stores/chat'
import QuoteCard from '../QuoteCard.vue'

const POLL_MS = 15000
const FETCH_LIMIT = 200

const chat = useChatStore()
const { aiOn, mode, load: loadConfigFields } = useQuoteConfig()
const saved = ref({ aiOn: true, mode: 'preview' })

const rows = ref([])
const loading = ref(false)
const loaded = ref(false)
const paused = ref(false)
let timer = null
let sub = null

/* ---------- 筛选状态 ---------- */
const filter = ref('all')
const FILTER_CHIPS = [
  { key: 'all',       label: '全部' },
  { key: 'quoted',    label: '已报价' },
  { key: 'pending',   label: '待处理' },
  { key: 'normal',    label: '正常询价' },
  { key: 'abnormal',  label: '异常询价' },
]

/* ---------- 统计（本地 count，不用新 API） ---------- */
const stats = computed(() => ({
  total:  rows.value.length,
  quoted: rows.value.filter(r => r.status === 3).length,
  pending: rows.value.filter(r => [0, 1].includes(r.status)).length,
}))

/* ---------- 过滤 ---------- */
const filteredRows = computed(() => {
  const list = rows.value
  const hasError = r => !!(r.price_json && r.price_json.error)
  switch (filter.value) {
    case 'quoted':   return list.filter(r => r.status === 3)
    case 'pending':  return list.filter(r => [0, 1].includes(r.status))
    case 'normal':   return list.filter(r => !hasError(r) && r.status !== 4)
    case 'abnormal': return list.filter(r => hasError(r) || r.status === 4)
    default: return list
  }
})

/* ---------- 配置读写（保留原有逻辑） ---------- */
async function loadConfig() {
  try {
    await loadConfigFields(null, chat.activeOpenid)
    saved.value = { aiOn: aiOn.value, mode: mode.value }
  } catch { /* 不打断 */ }
}
async function saveConfig(payload) {
  try {
    await saveQuoteConfig(payload, chat.activeOpenid)
    saved.value = { aiOn: aiOn.value, mode: mode.value }
    ElMessage.success('报价配置已保存')
  } catch (e) {
    aiOn.value = saved.value.aiOn
    mode.value = saved.value.mode
    ElMessage.error(e.message || '保存失败')
  }
}

/* ---------- 拉取 + 轮询 + WS ---------- */
async function fetchRows(silent = false) {
  if (!silent) loading.value = true
  try {
    const res = await fetchQuoteInquiries({ limit: FETCH_LIMIT, openid: chat.activeOpenid })
    rows.value = res?.list || []
    loaded.value = true
  } catch { /* 不打断 */ }
  finally { loading.value = false }
}
function refresh() { fetchRows(true) }
function onOpenDetail(id) {
  window.open(`/quote-detail/${id}`, '_blank')
}
function onWsEvent(event) {
  if (event === 'quote_inquiry_changed') refresh()
}
function startPolling() {
  if (timer) return
  timer = setInterval(() => { if (!paused.value) refresh() }, POLL_MS)
  sub = connectWs(onWsEvent)
}
function stopPolling() {
  clearInterval(timer); timer = null
  if (sub) { sub.stop(); sub = null }
}
onActivated(() => {
  if (!loaded.value) { fetchRows(); loadConfig() }
  startPolling()
})
onDeactivated(stopPolling)
onBeforeUnmount(stopPolling)

/* ---------- 设备切换联动：activeOpenid 变了 → 清缓存、重拉询价列表 + 配置 ---------- */
watch(() => chat.activeOpenid, () => {
  rows.value = []       // 清空旧设备缓存，避免串数据
  loaded.value = false  // 重置首次加载标记（让 onActivated 也能走 fetch）
  fetchRows()
  loadConfig()
})
</script>

<template>
  <div class="feed">

    <!-- ======== 顶栏：AI 开关 + 今日统计 ======== -->
    <div class="sub">
      <div class="ai-switch">
        <span class="dot"></span>
        AI 自动报价
        <label class="sw" :title="aiOn ? '已开启' : '已关闭'">
          <input v-model="aiOn" type="checkbox" @change="saveConfig({ ai_enabled: aiOn })">
          <span class="track"><span class="knob"></span></span>
        </label>
      </div>
      <div class="stats">
        今日 <span class="n t">{{ stats.total }}</span>
        <span class="s">·</span>
        已报价 <span class="n g">{{ stats.quoted }}</span>
        <span class="s">·</span>
        待处理 <span class="n a">{{ stats.pending }}</span>
      </div>
    </div>

    <!-- ======== 筛选 chips ======== -->
    <div class="filter">
      <button
        v-for="c in FILTER_CHIPS" :key="c.key"
        class="chip" :class="{ active: filter === c.key }"
        @click="filter = c.key"
      >{{ c.label }}</button>
    </div>

    <!-- ======== 列表 ======== -->
    <ul v-loading="loading && !loaded" class="list">
      <QuoteCard
        v-for="q in filteredRows" :key="q.id"
        :inquiry="q"
        @refresh="refresh"
        @open-detail="onOpenDetail"
      />
      <li v-if="loaded && !filteredRows.length" class="empty">
        {{ rows.length ? '当前筛选下暂无询价' : '暂无询价' }}
      </li>
    </ul>

  </div>
</template>

<style scoped>
/* ======== 顶栏 ======== */
.feed {
  display: flex; flex-direction: column; min-height: 0;
  background: var(--c-panel);
}

.sub {
  display: flex; align-items: center; justify-content: space-between;
  padding: 9px 16px;
  border-bottom: 1px solid #EEF0F3;
  flex-shrink: 0;
}
.ai-switch { display: flex; align-items: center; gap: 7px; font-size: 12px; color: var(--c-text-sub); }
.ai-switch .dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--c-ok);
  box-shadow: 0 0 0 3px rgba(23,156,82,0.12);
}
.sw { cursor: pointer; }
.sw input { display: none; }
.sw .track {
  display: inline-block; width: 30px; height: 16px;
  background: #D5D8DD; border-radius: 10px;
  position: relative; transition: background 0.15s;
  vertical-align: middle;
}
.sw input:checked + .track { background: #3370FF; }
.sw .knob {
  position: absolute; top: 2px; left: 2px;
  width: 12px; height: 12px; background: #fff; border-radius: 50%;
  box-shadow: 0 1px 2px rgba(0,0,0,0.12); transition: transform 0.15s;
}
.sw input:checked + .track .knob { transform: translateX(14px); }

.stats { font-size: 11.5px; color: var(--c-text-muted); display: flex; gap: 4px; }
.stats .n { font-weight: 600; font-variant-numeric: tabular-nums; }
.stats .n.t { color: var(--c-text); }
.stats .n.g { color: var(--c-ok); }
.stats .n.a { color: var(--c-warn); }
.stats .s { color: var(--c-text-muted); margin: 0 1px; }

/* ======== 筛选 ======== */
.filter {
  display: flex; gap: 4px; padding: 8px 16px;
  border-bottom: 1px solid #EEF0F3;
  flex-shrink: 0; overflow-x: auto;
}
.filter::-webkit-scrollbar { display: none; }
.chip {
  flex-shrink: 0; font-size: 11px; padding: 3px 10px; border-radius: 10px;
  background: transparent; color: var(--c-text-sub);
  border: 1px solid transparent; cursor: pointer;
  font-family: inherit; font-weight: 500; transition: all 0.15s;
}
.chip:hover { background: var(--c-bg); color: var(--c-text); }
.chip.active { background: #EAF0FB; color: #3370FF; }

/* ======== 列表 ======== */
.list { flex: 1; min-height: 0; overflow-y: auto; list-style: none; margin: 0; padding: 0; }
.list::-webkit-scrollbar { width: 4px; }
.list::-webkit-scrollbar-thumb { background: #EEF0F3; border-radius: 4px; }

.empty {
  padding: 40px 0; text-align: center;
  font-size: 12px; color: var(--c-text-muted);
}
</style>
