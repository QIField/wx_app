<script setup>
/** 视图一：自动报价 —— AI 执行开关 + 报价模式 + 新消息触发流（真实询价 feed）。
 *
 * 数据：GET /quote/inquiries（绑定设备口径，id 倒序）一次拉 200 条，卡片按状态呈现：
 *   pending/review 可操作（展开改价发送/忽略）、sent 只读、ignored/blocked 置灰。
 * 新鲜度：15s 轮询 + WS quote_inquiry_changed 静默刷新；暂停按钮停轮询。
 * 开关/模式：GET /quote/config 回填；PUT 保存失败回滚原值 + toast（客服 403 文案后端给）。
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { connectWs, fetchQuoteConfig, fetchQuoteInquiries, saveQuoteConfig } from '../../api'
import QuoteCard from '../QuoteCard.vue'

const POLL_MS = 15000
const FETCH_LIMIT = 200

const aiOn = ref(true)
const mode = ref('preview')
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
    const cfg = await fetchQuoteConfig()
    aiOn.value = cfg.ai_enabled !== false
    mode.value = cfg.quote_mode || 'preview'
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

onMounted(() => {
  fetchRows()
  loadConfig()
  timer = setInterval(() => {
    if (!paused.value) refresh()
  }, POLL_MS)
  sub = connectWs(onWsEvent)
})
onUnmounted(() => {
  clearInterval(timer)
  if (sub) sub.stop()
})
</script>

<template>
  <div class="auto">
    <div class="strip">
      <span class="lbl">AI 智能识别</span>
      <label class="switch" :title="aiOn ? '已开启：命中询价自动算价' : '已关闭：纯手动普通模式'">
        <input v-model="aiOn" type="checkbox" @change="saveConfig({ ai_enabled: aiOn })">
        <span class="track"></span>
      </label>
      <span class="sep"></span>
      <span class="sw-label">自动报价模式</span>
      <select v-model="mode" class="mode-sel" @change="saveConfig({ quote_mode: mode })">
        <option value="preview">仅侧边预览</option>
        <option value="auto">识别成功自动发送</option>
      </select>
      <span class="mode-chip" :class="modeCls">{{ modeTxt }}</span>
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
      <div v-if="loaded && !rows.length" class="empty">
        监听已开启的好友/群新消息，AI 识别需求后在此输出报价…
      </div>
      <div class="footnote">每 {{ POLL_MS / 1000 }} 秒自动刷新 · 新询价由 AI 守门自动分流</div>
    </div>
  </div>
</template>

<style scoped>
.auto { display: flex; flex-direction: column; min-height: 100%; }

.strip {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 10px;
  background: var(--c-primary-soft);
  border: 1px solid #c7d8ff;
  border-radius: var(--r-md);
  margin-bottom: 10px;
}
.lbl { font-size: 11px; color: var(--c-primary-deep); font-weight: 600; }
.sep { width: 1px; height: 14px; background: #c7d8ff; }
.sw-label { font-size: 11px; color: var(--c-text-sub); margin-left: 2px; }
.mode-sel {
  width: 128px; padding: 4px 6px; font-size: 11px;
  border: 1px solid var(--c-border-strong); border-radius: var(--r-md);
  background: var(--c-panel); color: var(--c-text); outline: none; font-family: inherit;
}
.mode-sel:focus { border-color: var(--c-primary); }

.mode-chip { margin-left: auto; font-size: 11px; padding: 3px 9px; border-radius: 999px; font-weight: 600; white-space: nowrap; }
.mode-chip.preview { background: var(--c-warn-soft); color: var(--c-warn); border: 1px solid rgba(240, 130, 30, 0.35); }
.mode-chip.auto { background: var(--c-ok-soft); color: var(--c-ok); border: 1px solid rgba(24, 160, 88, 0.35); }
.mode-chip.off { background: var(--c-bg); color: var(--c-text-sub); border: 1px solid var(--c-border); }

/* 开关（原型同款 34x18） */
.switch { position: relative; width: 34px; height: 18px; flex: none; cursor: pointer; }
.switch input { display: none; }
.switch .track { position: absolute; inset: 0; border-radius: 999px; background: #c4cddc; transition: background 0.18s; }
.switch .track::after {
  content: ''; position: absolute; top: 2px; left: 2px; width: 14px; height: 14px;
  border-radius: 50%; background: #fff; transition: left 0.18s; box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}
.switch input:checked + .track { background: var(--c-ok); }
.switch input:checked + .track::after { left: 18px; }

.feed-head { display: flex; align-items: center; gap: 8px; margin: 4px 0 8px; }
.feed-head .t { font-weight: 700; font-size: 12px; }
.live { display: inline-flex; align-items: center; gap: 4px; font-size: 10px; color: var(--c-ok); font-family: var(--f-num); }
.live i { width: 6px; height: 6px; border-radius: 50%; background: var(--c-ok); animation: blink 1.2s infinite; }
.live.paused { color: var(--c-text-sub); }
.live.paused i { background: var(--c-border-strong); animation: none; }
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.25; }
}
.pause {
  margin-left: auto; font-size: 11px; padding: 3px 8px;
  border: 1px solid var(--c-border-strong); border-radius: var(--r-sm);
  color: var(--c-text-sub); cursor: pointer; background: var(--c-panel);
  transition: all 0.15s;
}
.pause:hover { border-color: var(--c-primary); color: var(--c-primary); background: var(--c-primary-soft); }

.feed { display: flex; flex-direction: column; gap: 8px; flex: 1; min-height: 0; }
.feed > :deep(.card) {
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
  background: var(--c-panel);
  overflow: hidden;
}
.feed > :deep(.card.dim) { opacity: 0.72; }
.empty { padding: 22px 10px; text-align: center; color: var(--c-text-sub); font-size: 11px; }
.footnote { text-align: center; font-size: 10px; color: var(--c-border-strong); padding: 4px 0 2px; }
</style>
