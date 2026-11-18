<script setup>
/** 采购历史子页：按 OE 查询采购历史（上游 purchaseHistory），汇总 + 明细 + 简易分页。
 *
 * 上游三层嵌套 {total:{purchase_quantity,totalprice}, list:{total,current_page,last_page,data}}。
 */
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { qqPurchaseHistory } from '../../api'

const OE_DEFAULT = '1665000075'
const PAGE_SIZE = 10

const number = ref(OE_DEFAULT)
const loading = ref(false)
const loaded = ref(false)
const error = ref('')
const summary = ref({ quantity: '', total: '' })
const rows = ref([])
const page = ref(1)
const pages = ref(1)

const ts2date = (ts) => {
  const n = Number(ts)
  return n > 0 ? new Date(n * 1000).toISOString().slice(0, 10) : '-'
}
const fmt = (v) => (v === null || v === undefined || v === '' ? '-' : String(v))

async function load(p = 1) {
  const num = number.value.trim()
  if (!num) {
    ElMessage.warning('请输入 OE 编号')
    return
  }
  loading.value = true
  error.value = ''
  try {
    const data = (await qqPurchaseHistory(num, p, PAGE_SIZE)) || {}
    const total = data.total || {}
    const list = data.list || {}
    summary.value = {
      quantity: fmt(total.purchase_quantity),
      total: fmt(total.totalprice),
    }
    rows.value = Array.isArray(list.data) ? list.data : []
    page.value = Number(list.current_page) || p
    pages.value = Number(list.last_page) || 1
    loaded.value = true
  } catch (e) {
    error.value = e.message || '查询失败'
  } finally {
    loading.value = false
  }
}

const go = (delta) => {
  const next = page.value + delta
  if (next < 1 || next > pages.value) return
  load(next)
}

onMounted(load)
</script>

<template>
  <div class="history">
    <div class="mq-box">
      <div class="row">
        <input v-model="number" class="input num" placeholder="OE 编号" @keyup.enter="load(1)">
        <button class="btn primary" :disabled="loading" @click="load(1)">查询</button>
      </div>
    </div>

    <div v-if="loading" class="skel"><span class="ring"></span>采购历史查询中…</div>
    <div v-else-if="error" class="empty err">{{ error }}</div>

    <template v-else-if="loaded">
      <div class="ph-summary">
        <div class="ph-box"><div class="pl">累计采购次数</div><div class="pv num">{{ summary.quantity }}</div></div>
        <div class="ph-box"><div class="pl">累计采购金额</div><div class="pv num">¥{{ summary.total }}</div></div>
      </div>

      <table v-if="rows.length" class="qtable">
        <thead>
          <tr><th>采购单号</th><th>配件</th><th>供应商</th><th>单价</th><th>数量</th><th>日期</th></tr>
        </thead>
        <tbody>
          <tr v-for="(r, i) in rows" :key="i">
            <td class="n">{{ fmt(r.code || r.purchase_no) }}</td>
            <td>{{ fmt(r.part_name || r.name) }}</td>
            <td>{{ fmt(r.supplier_name || r.supplier) }}</td>
            <td class="n">¥{{ fmt(r.price) }}</td>
            <td class="n">{{ fmt(r.quantity || r.num) }}</td>
            <td class="n">{{ ts2date(r.ts || r.date) }}</td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty">该 OE 无采购记录</div>

      <div v-if="pages > 1" class="pager">
        <button class="pg" :disabled="page <= 1" @click="go(-1)">‹ 上一页</button>
        <span class="pinfo num">{{ page }} / {{ pages }}</span>
        <button class="pg" :disabled="page >= pages" @click="go(1)">下一页 ›</button>
      </div>
    </template>
    <div v-else class="empty">输入 OE 查询历史采购记录</div>
  </div>
</template>

<style scoped>
.mq-box {
  border: 1px solid var(--c-border); border-radius: var(--r-md);
  padding: 10px; background: #f9fafd; margin-bottom: 8px;
}
.row { display: flex; gap: 6px; }
.input {
  flex: 1; min-width: 0; padding: 5px 9px; font-size: 12px;
  border: 1px solid var(--c-border-strong); border-radius: var(--r-md);
  background: var(--c-panel); color: var(--c-text); outline: none;
}
.input:focus { border-color: var(--c-primary); }
.input.num { font-family: var(--f-num); }
.btn.primary {
  padding: 5px 13px; font-size: 12px; border-radius: var(--r-md); flex: none;
  border: 1px solid var(--c-primary-deep); color: #fff; font-weight: 600;
  background: linear-gradient(135deg, #2f6ff0, #1d5de4); cursor: pointer;
}
.btn.primary:disabled { opacity: 0.5; cursor: not-allowed; }

.ph-summary { display: flex; gap: 8px; margin-bottom: 8px; }
.ph-box {
  flex: 1; text-align: center;
  background: var(--c-primary-soft);
  border: 1px solid #c7d8ff;
  border-radius: var(--r-md); padding: 9px 6px;
}
.ph-box .pl { font-size: 10px; color: var(--c-primary-deep); margin-bottom: 3px; }
.ph-box .pv { font: 700 18px/1 var(--f-num); color: var(--c-primary); }

.skel { padding: 14px; text-align: center; color: var(--c-text-sub); font-size: 11px; }
.skel .ring {
  display: inline-block; width: 14px; height: 14px;
  border: 2px solid var(--c-border-strong); border-top-color: var(--c-primary);
  border-radius: 50%; animation: spin 0.7s linear infinite;
  vertical-align: -3px; margin-right: 6px;
}
@keyframes spin { to { transform: rotate(360deg); } }

.qtable { width: 100%; border-collapse: collapse; font-size: 11px; }
.qtable th {
  text-align: left; font-weight: 600; color: var(--c-text-sub);
  padding: 4px 6px; background: var(--c-bg);
  border-top: 1px solid var(--c-border); border-bottom: 1px solid var(--c-border);
  white-space: nowrap;
}
.qtable td { padding: 5px 6px; border-bottom: 1px solid var(--c-border); }
.qtable td.n { font-family: var(--f-num); white-space: nowrap; }
.empty { padding: 20px 10px; text-align: center; color: var(--c-text-sub); font-size: 11px; }
.empty.err { color: var(--c-danger); }

.pager { display: flex; align-items: center; justify-content: center; gap: 10px; margin-top: 8px; }
.pg {
  font-size: 11px; padding: 3px 9px;
  border: 1px solid var(--c-border-strong); border-radius: var(--r-sm);
  background: var(--c-panel); color: var(--c-text-sub); cursor: pointer;
}
.pg:hover:not(:disabled) { border-color: var(--c-primary); color: var(--c-primary); }
.pg:disabled { opacity: 0.4; cursor: not-allowed; }
.pinfo { font: 12px var(--f-num); color: var(--c-text-sub); }
</style>
