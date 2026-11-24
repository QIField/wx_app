<script setup>
/** 报价处理台单卡 —— 拓展栏简化版。
 *
 * 折叠态：群名 + 状态 chip + 车型 + 时间 + 最终价/配件名
 * 展开态：紧凑摘要卡（车型·VIN·询价概要·配件预览）+ 快捷动作区
 *   - 打开详情页报价：emit('open-detail', inquiry.id)
 *   - 定位聊天气泡：切会话 → 按 inquiry_time 找最近消息 → scrollIntoView
 * 改价/发送/忽略/复制话术全部保留。
 *
 * 数据结构同前（契约 A，price_json），动作走 /quote/inquiries/{id}/send|ignore。
 */
import { computed, inject, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useChatStore } from '../stores/chat.js'
import { ignoreQuoteInquiry, sendQuoteInquiry } from '../api'

const props = defineProps({ inquiry: { type: Object, required: true } })
const emit = defineEmits(['refresh', 'open-detail'])

const chat = useChatStore()
const chatPanelRef = inject('chatPanelRef', null)
const expanded = ref(false)
const priceInput = ref('')
const busy = ref(false)

const r = computed(() => props.inquiry.price_json || {})
const car = computed(() => r.value.car)
const items = computed(() => (r.value.pricing || {}).items || [])
const product = computed(() => r.value.product)
const quoteText = computed(() => ((r.value.pricing || {}).text || '').trim())

/** 可动作状态：待报价/待人工；已报价只读、已忽略已拦截只读。 */
const actionable = computed(() => [0, 1].includes(props.inquiry.status))

const carLine = computed(() => {
  const c = car.value
  if (!c) return props.inquiry.part_name || '（未识别车型）'
  const head = [c.brandName, c.model].filter(Boolean).join(' ')
  const tail = [c.yearPattern ? `${c.yearPattern}款` : '', c.displacement, c.fuel].filter(Boolean).join(' ')
  return tail ? `${head} ${tail}` : head
})

/** 配件缩略图预览（最多展示 2 个） */
const itemPreviews = computed(() =>
  items.value.slice(0, 2).map(it => ({
    image: it.product?.image || product.value?.image,
    name: it.product?.product_name || it.part || it.oe,
    price: it.final_price || it.cost_price,
    oe: it.oe,
  }))
)

/** VIN 后 6 位（省略展示） */
const vinShort = computed(() => {
  const v = car.value?.vin
  if (!v) return ''
  return v.length > 6 ? '···' + v.slice(-6) : v
})

const timeText = computed(() =>
  props.inquiry.sent_at || props.inquiry.inquiry_time || props.inquiry.created_at || '')

/* ---------- 核心动作 ---------- */

/** 打开详情页报价：新开标签页 /#/quote-detail/:id */
function onOpenDetail() {
  const url = `${location.origin}${location.pathname}#/quote-detail/${props.inquiry.id}`
  window.open(url, '_blank', 'noopener')
}

/** 定位聊天气泡：委托 ChatPanel.locateMessage（已内置 ensureOpened + loadOlderMessages + highlight）。
 *  入参：{ convId, id } —— ChatPanel.onHistoryLocate 的标准签名。 */
async function onJumpToBubble() {
  const { conversation_id: convId, message_id: msgId } = props.inquiry
  if (!convId) { ElMessage.warning('该询价未关联会话'); return }
  if (!chatPanelRef.value?.locateMessage) {
    ElMessage.error('聊天面板未就绪，请稍候再试'); return
  }
  if (!msgId) {
    ElMessage.warning('该询价暂无关联消息，将打开会话定位到最新');
  }
  try {
    await chatPanelRef.value.locateMessage({ convId, id: msgId || 0 })
    if (msgId) ElMessage.success('已定位到询价消息')
  } catch (e) {
    ElMessage.error('定位失败：' + (e.message || '未知原因'))
  }
}

/* ---------- 报价 & 发送 ---------- */

async function onSend() {
  const price = priceInput.value.trim()
  if (price && !(Number(price) > 0)) {
    ElMessage.warning('改价需为大于 0 的数字')
    return
  }
  busy.value = true
  try {
    await sendQuoteInquiry(props.inquiry.id, price)
    ElMessage.success('报价已发送')
  } catch (e) {
    ElMessage.error(e.message || '发送失败')
  } finally {
    busy.value = false
    emit('refresh')
  }
}

async function onIgnore() {
  busy.value = true
  try {
    await ignoreQuoteInquiry(props.inquiry.id)
    ElMessage.success('已忽略该询价')
  } catch (e) {
    ElMessage.error(e.message || '操作失败')
  } finally {
    busy.value = false
    emit('refresh')
  }
}

async function copyText() {
  try {
    await navigator.clipboard.writeText(quoteText.value)
    ElMessage.success('话术已复制')
  } catch {
    ElMessage.error('复制失败，请手动选择复制')
  }
}
</script>

<template>
  <div class="card" :class="{ open: expanded }">
    <div class="head" @click="expanded = !expanded">
      <div class="row-top">
        <span class="group">{{ inquiry.conversation_name }}</span>
        <span class="chip" :class="`s${inquiry.status}`">{{ inquiry.status_label }}</span>
      </div>
      <div class="car">{{ carLine }}</div>
      <div class="row-bottom">
        <span class="time">{{ timeText }}</span>
        <span class="meta">
          <em v-if="r.pricing?.final_price" class="num price">¥{{ r.pricing.final_price }}</em>
          <em v-else class="part">{{ inquiry.part_name || '—' }}</em>
          <svg class="chev" :class="{ up: expanded }" viewBox="0 0 24 24" width="12" height="12">
            <path d="M6 9l6 6 6-6" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </span>
      </div>
    </div>

    <!-- 展开态：紧凑摘要卡 + 快捷动作区 -->
    <div v-if="expanded" class="detail">

      <!-- 主操作区（视觉最显眼） -->
      <div class="quick-actions">
        <button class="qa-btn qa-primary" @click.stop="onOpenDetail">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>
          </svg>
          打开详情页报价
        </button>
        <button class="qa-btn qa-ghost" @click.stop="onJumpToBubble">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>
          </svg>
          定位聊天气泡
        </button>
      </div>

      <!-- 紧凑摘要卡 -->
      <div v-if="r.error" class="err">{{ r.error }}</div>

      <div class="snap">
        <div class="snap-row">
          <span class="snap-label">车型</span>
          <span class="snap-val snap-car">{{ carLine }}</span>
        </div>
        <div v-if="vinShort" class="snap-row">
          <span class="snap-label">VIN</span>
          <span class="snap-val num">{{ vinShort }}</span>
        </div>
        <div class="snap-row">
          <span class="snap-label">配件</span>
          <span class="snap-val">
            {{ inquiry.part_name || '—' }}
            <span v-if="items.length" class="snap-count">· {{ items.length }} 款报价</span>
          </span>
        </div>
      </div>

      <!-- 配件缩略图预览（最多 2 个，单行紧凑） -->
      <div v-if="itemPreviews.length" class="thumbs">
        <div v-for="(p, i) in itemPreviews" :key="i" class="thumb-item">
          <img v-if="p.image" class="thumb-img" :src="p.image" alt="" loading="lazy">
          <div v-else class="thumb-img placeholder">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
          </div>
          <div class="thumb-info">
            <div class="thumb-name" :title="p.name">{{ p.name }}</div>
            <div class="thumb-oe num">{{ p.oe }}</div>
            <div v-if="p.price" class="thumb-price num">¥{{ p.price }}</div>
          </div>
        </div>
      </div>

      <!-- 原有报价话术 & 改价发送（功能保留） -->
      <div v-if="quoteText || actionable" class="send-block">
        <div v-if="quoteText" class="send-head">
          <span>报价话术</span>
          <a class="copy" @click.prevent="copyText">复制</a>
        </div>
        <textarea v-if="quoteText" class="quote-text" readonly :value="quoteText" rows="3"></textarea>
        <div v-if="actionable" class="price-row">
          <input
            v-model="priceInput" class="price-input" type="number" min="0" step="0.01"
            placeholder="改价（可选）" @keyup.enter="onSend"
          >
          <button class="btn send" :disabled="busy" @click="onSend">发送</button>
          <button class="btn ignore" :disabled="busy" @click="onIgnore">忽略</button>
        </div>
        <div v-else-if="inquiry.sent_at" class="sent-note">已于 {{ inquiry.sent_at }} 发送</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.card {
  position: relative;
  animation: card-in 0.3s both;
}
@keyframes card-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: none; }
}
.card::before {
  content: '';
  position: absolute; left: 0; top: 10px; bottom: 10px; width: 3px;
  background: var(--c-primary);
  border-radius: 2px;
  opacity: 0;
  transition: opacity 0.15s;
}
.card:hover::before, .card.open::before { opacity: 1; }
.card.open, .head:hover { background: #fdf7f6; }

.head { padding: 9px 11px; cursor: pointer; }

.row-top { display: flex; justify-content: space-between; gap: 8px; align-items: center; }
.group {
  font-weight: 600; font-size: 13px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.chip {
  flex-shrink: 0; font-size: 10px; padding: 2px 8px; border-radius: 999px;
  color: var(--c-text-sub); background: var(--c-bg);
}
.chip.s1 { color: #b45309; background: #fef3c7; }   /* 待人工 */
.chip.s3 { color: #15803d; background: #dcfce7; }   /* 已报价 */
.chip.s4 { color: var(--c-text-sub); background: var(--c-bg); } /* 已忽略 */

.car {
  margin: 6px 0;
  padding: 5px 8px;
  font-size: 12px; line-height: 1.5;
  color: var(--c-primary-deep);
  background: var(--c-primary-soft);
  border-radius: var(--r-sm);
  border-left: 3px solid var(--c-primary);
}

.row-bottom { display: flex; justify-content: space-between; align-items: center; }
.time { font-size: 11px; color: var(--c-text-sub); }
.meta { display: flex; align-items: center; gap: 6px; }
.price { font-style: normal; font-weight: 700; font-size: 13px; color: var(--c-primary); }
.part {
  font-style: normal; font-size: 11px; color: var(--c-text-sub);
  max-width: 140px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.chev { color: var(--c-text-sub); transition: transform 0.15s; }
.chev.up { transform: rotate(180deg); }

/* ===== 展开态 ===== */
.detail { padding: 8px 11px 11px; display: flex; flex-direction: column; gap: 8px; }
.err {
  font-size: 11px; color: var(--c-danger);
  background: #fef2f2; border: 1px solid #fecaca;
  border-radius: var(--r-sm); padding: 5px 7px;
}

/* 主操作区（两个大按钮） */
.quick-actions {
  display: flex; gap: 6px; padding-bottom: 8px;
  border-bottom: 1px dashed var(--c-border);
}
.qa-btn {
  flex: 1; min-width: 0;
  display: inline-flex; align-items: center; justify-content: center; gap: 5px;
  font-size: 12px; font-weight: 500;
  padding: 7px 10px;
  border-radius: var(--r-sm);
  border: 1px solid var(--c-border-strong);
  background: var(--c-surface);
  color: var(--c-text);
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}
.qa-btn:hover { transform: translateY(-1px); }
.qa-primary {
  background: var(--c-primary);
  border-color: var(--c-primary-deep);
  color: #fff;
  font-weight: 600;
  box-shadow: 0 1px 4px rgba(232,32,22,0.25);
}
.qa-primary:hover { background: var(--c-primary-deep); box-shadow: 0 2px 6px rgba(232,32,22,0.35); }
.qa-ghost:hover { background: var(--c-primary-soft); border-color: var(--c-primary); color: var(--c-primary); }

/* 紧凑摘要卡 */
.snap {
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
  padding: 6px 10px;
  background: var(--c-panel);
}
.snap-row {
  display: flex; gap: 8px;
  font-size: 11px; line-height: 1.9;
}
.snap-label { color: var(--c-text-muted); width: 36px; flex-shrink: 0; }
.snap-val { color: var(--c-text); word-break: break-all; }
.snap-car { color: var(--c-primary-deep); font-weight: 500; }
.snap-count { color: var(--c-primary); font-size: 10px; }

/* 配件缩略图预览 */
.thumbs {
  display: flex; gap: 6px;
}
.thumb-item {
  flex: 1; min-width: 0;
  display: flex; gap: 6px;
  border: 1px solid var(--c-border);
  border-radius: var(--r-sm);
  padding: 6px;
  background: var(--c-surface);
}
.thumb-img {
  width: 40px; height: 40px;
  object-fit: cover;
  border-radius: var(--r-xs);
  border: 1px solid var(--c-border);
  flex-shrink: 0;
  background: var(--c-panel);
}
.thumb-img.placeholder {
  display: grid; place-items: center;
  color: var(--c-text-muted);
}
.thumb-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 0; }
.thumb-name {
  font-size: 11px; font-weight: 600;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.thumb-oe { font-size: 10px; color: var(--c-text-muted); }
.thumb-price { font-size: 12px; font-weight: 700; color: var(--c-primary); margin-top: 2px; }

/* 话术 + 改价发送 */
.send-block {
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
  padding: 6px 8px;
}
.send-head {
  font-size: 11px; font-weight: 600; color: var(--c-text-sub);
  margin-bottom: 4px; display: flex; justify-content: space-between; align-items: center;
}
.copy { color: var(--c-primary); font-weight: 400; cursor: pointer; font-size: 11px; }
.copy:hover { text-decoration: underline; }

.quote-text {
  width: 100%; box-sizing: border-box;
  font-size: 11px; line-height: 1.55; font-family: inherit;
  color: var(--c-text); background: #fafbfd;
  border: 1px solid var(--c-border); border-radius: var(--r-xs);
  padding: 5px 6px; resize: vertical;
}
.price-row { display: flex; gap: 6px; margin-top: 6px; }
.price-input {
  flex: 1; min-width: 0; box-sizing: border-box;
  font-size: 12px; padding: 5px 8px;
  border: 1px solid var(--c-border-strong); border-radius: var(--r-md);
  outline: none; transition: border-color 0.15s, box-shadow 0.15s;
}
.price-input:focus { border-color: var(--c-primary); box-shadow: 0 0 0 3px rgba(232, 32, 22, 0.1); }
.btn {
  flex-shrink: 0; font-size: 12px; padding: 5px 12px;
  border-radius: var(--r-md); border: 1px solid var(--c-border-strong);
  background: var(--c-panel); color: var(--c-text); cursor: pointer;
  transition: all 0.15s;
}
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn.send {
  background: var(--c-primary); border-color: var(--c-primary-deep);
  color: #fff; font-weight: 600;
  box-shadow: 0 1px 4px rgba(232, 32, 22, 0.25);
}
.btn.send:hover:not(:disabled) { background: var(--c-primary-deep); }
.btn.ignore:hover:not(:disabled) { color: var(--c-danger); border-color: var(--c-danger); }
.sent-note { margin-top: 6px; font-size: 11px; color: #15803d; }
</style>
