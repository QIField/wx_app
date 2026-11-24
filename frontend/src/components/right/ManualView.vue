<script setup>
/** 视图二：手动报价 —— 查询报价 / AI 对话 / 第三方比价 / 采购历史 四子页容器。
 *
 * 查询报价：万能输入框，自动识别三种模式 → POST /quote/query/manual-search
 *   1. 多号码（逗号/换行分隔）→ 逐个查询
 *   2. VIN + 空格 + 后缀 → 组合查询（后端按 VIN 译码 + 配件名过滤）
 *   3. 单条 OE/VIN/名称 → 原 detectType 路由
 *   附加能力：📷 图片 VIN 识别（上传 → OCR → 填入框里，不自动查）。
 * 其余三子页为独立组件（ManualAiChat / ManualThirdParty / ManualHistory）。
 */
import { computed, ref, defineComponent } from 'vue'
import { ElMessage } from 'element-plus'
import { qqManualSearch, uploadFile, qqOcrVin } from '../../api'
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

const subTab = ref('query')
const q = ref('')
const loading = ref(false)
const result = ref(null)
const error = ref('')

/* 多号码模式结果：[{q, status:'ok'|'err', data?, msg?}] */
const multiResults = ref([])
/* 图片识别状态 */
const ocrLoading = ref(false)
const ocrError = ref('')
/* 拖拽态 */
const isDragging = ref(false)
/* 隐藏的 file input 引用 */
const fileInputRef = ref(null)

/** 万能输入框解析：单条 / VIN+后缀 / 多号码 自动识别。 */
function parseInput(raw) {
  const text = (raw || '').trim()
  if (!text) return { mode: 'empty' }
  // 多号码：逗号/分号/换行分隔
  const items = text.split(/[,;\n]/).map((s) => s.trim()).filter(Boolean)
  if (items.length > 1) return { mode: 'multi', items }
  const single = items[0]
  // VIN + 后缀组合查询（17 位 VIN + 空格 + 配件名/号码）
  const vinMatch = single.match(/^([A-HJ-NPR-Z0-9]{17})\s+(.+)$/i)
  if (vinMatch) return { mode: 'combo', vin: vinMatch[1], suffix: vinMatch[2].trim() }
  // 单条
  return { mode: 'single', q: single, type: detectType(single) }
}

const parseInfo = computed(() => parseInput(q.value))

const typeLabel = () => {
  const p = parseInfo.value
  if (p.mode === 'combo') return `VIN + 后缀`
  if (p.mode === 'single') return TYPE_LABELS[p.type] || ''
  if (p.mode === 'multi') return `批量 ${p.items.length} 条`
  return ''
}

async function doQuery(text) {
  if (loading.value) return
  q.value = (text ?? q.value).trim()
  const p = parseInput(q.value)
  if (p.mode === 'empty') {
    ElMessage.warning('请输入查询内容')
    return
  }
  error.value = ''
  result.value = null
  multiResults.value = []
  loading.value = true
  try {
    if (p.mode === 'multi') {
      for (const item of p.items) {
        try {
          const data = await qqManualSearch(item)
          multiResults.value.push({ q: item, status: 'ok', data })
        } catch (e) {
          multiResults.value.push({ q: item, status: 'err', msg: e.message || '查询失败' })
        }
      }
    } else if (p.mode === 'combo') {
      result.value = await qqManualSearch(p.vin, p.suffix)
    } else {
      result.value = await qqManualSearch(p.q)
    }
  } catch (e) {
    error.value = e.message || '查询失败'
  } finally {
    loading.value = false
  }
}

/* ---------- 图片识别 ---------- */
function triggerFileInput() {
  fileInputRef.value?.click()
}
async function onFileChange(ev) {
  const file = ev.target.files?.[0]
  if (!file) return
  ev.target.value = '' // 清空以便重复选同一张图
  await handleImageFile(file)
}
async function handleImageFile(file) {
  ocrLoading.value = true
  ocrError.value = ''
  try {
    const up = await uploadFile(file)
    const { vin } = await qqOcrVin(up.url)
    q.value = vin // 只填入，不自动触发查询
  } catch (e) {
    ocrError.value = e.message || '图片识别失败'
  } finally {
    ocrLoading.value = false
  }
}
function onDragOver(ev) {
  ev.preventDefault()
  isDragging.value = true
}
function onDragLeave() {
  isDragging.value = false
}
async function onDrop(ev) {
  ev.preventDefault()
  isDragging.value = false
  const file = ev.dataTransfer?.files?.[0]
  if (file && file.type.startsWith('image/')) {
    await handleImageFile(file)
  } else {
    ocrError.value = '请拖入图片文件'
  }
}

/* ---------- 4 个子页全部用 component :is → keep-alive 统一缓存 ---------- */
const ManualQueryInline = defineComponent({
  name: 'ManualQueryInline',
  components: { QuoteResultCard },
  setup() {
    return {
      q, loading, error, result, multiResults,
      ocrLoading, ocrError, isDragging, fileInputRef,
      typeLabel, parseInfo,
      doQuery, triggerFileInput, onFileChange,
      onDragOver, onDragLeave, onDrop, QuoteResultCard,
    }
  },
  template: `
    <div>
      <div class="qq-box">
        <div class="qq-row">
          <div
            class="qq-input-wrap"
            :class="{ drag: isDragging }"
            @dragover="onDragOver"
            @dragleave="onDragLeave"
            @drop="onDrop"
          >
            <input
              v-model="q"
              class="qq-input num"
              placeholder="输入 OE/VIN/名称，多号码用逗号分隔，或拖入图片识别 VIN"
              @keyup.enter="doQuery()"
            >
          </div>
          <button class="qq-btn-icon" type="button" title="识别图片 VIN"
            :disabled="loading" @click="triggerFileInput()">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
              <circle cx="12" cy="13" r="4"/>
            </svg>
          </button>
          <input
            ref="fileInputRef"
            type="file"
            accept="image/*"
            style="display:none"
            @change="onFileChange"
          >
          <button class="qq-btn-primary" :disabled="loading" @click="doQuery()">查询</button>
        </div>
        <div v-if="ocrLoading || ocrError || (q.trim() && typeLabel())" class="qq-row sub">
          <span v-if="ocrLoading" class="type-hint ocr-loading">📷 图片识别中…</span>
          <span v-else-if="ocrError" class="type-hint ocr-err">{{ ocrError }}</span>
          <span v-else-if="q.trim()" class="type-hint">识别：{{ typeLabel() }}</span>
          <span v-if="parseInfo.mode === 'combo' && q.trim()" class="type-hint">
            VIN={{ parseInfo.vin }} · 后缀={{ parseInfo.suffix }}
          </span>
        </div>
      </div>
      <div class="res">
        <div v-if="loading" class="qq-skel"><span class="ring"></span>解析中（识别 → 译码 → CRM → 爆炸图）…</div>
        <div v-else-if="error" class="qq-empty err">
          <span class="qq-badge b-red">查询失败</span>
          <span class="msg">{{ error }}</span>
        </div>
        <div v-else-if="multiResults.length">
          <div v-for="(m, i) in multiResults" :key="i + ':' + m.q" class="mr-item">
            <div class="mr-head">
              <span class="mr-q">{{ m.q }}</span>
              <span v-if="m.status === 'err'" class="qq-badge b-red">{{ m.msg }}</span>
              <span v-else class="qq-badge b-green">✓</span>
            </div>
            <QuoteResultCard v-if="m.status === 'ok'" :r="m.data" />
          </div>
        </div>
        <QuoteResultCard v-else-if="result" :r="result" />
        <div v-else class="qq-empty">查询结果将在此输出（识别 → 译码 → CRM → 爆炸图）</div>
      </div>
    </div>
  `,
})

const currentSub = computed(() => {
  if (subTab.value === 'query') return ManualQueryInline
  if (subTab.value === 'ai') return ManualAiChat
  if (subTab.value === 'third') return ManualThirdParty
  return ManualHistory
})
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

    <!-- 4 个子页全部在 keep-alive 里，切 tab 不销毁任何一个 -->
    <keep-alive>
      <component :is="currentSub" />
    </keep-alive>
  </div>
</template>

<style scoped>
/* 纵向满高布局：子页贴到面板底部，内部自管滚动 */
.manual { display: flex; flex-direction: column; height: 100%; overflow: hidden; }
.manual > :deep(.ai-chat) { flex: 1 1 auto; }

/* 子 tab：与壳菜单同款分段 pill 组 */
.sub-tabs {
  display: flex; gap: 3px;
  padding: 3px;
  background: var(--c-bg);
  border-radius: 999px;
  margin-bottom: 10px;
}
.sub-tabs .st {
  flex: 1; text-align: center;
  font-size: 11px; padding: 5px 4px 6px;
  border-radius: 999px;
  color: var(--c-text-sub);
  cursor: pointer; transition: all 0.15s; user-select: none;
  white-space: nowrap;
}
.sub-tabs .st:hover { color: var(--c-primary); background: var(--c-panel); }
.sub-tabs .st.on {
  background: linear-gradient(145deg, #f2594e, var(--c-primary));
  color: #fff; font-weight: 600;
  box-shadow: 0 2px 6px rgba(232, 32, 22, 0.28);
}

/* 查询卡后接结果区，间距由 .res 控制，不吃公共 .qq-box 的 margin-bottom
 * 下面所有 .qq-* 都是 ManualQueryInline（defineComponent 内联模板）的 DOM，
 * 没有本 SFC 的 data-v 属性，必须用 :deep() 穿透 scoped */
.manual :deep(.qq-box) { margin-bottom: 0; }
.manual :deep(.type-hint) { font-size: 10px; color: var(--c-primary); white-space: nowrap; }

.manual :deep(.res) { margin-top: 10px; }
.manual :deep(.qq-empty.err) { display: flex; align-items: center; justify-content: center; gap: 8px; }
.manual :deep(.qq-empty.err .msg) { text-align: left; word-break: break-all; }
.manual :deep(.qq-empty.err .qq-badge) { flex: none; }

/* 万能输入框：wrap 自己带边框，吃满 48px 高度 */
.manual :deep(.qq-input-wrap) {
  flex: 1 1 auto;
  display: flex; align-items: center;
  min-height: 48px;
  border: 1px solid var(--c-border-strong);
  border-radius: 8px; background: var(--c-bg);
  transition: border-color 0.15s, box-shadow 0.15s;
}
.manual :deep(.qq-input-wrap:focus-within) { border-color: var(--c-primary); box-shadow: 0 0 0 2px var(--c-primary-soft); }
.manual :deep(.qq-input-wrap.drag) { border-color: var(--c-primary); border-style: dashed; background: var(--c-primary-soft); }
.manual :deep(.qq-input-wrap .qq-input) {
  flex: 1 1 auto; border: none; outline: none; background: transparent;
  padding: 12px 14px; font-size: 12px; line-height: 1.5;
}

/* 图片识别按钮 */
.manual :deep(.qq-btn-icon) {
  min-height: 48px;
  padding: 0 14px;
  border: 1px solid var(--c-border-strong);
  background: var(--c-bg);
  color: var(--c-text-sub);
  border-radius: 8px;
  cursor: pointer;
  display: inline-flex; align-items: center; justify-content: center;
  transition: all 0.15s;
}
.manual :deep(.qq-btn-icon:hover:not(:disabled)) {
  color: var(--c-primary);
  border-color: var(--c-primary);
  background: var(--c-primary-soft);
}
.manual :deep(.qq-btn-icon:disabled) { opacity: 0.5; cursor: not-allowed; }

/* 查询按钮 */
.manual :deep(.qq-btn-primary) {
  min-height: 48px;
  padding: 0 18px;
  font-size: 13px;
  border: none;
  background: linear-gradient(145deg, #f2594e, var(--c-primary));
  color: #fff; font-weight: 600;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
  box-shadow: 0 2px 6px rgba(232, 32, 22, 0.28);
}
.manual :deep(.qq-btn-primary:hover:not(:disabled)) { filter: brightness(1.05); }
.manual :deep(.qq-btn-primary:disabled) { opacity: 0.5; cursor: not-allowed; box-shadow: none; }

/* 行布局：用 stretch 让子项吃满父行高度，别让全局 align-items:center 压瘪 */
.manual :deep(.qq-row) { display: flex; gap: 8px; align-items: stretch; }
.manual :deep(.qq-row.sub) { margin-top: 8px; gap: 10px; align-items: center; flex-wrap: wrap; }

/* OCR 提示状态 */
.manual :deep(.type-hint.ocr-loading) { color: var(--c-primary); }
.manual :deep(.type-hint.ocr-err) { color: #e74c3c; }

/* 多号码结果区 */
.manual :deep(.mr-item) { margin-bottom: 10px; border-top: 1px dashed var(--c-border); padding-top: 8px; }
.manual :deep(.mr-head) { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.manual :deep(.mr-q) { font-size: 12px; color: var(--c-text-sub); font-family: monospace; }
.manual :deep(.qq-badge.b-green) { background: #27ae60; color: #fff; font-size: 10px; padding: 1px 8px; border-radius: 999px; }
.manual :deep(.qq-badge.b-red) { background: #e74c3c; color: #fff; font-size: 10px; padding: 1px 8px; border-radius: 999px; }
</style>
