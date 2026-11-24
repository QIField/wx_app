<script setup>
/** 视图一：自动报价 —— AI 执行开关 + 报价模式 + 新消息触发流（真实询价 feed）。
 *
 * 数据：GET /quote/inquiries（绑定设备口径，id 倒序）一次拉 200 条，卡片按状态呈现：
 *   pending/review 可操作（展开改价发送/忽略）、sent 只读、ignored/blocked 置灰。
 * 新鲜度：15s 轮询 + WS quote_inquiry_changed 静默刷新；暂停按钮停轮询。
 * 开关/模式：GET /quote/config 回填；PUT 保存失败回滚原值 + toast（客服 403 文案后端给）。
 */
import { computed, onActivated, onDeactivated, onBeforeUnmount, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { connectWs, fetchQuoteInquiries, saveQuoteConfig } from '../../api'
import { useQuoteConfig } from '../../composables/useQuoteConfig'
import QuoteCard from '../QuoteCard.vue'

const POLL_MS = 15000
const FETCH_LIMIT = 200

const { aiOn, mode, load: loadConfigFields } = useQuoteConfig()
const saved = ref({ aiOn: true, mode: 'preview' }) // 最近一次成功落库值（失败回滚基准）

const rows = ref([])
const loading = ref(false)
const loaded = ref(false)
const paused = ref(false)
let timer = null
let sub = null // connectWs 订阅 {ws, stop}，卸载时 stop() 防重连泄漏

const modeCls = computed(() => (!aiOn.value ? 'off' : mode.value === 'auto' ? 'auto' : 'preview'))
const modeTxt = computed(() =>
  !aiOn.value ? '未开启' : mode.value === 'auto' ? '识别成功自动发送' : '仅侧边预览')

async function loadConfig() {
  try {
    await loadConfigFields()
    saved.value = { aiOn: aiOn.value, mode: mode.value }
  } catch { /* 配置拉取失败不打断 feed，开关保持默认值可重试 */ }
}

async function saveConfig(payload) {
  try {
    await saveQuoteConfig(payload)
    saved.value = { aiOn: aiOn.value, mode: mode.value }
    ElMessage.success('报价配置已保存')
  } catch (e) {
    aiOn.value = saved.value.aiOn
    mode.value = saved.value.mode
    ElMessage.error(e.message || '保存失败')
  }
}

async function fetchRows(silent = false) {
  if (!silent) loading.value = true
  try {
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

function onWsEvent(event) {
  if (event === 'quote_inquiry_changed') refresh() // 落库/动作广播 → 静默刷新
}

function startPolling() {
  if (timer) return
  timer = setInterval(() => {
    if (!paused.value) refresh()
  }, POLL_MS)
  sub = connectWs(onWsEvent)
}
function stopPolling() {
  clearInterval(timer)
  timer = null
  if (sub) { sub.stop(); sub = null }
}

// keep-alive 场景：首次激活 / 每次重新激活都要启动
onActivated(() => {
  if (!loaded.value) {
    fetchRows()
    loadConfig()
  }
  startPolling()
})
onDeactivated(stopPolling)
onBeforeUnmount(stopPolling)
</script>

<template>
  <div class="auto">
    <div class="strip">
      <div class="strip-row">
        <span class="lbl">AI 智能识别</span>
        <label class="qq-switch" :title="aiOn ? '已开启' : '已关闭'">
          <input v-model="aiOn" type="checkbox" @change="saveConfig({ ai_enabled: aiOn })">
          <span class="track"></span>
        </label>
        <span class="mode-chip" :class="modeCls">{{ modeTxt }}</span>
      </div>
      <div class="strip-row">
        <span class="sw-label">自动报价模式</span>
        <select v-model="mode" class="mode-sel" @change="saveConfig({ quote_mode: mode })">
          <option value="preview">仅侧边预览</option>
          <option value="auto">识别成功自动发送</option>
        </select>
      </div>
    </div>

    <div class="feed-head">
      <span class="t">新消息触发流</span>
      <span class="live" :class="{ paused: paused }"><i></i>{{ paused ? 'PAUSED' : 'LIVE' }}</span>
      <button class="pause" @click="paused = !paused">{{ paused ? '▶ 继续' : '⏸ 暂停' }}</button>
    </div>

    <div v-loading="loading && !loaded" class="feed">
      <QuoteCard
        v-for="q in rows" :key="q.id"
        :inquiry="q" :class="{ dim: [2, 4].includes(q.status) }"
        @refresh="refresh"
      />
      <div v-if="loaded && !rows.length" class="qq-empty">暂无询价</div>
    </div>
  </div>
</template>

<style scoped>
.auto { display: flex; flex-direction: column; min-height: 100%; }

/* 配置横幅：红软底（参照车车安乘配「推广商城」横幅），两行布局适配窄面板 */
.strip {
  padding: 9px 11px;
  background: var(--c-primary-soft);
  border: 1px solid #f9c7c5;
  border-radius: var(--r-lg);
  margin-bottom: 10px;
  display: flex; flex-direction: column; gap: 8px;
}
.strip-row { display: flex; align-items: center; gap: 8px; min-width: 0; }
.lbl { font-size: 11px; color: var(--c-primary-deep); font-weight: 700; white-space: nowrap; }
.sw-label { font-size: 11px; color: var(--c-text-sub); white-space: nowrap; }
.mode-sel {
  flex: 1; min-width: 0; padding: 4px 6px; font-size: 11px;
  border: 1px solid #f9c7c5; border-radius: var(--r-md);
  background: var(--c-panel); color: var(--c-text); outline: none; font-family: inherit;
  transition: border-color 0.15s;
}
.mode-sel:focus { border-color: var(--c-primary); }

.mode-chip { margin-left: auto; font-size: 11px; padding: 3px 9px; border-radius: 999px; font-weight: 600; white-space: nowrap; }
.mode-chip.preview { background: var(--c-warn-soft); color: var(--c-warn); border: 1px solid rgba(240, 130, 30, 0.35); }
.mode-chip.auto { background: var(--c-ok-soft); color: var(--c-ok); border: 1px solid rgba(24, 160, 88, 0.35); }
.mode-chip.off { background: var(--c-bg); color: var(--c-text-sub); border: 1px solid var(--c-border); }

.feed-head { display: flex; align-items: center; gap: 8px; margin: 2px 0 8px; }
.feed-head .t {
  font-weight: 700; font-size: 12px;
  display: flex; align-items: center; gap: 6px;
}
/* 章节标题红色竖条（车车安乘配卡片标题语言） */
.feed-head .t::before {
  content: ''; width: 3px; height: 12px; flex: none;
  border-radius: 2px;
  background: var(--c-primary);
}
.live { display: inline-flex; align-items: center; gap: 4px; font-size: 10px; color: var(--c-ok); font-family: var(--f-num); }
.live i { width: 6px; height: 6px; border-radius: 50%; background: var(--c-ok); animation: blink 1.2s infinite; }
.live.paused { color: var(--c-text-sub); }
.live.paused i { background: var(--c-border-strong); animation: none; }
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.25; }
}
.pause {
  margin-left: auto; font-size: 11px; padding: 3px 9px;
  border: 1px solid var(--c-border-strong); border-radius: 999px;
  color: var(--c-text-sub); cursor: pointer; background: var(--c-panel);
  transition: all 0.15s;
}
.pause:hover { border-color: var(--c-primary); color: var(--c-primary); background: var(--c-primary-soft); }

/* feed 卡片：白卡浮起，hover 轻抬 */
.feed { display: flex; flex-direction: column; gap: 8px; flex: 1; min-height: 0; }
.feed > :deep(.card) {
  border: 1px solid var(--c-border);
  border-radius: var(--r-lg);
  background: var(--c-panel);
  box-shadow: 0 2px 8px rgba(31, 45, 61, 0.05);
  overflow: hidden;
  transition: box-shadow 0.15s, border-color 0.15s;
}
.feed > :deep(.card:hover) { border-color: var(--c-border-strong); box-shadow: 0 4px 12px rgba(31, 45, 61, 0.08); }
.feed > :deep(.card.dim) { opacity: 0.72; }
.footnote { text-align: center; font-size: 10px; color: var(--c-text-sub); opacity: 0.7; padding: 4px 0 2px; }
</style>
