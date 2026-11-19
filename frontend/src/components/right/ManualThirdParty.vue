<script setup>
/** 第三方比价子页：兆配云 zpy（城市报价表）+ 机汽人 jqr（供应商竞价表）。
 *
 * 上游中文键名原样透传，价格统一 String 化展示；zpy 最低价高亮。
 * 默认查询示例 OE（1665000075），输入后回车/点击查询。
 */
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { qqJqr, qqZpy } from '../../api'
import { fmtValue } from '../../utils/quoteQuery'

const SOURCE_DEFAULT = '1665000075'

const number = ref(SOURCE_DEFAULT)
const source = ref('zpy') // zpy | jqr
const loading = ref(false)
const zpyRows = ref([])
const jyRows = ref([])
const xjRows = ref([])
const loaded = ref(false)
const error = ref('')

const ZPY_COLS = [
  { key: '城市', label: '城市' },
  { key: '库存', label: '库存' },
  { key: '折扣', label: '折扣' },
  { key: '含税售价', label: '含税售价' },
  { key: '4S含税进价', label: '4S含税进价' },
  { key: '发货说明', label: '发货说明' },
]

const JQR_COLS = [
  { key: 'custom_brand_name', label: '品牌' },
  { key: 'city_name', label: '城市' },
  { key: 'default_code', label: '供应商编码' },
  { key: 'level_code', label: '等级' },
  { key: 'credit_score', label: '信用分' },
  { key: '_score', label: '匹配分' },
]

async function load() {
  const num = number.value.trim()
  if (!num) {
    ElMessage.warning('请输入 OE 编号')
    return
  }
  loading.value = true
  error.value = ''
  try {
    if (source.value === 'zpy') {
      const data = await qqZpy(num)
      zpyRows.value = Array.isArray(data) ? data : []
      jyRows.value = []
    } else {
      const data = (await qqJqr(num)) || {}
      jyRows.value = Array.isArray(data.jy_data) ? data.jy_data : []
      xjRows.value = Array.isArray(data.xj_data) ? data.xj_data : []
      zpyRows.value = []
    }
    loaded.value = true
  } catch (e) {
    error.value = e.message || '查询失败'
  } finally {
    loading.value = false
  }
}

const minPrice = () => {
  const prices = zpyRows.value
    .map((r) => parseFloat(String(r['含税售价'] ?? '').replace(/[^\d.]/g, '')))
    .filter((n) => n > 0)
  return prices.length ? Math.min(...prices) : NaN
}

const isMin = (row) => {
  const p = parseFloat(String(row['含税售价'] ?? '').replace(/[^\d.]/g, ''))
  return p > 0 && p === minPrice()
}

const fmt = fmtValue

function switchSource(key) {
  source.value = key
  if (loaded.value) load()
}

onMounted(load)
</script>

<template>
  <div class="third">
    <div class="qq-box">
      <div class="qq-row">
        <div class="seg">
          <span class="sg" :class="{ on: source === 'zpy' }" @click="switchSource('zpy')">兆配云</span>
          <span class="sg" :class="{ on: source === 'jqr' }" @click="switchSource('jqr')">机汽人</span>
        </div>
        <input v-model="number" class="qq-input num" placeholder="OE 编号" @keyup.enter="load">
        <button class="qq-btn-primary" :disabled="loading" @click="load">查询</button>
      </div>
    </div>

    <div v-if="loading" class="qq-skel"><span class="ring"></span>比价查询中…</div>
    <div v-else-if="error" class="qq-empty err">{{ error }}</div>

    <template v-else-if="source === 'zpy'">
      <div v-if="zpyRows.length" class="qq-scroll">
        <table class="qq-table">
          <thead>
            <tr><th v-for="c in ZPY_COLS" :key="c.key">{{ c.label }}</th></tr>
          </thead>
          <tbody>
            <tr v-for="(r, i) in zpyRows" :key="i" :class="{ min: isMin(r) }">
              <td v-for="c in ZPY_COLS" :key="c.key" :class="{ n: c.key !== '发货说明' }">
                {{ fmt(r[c.key]) }}
                <span v-if="c.key === '含税售价' && isMin(r)" class="qq-badge b-green">最低</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else-if="loaded" class="qq-empty">兆配云未返回该 OE 的报价</div>
    </template>

    <template v-else>
      <table v-if="jyRows.length" class="qq-table">
        <thead>
          <tr><th v-for="c in JQR_COLS" :key="c.key">{{ c.label }}</th></tr>
        </thead>
        <tbody>
          <tr v-for="(r, i) in jyRows" :key="i">
            <td v-for="c in JQR_COLS" :key="c.key" :class="{ n: c.key !== 'custom_brand_name' }">{{ fmt(r[c.key]) }}</td>
          </tr>
        </tbody>
      </table>
      <div v-else-if="loaded" class="qq-empty">
        机汽人未返回该 OE 的竞价{{ xjRows.length ? '' : '（xj 数据为空）' }}
      </div>
    </template>
  </div>
</template>

<style scoped>
/* 数据源切换：分段 pill 组 */
.seg {
  display: flex; gap: 2px; flex: none;
  padding: 2px;
  background: var(--c-bg);
  border-radius: 999px;
}
.sg {
  padding: 4px 10px; font-size: 11px; color: var(--c-text-sub);
  cursor: pointer; border-radius: 999px;
  transition: all 0.15s; user-select: none;
}
.sg:hover { color: var(--c-primary); }
.sg.on {
  background: var(--c-panel); color: var(--c-primary); font-weight: 600;
  box-shadow: 0 1px 3px rgba(31, 45, 61, 0.12);
}

/* 兆配云最低价行：绿色语义高亮 */
.qq-table tr.min td { background: var(--c-ok-soft); font-weight: 600; }
/* 单元格内「最低」徽章：比公共款更紧凑、实底绿（表格高亮语义） */
.qq-table .qq-badge.b-green { padding: 1px 7px; margin-left: 4px; background: var(--c-ok); color: #fff; }
</style>
