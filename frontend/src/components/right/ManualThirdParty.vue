<script setup>
/** 第三方比价子页：兆配云 zpy（城市报价表）+ 机汽人 jqr（供应商竞价表）。
 *
 * 全字段展示：上游返回的每个 key 都进表格，不会漏。
 * - 已知字段 → 友好 label + 固定排序
 * - 未知字段 → 自动追加到表格末尾，保留原始 key 作列名
 * - 嵌套数组/对象 → 智能 stringify（数组提取 name 拼接）
 * - URL 字段 → 截断展示
 *
 * 默认查询示例 OE（1665000075），输入后回车/点击查询。
 */
import { onMounted, ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { qqJqr, qqZpy } from '../../api'

const SOURCE_DEFAULT = '1665000075'

const source = ref('zpy') // zpy | jqr
const loading = ref(false)

// 每个 tab 独立缓存：各自记住上次查询的 OE、结果、是否查过、错误
const zpyState = {
  number: ref(SOURCE_DEFAULT),
  rows: ref([]),
  loaded: ref(false),
  error: ref(''),
}
const jqrState = {
  number: ref(SOURCE_DEFAULT),
  jyRows: ref([]),
  xjRows: ref([]),
  loaded: ref(false),
  error: ref(''),
}

// 当前 tab 的 OE（输入框绑定）
const number = computed({
  get: () => (source.value === 'zpy' ? zpyState.number : jqrState.number).value,
  set: (v) => {
    ;(source.value === 'zpy' ? zpyState.number : jqrState.number).value = v
  },
})

// ---------- 兆配云：中文键名，上游原样透传 ----------
const ZPY_COLS = [
  { key: '配件编号', label: '配件编号' },
  { key: '配件名称', label: '配件名称' },
  { key: '品牌', label: '品牌' },
  { key: '4S含税售价', label: '4S含税售价' },
  { key: '4S含税进价', label: '4S含税进价' },
  { key: '折扣', label: '折扣' },
  { key: '含税售价', label: '含税售价' },
  { key: '城市', label: '城市' },
  { key: '库存', label: '库存' },
  { key: '发货说明', label: '发货说明' },
  { key: '物料组', label: '物料组' },
]

// ---------- 机汽人：英文键名，上游原样透传 ----------
const JQR_COLS = [
  // 配件核心信息
  { key: 'product_name', label: '配件名称' },
  { key: 'oe_number', label: 'OE编号' },
  { key: 'search_oe', label: '搜索OE' },
  { key: 'oe_epc_name', label: 'EPC配件名' },
  { key: 'product_name_search', label: '配件搜索名' },
  { key: 'quality_name', label: '品质' },
  // 品牌
  { key: 'brand_name', label: '品牌' },
  { key: 'custom_brand_name', label: '品牌全称' },
  { key: 'brand_initial', label: '品牌首字母' },
  { key: 'producing_area', label: '产地' },
  // 价格与供应商
  { key: 'price', label: '价格' },
  { key: 'price_except_flag', label: '特殊价' },
  { key: 'quantity', label: '数量' },
  { key: 'seller_name', label: '供应商' },
  { key: 'seller_id', label: '供应商ID' },
  { key: 'supplier_code', label: '供应商编码' },
  { key: 'default_code', label: '产品编码' },
  { key: 'product_id', label: '产品ID' },
  { key: 'product_template_id', label: '模板ID' },
  { key: 'payment_flag', label: '支付方式' },
  { key: 'plan_id', label: '方案ID' },
  // 位置与信用
  { key: 'city_name', label: '城市' },
  { key: 'country_code', label: '国家' },
  { key: 'credit_score', label: '信用分' },
  { key: 'level_code', label: '等级编码' },
  { key: 'level_flag', label: '等级标记' },
  { key: '_score', label: '匹配分' },
  // 车型适配
  { key: 'make', label: '适配品牌' },
  { key: 'make_name', label: '品牌名' },
  { key: 'make_id', label: '品牌ID' },
  { key: 'make_vehicle', label: '车型' },
  // 时间与统计
  { key: 'datelastupdate', label: '更新时间' },
  { key: 'enquiry_count', label: '询价次数' },
  { key: 'part_note', label: '备注' },
  { key: 'description', label: '描述' },
  // 渠道/其他
  { key: 'circle_name', label: '渠道名' },
  { key: 'circle_prod_id', label: '渠道产品ID' },
  { key: 'en_brand_name', label: '英文品牌' },
  { key: 'en_quality_name', label: '英文品质' },
  { key: 'vn_brand_name', label: '越南品牌' },
  { key: 'vn_quality_name', label: '越南品质' },
  { key: 'uom_name', label: '单位' },
  { key: 'seller_uuid', label: '供应商UUID' },
  // 图片 URL（保留原始，前端用 truncateUrl 截断）
  { key: 'brand_images_url', label: '品牌图标' },
  { key: 'make_images_url', label: '车型图标' },
]

// ---------- 工具函数 ----------

/** 单行值 → 可展示字符串：null/undefined/空→'-'，数组提取 name 拼接，URL 截断。 */
function cellValue(v) {
  if (v === null || v === undefined || v === '') return '-'
  if (Array.isArray(v)) {
    if (v.length === 0) return '-'
    // 对象数组：尝试提取 name 字段（机汽人 make: [{id, images, name}]）
    const names = v.map((item) => (item && typeof item === 'object' ? item.name : item))
    return names.join(', ')
  }
  if (typeof v === 'object') {
    try { return JSON.stringify(v) } catch { return String(v) }
  }
  const s = String(v)
  // 超长 URL 截断
  if (s.startsWith('http') && s.length > 60) return s.slice(0, 57) + '...'
  return s
}

/** 收集所有 row 的 key，去重；用于兜底未知字段自动追加。 */
function collectKeys(rows) {
  const set = new Set()
  for (const r of rows) {
    if (r && typeof r === 'object') Object.keys(r).forEach((k) => set.add(k))
  }
  return [...set]
}

/** 合并 COLS + 未知 key：未知 key 追加到末尾，label 用原始 key。 */
function buildCols(cols, rows) {
  const known = new Set(cols.map((c) => c.key))
  const extras = collectKeys(rows)
    .filter((k) => !known.has(k))
    .map((k) => ({ key: k, label: k }))
  return [...cols, ...extras]
}

// ---------- 动态列 ----------
const zpyCols = computed(() => buildCols(ZPY_COLS, zpyState.rows.value))
const jqrCols = computed(() => buildCols(JQR_COLS, jqrState.jyRows.value))

// ---------- 当前 tab 状态（模板里用） ----------
const curError = computed(() => (source.value === 'zpy' ? zpyState.error : jqrState.error).value)
const curLoaded = computed(() => (source.value === 'zpy' ? zpyState.loaded : jqrState.loaded).value)
const curZpyRows = computed(() => zpyState.rows.value)
const curJyRows = computed(() => jqrState.jyRows.value)
const curXjRows = computed(() => jqrState.xjRows.value)

// ---------- 查询：只更新当前 tab，不动另一个 ----------
async function load() {
  const num = number.value.trim()
  if (!num) {
    ElMessage.warning('请输入 OE 编号')
    return
  }
  loading.value = true
  if (source.value === 'zpy') {
    zpyState.error.value = ''
    try {
      const data = await qqZpy(num)
      zpyState.rows.value = Array.isArray(data) ? data : []
      zpyState.loaded.value = true
      zpyState.number.value = num
    } catch (e) {
      zpyState.error.value = e.message || '查询失败'
    }
  } else {
    jqrState.error.value = ''
    try {
      const data = (await qqJqr(num)) || {}
      jqrState.jyRows.value = Array.isArray(data.jy_data) ? data.jy_data : []
      jqrState.xjRows.value = Array.isArray(data.xj_data) ? data.xj_data : []
      jqrState.loaded.value = true
      jqrState.number.value = num
    } catch (e) {
      jqrState.error.value = e.message || '查询失败'
    }
  }
  loading.value = false
}

// ---------- 兆配云最低价高亮 ----------
const minPrice = () => {
  const prices = zpyState.rows.value
    .map((r) => parseFloat(String(r['含税售价'] ?? '').replace(/[^\d.]/g, '')))
    .filter((n) => n > 0)
  return prices.length ? Math.min(...prices) : NaN
}
const isMin = (row) => {
  const p = parseFloat(String(row['含税售价'] ?? '').replace(/[^\d.]/g, ''))
  return p > 0 && p === minPrice()
}

// ---------- 切换 tab：只切 source，不重查、不清空 ----------
function switchSource(key) {
  if (key === source.value) return
  source.value = key
  // 输入框自动同步成目标 tab 上次查询的 OE
  // （number 是 computed，getter 会自动从对应 state 取值）
}

// 挂载时只查当前 tab 一次；另一个 tab 等到用户点过去再查
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
    <div v-else-if="curError" class="qq-empty err">{{ curError }}</div>

    <template v-else-if="source === 'zpy'">
      <div v-if="curZpyRows.length" class="qq-scroll">
        <table class="qq-table">
          <thead>
            <tr><th v-for="c in zpyCols" :key="c.key">{{ c.label }}</th></tr>
          </thead>
          <tbody>
            <tr v-for="(r, i) in curZpyRows" :key="i" :class="{ min: isMin(r) }">
              <td v-for="c in zpyCols" :key="c.key">
                {{ cellValue(r[c.key]) }}
                <span v-if="c.key === '含税售价' && isMin(r)" class="qq-badge b-green">最低</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else-if="curLoaded" class="qq-empty">兆配云未返回该 OE 的报价</div>
      <div v-else class="qq-empty">输入 OE 编号后点击查询</div>
    </template>

    <template v-else>
      <div v-if="curJyRows.length" class="qq-scroll">
        <table class="qq-table">
          <thead>
            <tr><th v-for="c in jqrCols" :key="c.key">{{ c.label }}</th></tr>
          </thead>
          <tbody>
            <tr v-for="(r, i) in curJyRows" :key="i">
              <td v-for="c in jqrCols" :key="c.key">{{ cellValue(r[c.key]) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else-if="curLoaded" class="qq-empty">
        机汽人未返回该 OE 的竞价{{ curXjRows.length ? '' : '（xj 数据为空）' }}
      </div>
      <div v-else class="qq-empty">输入 OE 编号后点击查询</div>
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

/* 全字段展示 → 表格变宽，需要横向滚动 */
.qq-scroll {
  max-width: 100%;
  overflow-x: auto;
}
.qq-table {
  min-width: max-content;
  border-collapse: collapse;
}
</style>
