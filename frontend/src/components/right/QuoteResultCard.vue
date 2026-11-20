<script setup>
/** 手动查询结果卡（原型 quoteCardHTML 同构）：车型线 / 产品档案 / 价格行（改价联动）
 *  / 品牌比价表 / 爆炸图周边配件表 / 动作区。
 *
 * 发送：图前文后发到当前工作台会话（chat store currentId 守卫，无会话禁用 + tooltip）。
 * 改价：r._price 覆盖发送价，话术与省比联动（utils/quoteQuery 纯函数）。
 */
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useChatStore } from '../../stores/chat'
import { quotePrice, quoteText } from '../../utils/quoteQuery'

const props = defineProps({ r: { type: Object, required: true } })
const chat = useChatStore()

const editing = ref(false)
const priceInput = ref('')
const sending = ref(false)
const sentOk = ref(false)

const product = computed(() => props.r.product || null)
const car = computed(() => props.r.car || null)
const chain = computed(() => props.r.chain || [])
const images = computed(() => props.r.partImagesList || null)
const child = computed(() => (product.value && product.value.child) || [])
const canSend = computed(() => !!chat.currentId && !!product.value && !sentOk.value)

const carLine = computed(() => {
  const c = car.value
  if (!c) return ''
  const head = [c.brandName, c.model].filter(Boolean).join(' ')
  const tail = [c.yearPattern ? `${c.yearPattern}款` : '', c.displacement, c.fuel]
    .filter(Boolean).join(' ')
  const vin = c.vin ? ` · VIN ${c.vin}` : ''
  return [head, tail].filter(Boolean).join(' ') + vin
})

function startEdit() {
  priceInput.value = String(quotePrice(props.r) || '')
  editing.value = true
}

function confirmEdit() {
  const v = parseFloat(priceInput.value)
  if (!(v > 0)) {
    ElMessage.warning('请输入有效价格')
    return
  }
  props.r._price = v.toFixed(2)
  props.r._edited = true
  editing.value = false
  ElMessage.success(`已改价：¥${v.toFixed(2)}`)
}

async function onSend() {
  if (!canSend.value || sending.value) return
  sending.value = true
  try {
    const img = ((product.value && product.value.image) || '').trim()
    if (img) await chat.sendMedia(2, '', { img_url: img, path: '' }) // 产品决议：图在前
    await chat.sendText(quoteText(props.r))
    sentOk.value = true
    ElMessage.success('报价已发送至当前会话')
  } catch (e) {
    ElMessage.error(e.message || '发送失败')
  } finally {
    sending.value = false
  }
}

async function copyText() {
  try {
    await navigator.clipboard.writeText(quoteText(props.r))
    ElMessage.success('话术已复制')
  } catch {
    ElMessage.error('复制失败，请手动选择复制')
  }
}
</script>

<template>
  <div class="qcard">
    <div v-if="chain.length" class="chain">
      <template v-for="(s, i) in chain" :key="s + i">
        <span v-if="i" class="arr">▸</span>
        <span class="qq-badge b-blue">{{ s }}</span>
      </template>
      <span v-if="r.type" class="qq-badge b-gray">{{ { vin: 'VIN', oe: 'OE', name: '名称' }[r.type] }}查询</span>
    </div>

    <div v-if="car" class="car"><b>{{ carLine }}</b></div>

    <div v-if="product" class="qrow">
      <img v-if="product.image" class="thumb" :src="product.image" alt="" loading="lazy">
      <div v-else class="thumb none">无图</div>
      <div class="qinfo">
        <div class="pname">{{ product.product_name }}</div>
        <div class="poe num">OE {{ (product.display_number || {}).value }} · store {{ product.store_number }} · PARTENT {{ product.partent_number }}</div>
        <div class="price-line">
          <span class="mine num">¥{{ quotePrice(r) }}<small> 起我方价</small></span>
          <button v-if="!sentOk" class="price-edit" title="发送前改价" @click="startEdit">✎</button>
          <span v-if="edited" class="qq-badge b-orange">已改价</span>

        </div>
        <div v-if="product.sell_point" class="sell">卖点：{{ product.sell_point }}</div>
        <div v-if="editing" class="price-edit-row">
          <input v-model="priceInput" class="qq-input num" inputmode="decimal" @keyup.enter="confirmEdit" @keyup.esc="editing = false">
          <button class="qq-btn-sm primary" @click="confirmEdit">确定</button>
          <button class="qq-btn-sm" @click="editing = false">取消</button>
        </div>
      </div>
    </div>

    <div v-if="child.length" class="qq-scroll">
      <table class="qq-table">
        <thead>
          <tr><th>品牌</th><th>我方价</th><th>库存</th></tr>
        </thead>
        <tbody>
          <tr v-for="(c, i) in child" :key="i" :class="{ me: i === 0 }">
            <td>{{ c.brand_name }}<span v-if="i === 0" class="qq-badge b-green">推荐</span></td>
            <td class="n">¥{{ c.cost_price }}</td>
            <td class="n">
              <span v-if="c.stock > 0">{{ c.stock }}</span>
              <span v-else class="qq-badge b-red">缺货</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="images && images.length" class="qq-scroll">
      <table class="qq-table">
        <thead>
          <tr><th>标号</th><th>周边配件（爆炸图）</th><th>OE</th><th>用量</th></tr>
        </thead>
        <tbody>
          <tr v-for="(it, i) in images" :key="i">
            <td class="n">{{ it.imageLabel }}</td>
            <td>{{ it.oeName }}<small class="sub"> / {{ it.stdName }}</small></td>
            <td class="n">{{ it.oeCode }}</td>
            <td class="n">×{{ it.count }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="qacts">
      <button v-if="product" class="qq-btn-sm primary" :disabled="!canSend || sending" :title="chat.currentId ? '' : '请在工作台选中会话'" @click="onSend">
        {{ sentOk ? '已发送' : sending ? '发送中…' : '发送报价' }}
      </button>
      <button class="qq-btn-sm" @click="copyText">复制话术</button>
      <span class="sent-tag">
        <span v-if="sentOk" class="qq-badge b-green">✓ 已发送至会话</span>
        <span v-else-if="!product" class="qq-badge b-gray">无产品档案，仅车型卡</span>
      </span>
    </div>
  </div>
</template>

<style scoped>
.qcard { font-size: 12px; }

.chain { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; margin-bottom: 8px; }
.chain .arr { font-size: 9px; color: var(--c-border-strong); margin: 0 1px; }
.chain .qq-badge.b-gray { margin-left: auto; }

.car {
  font-size: 11px; color: var(--c-text-sub);
  background: var(--c-bg); border-radius: var(--r-sm);
  padding: 5px 8px; margin-bottom: 8px;
}
.car b { color: var(--c-text); }

.qrow { display: flex; gap: 8px; margin-bottom: 8px; }
.thumb {
  flex: none; width: 64px; height: 64px;
  border-radius: var(--r-sm); object-fit: cover;
  border: 1px solid var(--c-border); background: var(--c-bg);
}
.thumb.none { display: grid; place-items: center; color: #9aa7bc; font-size: 10px; }
.qinfo { flex: 1; min-width: 0; }
.pname { font-weight: 700; font-size: 12px; margin-bottom: 2px; }
.poe { font: 11px/1.4 var(--f-num); color: var(--c-text-sub); margin-bottom: 5px; }
.sell { font-size: 10px; color: var(--c-text-sub); margin-top: 4px; }
.sub { color: var(--c-text-sub); }

.price-line { display: flex; align-items: baseline; gap: 6px; flex-wrap: wrap; }
.mine { font: 700 17px/1 var(--f-num); color: var(--c-danger); }
.mine small { font-size: 10px; font-weight: 400; color: var(--c-text-sub); }
.s4 { font: 12px/1 var(--f-num); color: var(--c-text-sub); text-decoration: line-through; }
.save { font-size: 10px; color: var(--c-ok); background: var(--c-ok-soft); padding: 2px 6px; border-radius: var(--r-sm); }
.price-edit {
  border: none; background: var(--c-primary-soft); color: var(--c-primary);
  font-size: 11px; line-height: 1; padding: 3px 7px; border-radius: var(--r-sm);
  cursor: pointer; align-self: center;
}
.price-edit:hover { background: #fbd9d7; }
.price-edit-row { display: flex; gap: 5px; margin-top: 6px; }
/* 改价输入框：定宽紧凑款，覆盖公共 .qq-input 的自适应布局 */
.price-edit-row .qq-input { flex: none; width: 84px; padding: 3px 6px; }
.price-edit-row .qq-input:focus { box-shadow: none; }

.qq-table { margin: 6px 0 8px; }
.qq-table tr.me td { background: var(--c-primary-soft); font-weight: 600; }
.qq-table .qq-badge.b-green { margin-left: 4px; }

.qacts { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; margin-top: 4px; }
.sent-tag { margin-left: auto; display: inline-flex; }
</style>
