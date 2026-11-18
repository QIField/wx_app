<script setup>
/** 报价设置页：报价模式 / AI 执行开关 / 等级价格系数 / 配件黑名单（global 行）。
 *
 * 读 GET /quote/config，保存 PUT /quote/config（仅 admin/developer 可写，
 * 客服保存 403 → toast 后端文案）。黑名单一行一个配件，前端预校验后端同款规则。
 */
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchQuoteConfig, saveQuoteConfig } from '../api'

const MAX_BLACKLIST = 20
const MAX_PART_LEN = 20

const loading = ref(true)
const saving = ref(false)
const quoteMode = ref('preview')
const aiEnabled = ref(true)
const rates = ref({ vip_a: '', vip_b: '', normal: '' })
const blacklistText = ref('')

const RATE_LABELS = [
  { key: 'vip_a', label: 'VIP-A 系数' },
  { key: 'vip_b', label: 'VIP-B 系数' },
  { key: 'normal', label: '普通客户系数' },
]

onMounted(async () => {
  try {
    const cfg = await fetchQuoteConfig()
    quoteMode.value = cfg.quote_mode || 'preview'
    aiEnabled.value = cfg.ai_enabled !== false
    rates.value = {
      vip_a: cfg.price_map?.vip_a ?? '0.75',
      vip_b: cfg.price_map?.vip_b ?? '0.82',
      normal: cfg.price_map?.normal ?? '0.90',
    }
    blacklistText.value = (cfg.parts_blacklist || []).join('\n')
  } catch (e) {
    ElMessage.error(e.message || '配置加载失败')
  } finally {
    loading.value = false
  }
})

function validate() {
  for (const { key, label } of RATE_LABELS) {
    const v = Number(rates.value[key])
    if (!(v > 0 && v <= 1)) return `${label}必须在 (0, 1] 区间`
  }
  const parts = blacklistLines()
  if (parts.length > MAX_BLACKLIST) return `黑名单最多 ${MAX_BLACKLIST} 个配件`
  if (parts.some((t) => t.length > MAX_PART_LEN)) return `单个配件不能超过 ${MAX_PART_LEN} 字`
  return ''
}

function blacklistLines() {
  return blacklistText.value
    .split('\n')
    .map((t) => t.trim())
    .filter((t) => t)
}

async function onSave() {
  const err = validate()
  if (err) {
    ElMessage.warning(err)
    return
  }
  saving.value = true
  try {
    await saveQuoteConfig({
      quote_mode: quoteMode.value,
      ai_enabled: aiEnabled.value,
      price_map: {
        vip_a: Number(rates.value.vip_a).toFixed(2),
        vip_b: Number(rates.value.vip_b).toFixed(2),
        normal: Number(rates.value.normal).toFixed(2),
      },
      parts_blacklist: blacklistLines(),
    })
    ElMessage.success('报价配置已保存')
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div v-loading="loading" class="settings">
    <div class="set-block">
      <div class="set-title">报价模式</div>
      <label class="radio-row" :class="{ on: quoteMode === 'preview' }">
        <input v-model="quoteMode" type="radio" value="preview">
        <b>仅预览</b>
        <span>算价结果只进本处理台，人工确认后发送</span>
      </label>
      <label class="radio-row" :class="{ on: quoteMode === 'auto' }">
        <input v-model="quoteMode" type="radio" value="auto">
        <b>自动发送</b>
        <span>算价完成即自动发产品图+话术给客户</span>
      </label>
    </div>

    <div class="set-block">
      <div class="set-title">AI 执行开关</div>
      <label class="switch-row">
        <el-switch v-model="aiEnabled" />
        <span>{{ aiEnabled ? '已开启：命中询价自动算价' : '已关闭：纯手动普通模式' }}</span>
      </label>
    </div>

    <div class="set-block">
      <div class="set-title">等级价格系数<span class="hint">报价 = 成本 × 系数</span></div>
      <div v-for="r in RATE_LABELS" :key="r.key" class="rate-row">
        <span class="rate-label">{{ r.label }}</span>
        <input v-model="rates[r.key]" class="rate-input" type="number" min="0" max="1" step="0.01">
      </div>
    </div>

    <div class="set-block">
      <div class="set-title">配件黑名单<span class="hint">一行一个，最多 {{ MAX_BLACKLIST }} 个，单个 ≤ {{ MAX_PART_LEN }} 字</span></div>
      <textarea
        v-model="blacklistText" class="bl-text" rows="5"
        placeholder="命中的配件不报价不自动发送，直接转人工"
      ></textarea>
    </div>

    <button class="save-btn" :disabled="saving" @click="onSave">保存设置</button>
  </div>
</template>

<style scoped>
.settings { padding: 10px 12px 14px; display: flex; flex-direction: column; gap: 12px; }
.set-block {
  border: 1px solid var(--c-border); border-radius: var(--r-sm);
  padding: 8px 10px;
}
.set-title {
  font-size: 12px; font-weight: 600; margin-bottom: 6px;
  display: flex; justify-content: space-between; align-items: baseline;
}
.hint { font-size: 10px; font-weight: 400; color: var(--c-text-sub); }

.radio-row {
  display: grid; grid-template-columns: auto auto 1fr; align-items: baseline; gap: 5px;
  font-size: 12px; padding: 5px 6px; border-radius: var(--r-sm); cursor: pointer;
}
.radio-row span { color: var(--c-text-sub); font-size: 11px; }
.radio-row.on { background: var(--c-primary-soft); }
.radio-row.on b { color: var(--c-primary); }

.switch-row {
  display: flex; align-items: center; gap: 8px;
  font-size: 12px; color: var(--c-text-sub); cursor: pointer;
}

.rate-row { display: flex; align-items: center; gap: 8px; padding: 3px 0; }
.rate-label { font-size: 12px; color: var(--c-text-sub); width: 90px; flex-shrink: 0; }
.rate-input {
  width: 80px; font-size: 12px; padding: 4px 8px;
  border: 1px solid var(--c-border); border-radius: var(--r-sm); outline: none;
}
.rate-input:focus { border-color: var(--c-primary); }

.bl-text {
  width: 100%; box-sizing: border-box;
  font-size: 12px; line-height: 1.6; font-family: inherit;
  color: var(--c-text); background: #fafbfd;
  border: 1px solid var(--c-border); border-radius: var(--r-sm);
  padding: 6px 8px; resize: vertical;
}
.bl-text:focus { outline: none; border-color: var(--c-primary); }

.save-btn {
  font-size: 13px; font-weight: 600; padding: 7px 0;
  border: none; border-radius: var(--r-sm);
  background: var(--c-primary); color: #fff; cursor: pointer;
}
.save-btn:hover:not(:disabled) { filter: brightness(1.08); }
.save-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
