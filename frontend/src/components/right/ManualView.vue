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
      <div class="qq-box">
        <div class="qq-row">
          <input v-model="q" class="qq-input num" placeholder="输入 OE / VIN / 配件名称（如：节温器）" @keyup.enter="doQuery()">
          <button class="qq-btn-primary" :disabled="loading" @click="doQuery()">查询</button>
        </div>
        <div class="qq-row sub">
          <input v-model="partName" class="qq-input" placeholder="配件名（VIN 查询时译码用，可留空）" @keyup.enter="doQuery()">
          <span v-if="q.trim()" class="type-hint">识别：{{ typeLabel() }}</span>
        </div>
        <div class="chips">
          <span v-for="c in CHIPS" :key="c.q" class="chip num" @click="doQuery(c.q)">{{ c.label }}</span>
        </div>
      </div>

      <div class="res">
        <div v-if="loading" class="qq-skel"><span class="ring"></span>解析中（识别 → 译码 → CRM → 爆炸图）…</div>
        <div v-else-if="error" class="qq-empty err">
          <span class="qq-badge b-red">查询失败</span>
          <span class="msg">{{ error }}</span>
        </div>
        <QuoteResultCard v-else-if="result" :r="result" />
        <div v-else class="qq-empty">查询结果将在此输出（识别 → 译码 → CRM → 爆炸图）</div>
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

/* 查询卡后接结果区，间距由 .res 控制，不吃公共 .qq-box 的 margin-bottom */
.qq-box { margin-bottom: 0; }
.type-hint { font-size: 10px; color: var(--c-primary); white-space: nowrap; }

.chips { display: flex; gap: 5px; margin-top: 7px; flex-wrap: wrap; }
.chip {
  font-size: 10px; padding: 3px 8px; border-radius: 999px;
  background: var(--c-panel); border: 1px solid var(--c-border-strong);
  color: var(--c-text-sub); cursor: pointer; transition: all 0.15s;
}
.chip:hover { border-color: var(--c-primary); color: var(--c-primary); background: var(--c-primary-soft); }

.res { margin-top: 10px; }
.qq-empty.err { display: flex; align-items: center; justify-content: center; gap: 8px; }
.qq-empty.err .msg { text-align: left; word-break: break-all; }
.qq-empty.err .qq-badge { flex: none; }
</style>
