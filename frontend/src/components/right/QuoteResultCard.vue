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
import { quotePrice, quoteText, savePercent } from '../../utils/quoteQuery'

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
const percent = computed(() => savePercent(props.r))

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
        <span class="badge b-blue">{{ s }}</span>
      </template>
      <span v-if="r.type" class="badge b-gray">{{ { vin: 'VIN', oe: 'OE', name: '名称' }[r.type] }}查询</span>
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
          <span v-if="edited" class="badge b-orange">已改价</span>
          <span v-if="product.store_price" class="s4 num">4S ¥{{ product.store_price }}</span>
          <span v-if="percent != null" class="save">省 {{ percent }}%</span>
        </div>
        <div v-if="product.sell_point" class="sell">卖点：{{ product.sell_point }}</div>
        <div v-if="editing" class="price-edit-row">
          <input v-model="priceInput" class="input num" inputmode="decimal" @keyup.enter="confirmEdit" @keyup.esc="editing = false">
          <button class="btn sm primary" @click="confirmEdit">确定</button>
          <button class="btn sm" @click="editing = false">取消</button>
        </div>
      </div>
    </div>

    <table v-if="child.length" class="qtable">
      <thead>
        <tr><th>品牌</th><th>我方价</th><th>4S价</th><th>库存</th></tr>
      </thead>
      <tbody>
        <tr v-for="(c, i) in child" :key="i" :class="{ me: i === 0 }">
          <td>{{ c.brand_name }}<span v-if="i === 0" class="badge b-green">推荐</span></td>
          <td class="n">¥{{ c.cost_price }}</td>
          <td class="n">¥{{ c.store_price }}</td>
          <td class="n">
            <span v-if="c.stock > 0">{{ c.stock }}</span>
            <span v-else class="badge b-red">缺货</span>
          </td>
        </tr>
      </tbody>
    </table>

    <table v-if="images && images.length" class="qtable">
      <thead>
        <tr><th>标号</th><th>周边配件（爆炸图）</th><th>OE</th><th>4S价</th><th>用量</th></tr>
      </thead>
      <tbody>
        <tr v-for="(it, i) in images" :key="i">
          <td class="n">{{ it.imageLabel }}</td>
          <td>{{ it.oeName }}<small class="sub"> / {{ it.stdName }}</small></td>
          <td class="n">{{ it.oeCode }}</td>
          <td class="n">¥{{ it.price4s }}</td>
          <td class="n">×{{ it.count }}</td>
        </tr>
      </tbody>
    </table>

    <div class="qacts">
      <button v-if="product" class="btn sm primary" :disabled="!canSend || sending" :title="chat.currentId ? '' : '请在工作台选中会话'" @click="onSend">
        {{ sentOk ? '已发送' : sending ? '发送中…' : '发送报价' }}
      </button>
      <button class="btn sm" @click="copyText">复制话术</button>
      <span class="sent-tag">
        <span v-if="sentOk" class="badge b-green">✓ 已发送至会话</span>
        <span v-else-if="!product" class="badge b-gray">无产品档案，仅车型卡</span>
      </span>
    </div>
  </div>
</template>

<style scoped>
.qcard { font-size: 12px; }

.chain { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; margin-bottom: 8px; }
.chain .arr { font-size: 9px; color: var(--c-border-strong); margin: 0 1px; }

.badge { display: inline-block; padding: 2px 7px; font-size: 10px; border-radius: var(--r-sm); font-weight: 600; }
.badge.b-blue { background: var(--c-primary-soft); color: var(--c-primary); }
.badge.b-green { background: var(--c-ok-soft); color: var(--c-ok); margin-left: 4px; }
.badge.b-red { background: var(--c-danger-soft); color: var(--c-danger); }
.badge.b-orange { background: var(--c-warn-soft); color: var(--c-warn); }
.badge.b-gray { background: var(--c-bg); color: var(--c-text-sub); margin-left: auto; }

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
.price-edit:hover { background: #d8e5ff; }
.price-edit-row { display: flex; gap: 5px; margin-top: 6px; }
.price-edit-row .input { width: 84px; padding: 3px 6px; font-size: 12px; font-family: var(--f-num); border: 1px solid var(--c-border-strong); border-radius: var(--r-sm); outline: none; }
.price-edit-row .input:focus { border-color: var(--c-primary); }

.btn.sm {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 8px; font-size: 11px; border-radius: var(--r-sm);
  border: 1px solid var(--c-border-strong); background: var(--c-panel);
  color: var(--c-text); cursor: pointer; transition: all 0.15s;
}
.btn.sm:hover:not(:disabled) { border-color: var(--c-primary); color: var(--c-primary); background: var(--c-primary-soft); }
.btn.sm.primary { background: linear-gradient(135deg, #2f6ff0, #1d5de4); border-color: var(--c-primary-deep); color: #fff; font-weight: 600; }
.btn.sm.primary:hover:not(:disabled) { background: linear-gradient(135deg, #3d7bf5, #2a67e8); color: #fff; }
.btn.sm:disabled { opacity: 0.45; cursor: not-allowed; }
.btn.sm + .btn.sm { margin-left: 0; }

.qtable { width: 100%; border-collapse: collapse; margin: 6px 0 8px; font-size: 11px; }
.qtable th {
  text-align: left; font-weight: 600; color: var(--c-text-sub);
  padding: 4px 6px; background: var(--c-bg);
  border-top: 1px solid var(--c-border); border-bottom: 1px solid var(--c-border);
  white-space: nowrap;
}
.qtable td { padding: 5px 6px; border-bottom: 1px solid var(--c-border); }
.qtable td.n { font-family: var(--f-num); white-space: nowrap; }
.qtable tr.me td { background: var(--c-primary-soft); font-weight: 600; }

.qacts { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; margin-top: 4px; }
.sent-tag { margin-left: auto; display: inline-flex; }
</style>
