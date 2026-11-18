<script setup>
/** 报价处理台单卡：询价摘要 + 展开详情（车型/报价明细/产品比价/话术）+ 人工动作。
 *
 * 数据为契约 A r 结构（price_json），动作走 /quote/inquiries/{id}/send|ignore：
 * 改价只传 price（后端话术联动重建），下发失败后端转 review，前端一律刷新列表。
 */
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ignoreQuoteInquiry, sendQuoteInquiry } from '../api'

const props = defineProps({ inquiry: { type: Object, required: true } })
const emit = defineEmits(['refresh'])

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

const timeText = computed(() =>
  props.inquiry.sent_at || props.inquiry.inquiry_time || props.inquiry.created_at || '')

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

    <div v-if="expanded" class="detail">
      <div v-if="r.error" class="err">{{ r.error }}</div>

      <div v-if="car" class="block">
        <div class="blk-title">车辆信息</div>
        <div class="kv"><span>VIN</span><b>{{ car.vin || '—' }}</b></div>
        <div class="kv"><span>车型</span><b>{{ car.brandName }} {{ car.model }}</b></div>
        <div class="kv"><span>年款/排量</span><b>{{ car.yearPattern || '—' }} / {{ car.displacement || '—' }} {{ car.fuel }}</b></div>
      </div>

      <div v-if="items.length" class="block">
        <div class="blk-title">报价明细</div>
        <div v-for="(it, i) in items" :key="i" class="item">
          <div class="item-name">{{ it.product?.product_name || it.part }}（OE {{ it.oe }}）</div>
          <div class="item-prices">
            <span>成本 ¥{{ it.cost_price || '—' }}</span>
            <em v-if="it.final_price" class="final">报价 ¥{{ it.final_price }}</em>
            <em v-if="it.save_percent" class="save">省{{ it.save_percent }}%</em>
          </div>
        </div>
      </div>

      <div v-if="product" class="block">
        <div class="blk-title">产品档案</div>
        <div class="prod">
          <img v-if="product.image" class="prod-img" :src="product.image" alt="" loading="lazy">
          <div class="prod-info">
            <b class="prod-name">{{ product.product_name || '—' }}</b>
            <span class="prod-sub">{{ product.brand_name }} · 库号 {{ product.store_number || '—' }}</span>
            <span class="prod-sub">4S对照 ¥{{ product.store_price || '—' }}</span>
          </div>
        </div>
        <div v-if="product.child?.length" class="brands">
          <div v-for="(b, i) in product.child" :key="i" class="brand-row">
            <span class="b-name">{{ b.brand_name }}</span>
            <span class="b-price num">¥{{ b.cost_price || '—' }}</span>
            <span class="b-stock" :class="{ out: !b.stock }">{{ b.stock > 0 ? `库存${b.stock}` : '缺货' }}</span>
          </div>
        </div>
      </div>

      <div v-if="quoteText" class="block">
        <div class="blk-title">
          报价话术
          <a class="copy" @click.prevent="copyText">复制</a>
        </div>
        <textarea class="quote-text" readonly :value="quoteText" rows="6"></textarea>
        <div v-if="actionable" class="price-row">
          <input
            v-model="priceInput" class="price-input" type="number" min="0" step="0.01"
            placeholder="改价（可选，改首件报价）" @keyup.enter="onSend"
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
  border-bottom: 1px dashed var(--c-border-strong);
  position: relative;
  animation: card-in 0.3s both;
}
@keyframes card-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: none; }
}
.card::before {
  content: '';
  position: absolute; left: -2px; top: 10px; bottom: 10px; width: 3px;
  background: var(--c-primary);
  border-radius: 2px;
  opacity: 0;
  transition: opacity 0.15s;
}
.card:hover::before, .card.open::before { opacity: 1; }
.card.open { background: #f8fafd; }

.head { padding: 8px 10px; cursor: pointer; }
.head:hover { background: #f8fafd; }

.row-top { display: flex; justify-content: space-between; gap: 8px; align-items: center; }
.group {
  font-weight: 600; font-size: 13px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.chip {
  flex-shrink: 0; font-size: 10px; padding: 1px 6px; border-radius: 3px;
  color: var(--c-text-sub); background: #f1f3f7;
}
.chip.s1 { color: #b45309; background: #fef3c7; }   /* 待人工 */
.chip.s3 { color: #15803d; background: #dcfce7; }   /* 已报价 */
.chip.s4 { color: var(--c-text-sub); background: #eef0f4; } /* 已忽略 */

.car {
  margin: 5px 0;
  padding: 5px 7px;
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

.detail { padding: 2px 10px 10px; display: flex; flex-direction: column; gap: 8px; }
.err {
  font-size: 11px; color: var(--c-danger);
  background: #fef2f2; border: 1px solid #fecaca;
  border-radius: var(--r-sm); padding: 5px 7px;
}
.block { border: 1px solid var(--c-border); border-radius: var(--r-sm); padding: 6px 8px; }
.blk-title {
  font-size: 11px; font-weight: 600; color: var(--c-text-sub);
  margin-bottom: 5px; display: flex; justify-content: space-between; align-items: center;
}
.copy { color: var(--c-primary); font-weight: 400; cursor: pointer; }
.copy:hover { text-decoration: underline; }

.kv { display: flex; gap: 6px; font-size: 11px; line-height: 1.8; }
.kv span { color: var(--c-text-sub); flex-shrink: 0; }
.kv b { font-weight: 500; word-break: break-all; }

.item { padding: 3px 0; border-bottom: 1px dashed var(--c-border); }
.item:last-child { border-bottom: none; }
.item-name { font-size: 12px; font-weight: 600; }
.item-prices { display: flex; gap: 8px; align-items: baseline; font-size: 11px; color: var(--c-text-sub); margin-top: 2px; }
.final { font-style: normal; font-weight: 700; color: var(--c-primary); font-size: 12px; }
.save { font-style: normal; color: #15803d; }

.prod { display: flex; gap: 8px; }
.prod-img {
  width: 52px; height: 52px; object-fit: cover;
  border-radius: var(--r-sm); border: 1px solid var(--c-border); flex-shrink: 0;
}
.prod-info { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.prod-name { font-size: 12px; line-height: 1.4; }
.prod-sub { font-size: 11px; color: var(--c-text-sub); }

.brands { margin-top: 6px; border-top: 1px dashed var(--c-border); padding-top: 4px; }
.brand-row {
  display: flex; align-items: center; gap: 8px;
  font-size: 11px; line-height: 1.9;
}
.b-name { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.b-price { color: var(--c-text); font-weight: 600; }
.b-stock { color: #15803d; flex-shrink: 0; }
.b-stock.out { color: var(--c-danger); }

.quote-text {
  width: 100%; box-sizing: border-box;
  font-size: 11px; line-height: 1.6; font-family: inherit;
  color: var(--c-text); background: #fafbfd;
  border: 1px solid var(--c-border); border-radius: var(--r-sm);
  padding: 6px 7px; resize: vertical;
}
.price-row { display: flex; gap: 6px; margin-top: 8px; }
.price-input {
  flex: 1; min-width: 0; box-sizing: border-box;
  font-size: 12px; padding: 5px 8px;
  border: 1px solid var(--c-border); border-radius: var(--r-sm);
  outline: none;
}
.price-input:focus { border-color: var(--c-primary); }
.btn {
  flex-shrink: 0; font-size: 12px; padding: 5px 12px;
  border-radius: var(--r-sm); border: 1px solid var(--c-border);
  background: var(--c-panel); color: var(--c-text); cursor: pointer;
}
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn.send { background: var(--c-primary); border-color: var(--c-primary); color: #fff; font-weight: 600; }
.btn.send:hover:not(:disabled) { filter: brightness(1.08); }
.btn.ignore:hover:not(:disabled) { color: var(--c-danger); border-color: var(--c-danger); }
.sent-note { margin-top: 6px; font-size: 11px; color: #15803d; }
</style>
