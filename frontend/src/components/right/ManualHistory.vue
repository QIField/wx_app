<script setup>
/** 采购历史子页：按 OE 查询采购历史。
 *
 * 后端 purchase_history 默认 limit=9999，一次拉全所有记录，前端本地分页展示。
 * 布局：history 占满父容器高度 → 输入框/汇总卡钉顶 → 表格区滚动 + 分页器钉底。
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { qqPurchaseHistory } from '../../api'
import { fmtValue, ts2date } from '../../utils/quoteQuery'

const OE_DEFAULT = '33526866656'
const PAGE_SIZE = 10

const number = ref(OE_DEFAULT)
const loading = ref(false)
const loaded = ref(false)
const error = ref('')
const summary = ref({ quantity: '', total: '', count: '' })
const rows = ref([])
const page = ref(1)

const fmt = fmtValue

const pageCount = computed(() => Math.max(1, Math.ceil(rows.value.length / PAGE_SIZE)))
const pageRows = computed(() => {
  const start = (page.value - 1) * PAGE_SIZE
  return rows.value.slice(start, start + PAGE_SIZE)
})

const go = (delta) => {
  const next = page.value + delta
  if (next < 1 || next > pageCount.value) return
  page.value = next
}
const jump = (n) => {
  const v = Number(n)
  if (v >= 1 && v <= pageCount.value) page.value = v
}

async function load() {
  const num = number.value.trim()
  if (!num) {
    ElMessage.warning('请输入 OE 编号')
    return
  }
  loading.value = true
  error.value = ''
  try {
    const data = (await qqPurchaseHistory(num)) || {}
    const total = data.total || {}
    const list = data.list || {}
    rows.value = Array.isArray(list.data) ? list.data : []
    summary.value = {
      quantity: fmt(total.purchase_quantity),
      total: fmt(total.totalprice),
      count: fmt(list.total || rows.value.length),
    }
    page.value = 1
    loaded.value = true
  } catch (e) {
    error.value = e.message || '查询失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <!-- history: flex column 占满父容器，内部自管滚动 -->
  <div class="history">
    <!-- 顶部固定区：输入框 + 汇总卡，不参与压缩 -->
    <div class="qq-box">
      <div class="qq-row">
        <input v-model="number" class="qq-input num" placeholder="OE 编号" @keyup.enter="load()">
        <button class="qq-btn-primary" :disabled="loading" @click="load()">查询</button>
      </div>
    </div>

    <div v-if="loading" class="qq-skel"><span class="ring"></span>采购历史查询中…</div>
    <div v-else-if="error" class="qq-empty err">{{ error }}</div>

    <template v-else-if="loaded">
      <div class="ph-summary">
        <div class="ph-box">
          <div class="pl">累计采购次数</div>
          <div class="pv num">{{ summary.count }}</div>
        </div>
        <div class="ph-box">
          <div class="pl">累计采购数量（件）</div>
          <div class="pv num">{{ summary.quantity }}</div>
        </div>
        <div class="ph-box">
          <div class="pl">累计采购金额</div>
          <div class="pv num">¥{{ summary.total }}</div>
        </div>
      </div>

      <!-- 表格 + 分页器：flex:1 填满剩余空间 -->
      <div v-if="rows.length" class="list-area">
        <div class="qq-scroll">
          <table class="qq-table">
            <thead>
              <tr>
                <th>单号</th><th>类型</th><th>配件</th><th>品牌</th>
                <th>供应商</th><th class="num-col">单价</th><th class="num-col">数量</th>
                <th class="num-col">金额</th><th>仓库</th><th>日期</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(r, i) in pageRows" :key="i">
                <td class="n" :title="fmt(r.order_no)">{{ fmt(r.order_no) }}</td>
                <td :class="{ neg: r.order_type_id === '2' }">{{ fmt(r.order_type_cn) }}</td>
                <td>{{ fmt(r.l_name_zh_default || r.pdname) }}</td>
                <td>{{ fmt(r.brand) }}</td>
                <td class="sup" :title="fmt(r.company_name)">{{ fmt(r.company_name) }}</td>
                <td class="n">¥{{ fmt(r.unit_cost) }}</td>
                <td class="n" :class="{ neg: Number(r.purchase_quantity) < 0 }">{{ fmt(r.purchase_quantity) }}</td>
                <td class="n" :class="{ neg: Number(r.amount_money) < 0 }">¥{{ fmt(r.amount_money) }}</td>
                <td>{{ fmt(r.warehouse) }}</td>
                <td class="n">{{ ts2date(r.create_date) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="pageCount > 1" class="pager">
          <button class="pg" :disabled="page <= 1" @click="go(-1)">‹</button>
          <span v-for="n in pageCount" :key="n"
            :class="['pg', { active: n === page }]" @click="jump(n)">{{ n }}</span>
          <button class="pg" :disabled="page >= pageCount" @click="go(1)">›</button>
          <span class="pinfo num">{{ page }} / {{ pageCount }} · 共 {{ rows.length }} 条</span>
        </div>
      </div>
      <div v-else class="qq-empty flex-grow">该 OE 无采购记录</div>
    </template>

    <div v-else class="qq-empty flex-grow">输入 OE 查询历史采购记录</div>
  </div>
</template>

<style scoped>
/* 根容器：flex column 撑满父级，内部子元素自管滚动 */
.history {
  display: flex; flex-direction: column;
  height: 100%; min-height: 0;  /* min-height:0 允许子项收缩触发滚动 */
}
.history > .qq-box { flex: none; }

.ph-summary { display: flex; gap: 8px; margin-bottom: 8px; flex: none; }
.ph-box {
  flex: 1; text-align: center;
  background: var(--c-panel);
  border: 1px solid var(--c-border);
  border-radius: var(--r-lg);
  padding: 10px 6px;
  box-shadow: 0 2px 8px rgba(31, 45, 61, 0.05);
}
.ph-box .pl { font-size: 10px; color: var(--c-text-sub); margin-bottom: 4px; }
.ph-box .pv { font: 700 18px/1 var(--f-num); color: var(--c-primary); }

/* 列表区：flex column，内部表格可滚，分页器钉底 */
.list-area {
  display: flex; flex-direction: column;
  flex: 1; min-height: 0;  /* 关键：允许 flex 子项收缩 */
}
.list-area > .qq-scroll {
  flex: 1; min-height: 0;
  overflow: auto; scrollbar-width: thin;
}
.list-area > .pager { flex: none; }

.flex-grow { flex: 1; display: flex; align-items: center; justify-content: center; }

.qq-table .num-col { text-align: right; }
.qq-table td.neg, .qq-table .neg { color: #c0392b; }
.qq-table td.sup {
  max-width: 120px; overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap;
}

.pager { display: flex; align-items: center; justify-content: center; gap: 6px; margin-top: 8px; flex-wrap: wrap; }
.pg {
  font-size: 11px; padding: 3px 9px; border: 1px solid var(--c-border-strong);
  border-radius: 6px; background: var(--c-panel); color: var(--c-text-sub); cursor: pointer;
  transition: all 0.15s; line-height: 1;
}
.pg:hover:not(:disabled):not(.active) { border-color: var(--c-primary); color: var(--c-primary); }
.pg.active { background: var(--c-primary); border-color: var(--c-primary); color: #fff; }
.pg:disabled { opacity: 0.35; cursor: not-allowed; }
.pinfo { font: 12px var(--f-num); color: var(--c-text-sub); margin-left: 4px; }
</style>
