<script setup>
/** 视图二：手动报价 —— 查询报价 / AI 对话 / 第三方比价 / 采购历史 四子页容器。
 *
 * 查询报价：输入 OE/VIN/名称（可附配件名）→ POST /quote/query/manual-search
 *   后端链式编排（vininfo→partno→product_list→爆炸图）→ QuoteResultCard 展示。
 *   类型识别与原型 detectType 同款；示例 chips 一键查询。
 * 其余三子页为独立组件（ManualAiChat / ManualThirdParty / ManualHistory）。
 */
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { qqManualSearch } from '../../api'
import { TYPE_LABELS, detectType } from '../../utils/quoteQuery'
import QuoteResultCard from './QuoteResultCard.vue'
import ManualAiChat from './ManualAiChat.vue'
import ManualThirdParty from './ManualThirdParty.vue'
import ManualHistory from './ManualHistory.vue'

const SUBS = [
  { key: 'query', label: '查询报价' },
  { key: 'ai', label: 'AI 对话' },
  { key: 'third', label: '第三方比价' },
  { key: 'history', label: '采购历史' },
]

const CHIPS = [
  { label: 'OE 1665000075', q: '1665000075' },
  { label: 'VIN 宝马X3', q: 'WBAWX3100G0L69597' },
  { label: '名称：节温器', q: '节温器' },
  { label: '无效OE演示', q: '0005400017' },
]

const subTab = ref('query')
const q = ref('')
const partName = ref('')
const loading = ref(false)
const result = ref(null)
const error = ref('')

const typeLabel = () => TYPE_LABELS[detectType(q.value)] || ''

async function doQuery(text) {
  const query = (text ?? q.value).trim()
  if (!query) {
    ElMessage.warning('请输入查询内容')
    return
  }
  q.value = query
  loading.value = true
  error.value = ''
  result.value = null
  try {
    result.value = await qqManualSearch(query, partName.value.trim() || undefined)
  } catch (e) {
    error.value = e.message || '查询失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="manual">
    <div class="sub-tabs">
      <span
        v-for="s in SUBS" :key="s.key"
        class="st" :class="{ on: subTab === s.key }"
        @click="subTab = s.key"
      >{{ s.label }}</span>
    </div>

    <template v-if="subTab === 'query'">
      <div class="mq-box">
        <div class="mq-row">
          <input v-model="q" class="input num" placeholder="输入 OE / VIN / 配件名称（如：节温器）" @keyup.enter="doQuery()">
          <button class="btn primary" :disabled="loading" @click="doQuery()">查询</button>
        </div>
        <div class="mq-row sub">
          <input v-model="partName" class="input" placeholder="配件名（VIN 查询时译码用，可留空）" @keyup.enter="doQuery()">
          <span v-if="q.trim()" class="type-hint">识别：{{ typeLabel() }}</span>
        </div>
        <div class="chips">
          <span v-for="c in CHIPS" :key="c.q" class="chip num" @click="doQuery(c.q)">{{ c.label }}</span>
        </div>
      </div>

      <div class="res">
        <div v-if="loading" class="skel"><span class="ring"></span>解析中（识别 → 译码 → CRM → 爆炸图）…</div>
        <div v-else-if="error" class="empty err">
          <span class="badge b-red">查询失败</span>
          <span class="msg">{{ error }}</span>
        </div>
        <QuoteResultCard v-else-if="result" :r="result" />
        <div v-else class="empty">查询结果将在此输出（识别 → 译码 → CRM → 爆炸图）</div>
      </div>
    </template>

    <ManualAiChat v-else-if="subTab === 'ai'" />
    <ManualThirdParty v-else-if="subTab === 'third'" />
    <ManualHistory v-else />
  </div>
</template>

<style scoped>
.sub-tabs { display: flex; gap: 4px; margin-bottom: 8px; }
.sub-tabs .st {
  flex: 1; text-align: center;
  font-size: 11px; padding: 6px 0;
  border-radius: var(--r-md);
  border: 1px solid var(--c-border);
  background: var(--c-panel); color: var(--c-text-sub);
  cursor: pointer; transition: all 0.15s; user-select: none;
}
.sub-tabs .st.on {
  background: var(--c-primary-soft);
  border-color: var(--c-primary); color: var(--c-primary); font-weight: 600;
}

.mq-box {
  border: 1px solid var(--c-border); border-radius: var(--r-md);
  padding: 10px; background: #f9fafd;
}
.mq-row { display: flex; gap: 6px; align-items: center; }
.mq-row.sub { margin-top: 6px; }
.mq-row .input {
  flex: 1; min-width: 0;
  padding: 6px 9px; font-size: 12px;
  border: 1px solid var(--c-border-strong); border-radius: var(--r-md);
  background: var(--c-panel); color: var(--c-text); outline: none; font-family: inherit;
}
.mq-row .input.num { font-family: var(--f-num); }
.mq-row .input:focus { border-color: var(--c-primary); box-shadow: 0 0 0 2px rgba(29, 93, 228, 0.12); }
.mq-row .input::placeholder { color: #9aa7bc; }
.mq-row .input.sub-in { font-size: 11px; }
.type-hint { font-size: 10px; color: var(--c-primary); white-space: nowrap; }

.btn.primary {
  padding: 6px 14px; font-size: 12px; border-radius: var(--r-md);
  border: 1px solid var(--c-primary-deep); color: #fff; font-weight: 600;
  background: linear-gradient(135deg, #2f6ff0, #1d5de4); cursor: pointer;
}
.btn.primary:hover:not(:disabled) { background: linear-gradient(135deg, #3d7bf5, #2a67e8); }
.btn.primary:disabled { opacity: 0.5; cursor: not-allowed; }

.chips { display: flex; gap: 5px; margin-top: 7px; flex-wrap: wrap; }
.chip {
  font-size: 10px; padding: 3px 8px; border-radius: 999px;
  background: var(--c-panel); border: 1px solid var(--c-border-strong);
  color: var(--c-text-sub); cursor: pointer; transition: all 0.15s;
}
.chip:hover { border-color: var(--c-primary); color: var(--c-primary); background: var(--c-primary-soft); }

.res { margin-top: 10px; }
.skel { padding: 14px; text-align: center; color: var(--c-text-sub); font-size: 11px; }
.skel .ring {
  display: inline-block; width: 14px; height: 14px;
  border: 2px solid var(--c-border-strong); border-top-color: var(--c-primary);
  border-radius: 50%; animation: spin 0.7s linear infinite;
  vertical-align: -3px; margin-right: 6px;
}
@keyframes spin { to { transform: rotate(360deg); } }
.empty { padding: 22px 10px; text-align: center; color: var(--c-text-sub); font-size: 11px; }
.empty.err { display: flex; align-items: center; justify-content: center; gap: 8px; }
.empty.err .msg { text-align: left; word-break: break-all; }
.badge.b-red { display: inline-block; padding: 2px 7px; font-size: 10px; border-radius: var(--r-sm); font-weight: 600; background: var(--c-danger-soft); color: var(--c-danger); flex: none; }
</style>
