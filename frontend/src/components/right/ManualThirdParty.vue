<script setup>
/** 第三方比价子页：兆配云 zpy（城市报价表）+ 机汽人 jqr（供应商竞价表）。
 *
 * 每个 tab 独立缓存：切 tab 不清空上次查询结果，输入框自动同步。
 * - 兆配云 11 字段（4S 价 / 折扣 / 含税售价 / 城市库存）
 * - 机汽人 10 字段（严格对齐官网列表页，供应商→配件编码→价格）
 * - 字段严格按 COLS 定义显示，不做动态追加
 *
 * 默认查询示例 OE（1665000075），输入后回车/点击查询。
 * 首次进入不自动加载，等用户自己输入 OE。
 */
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { qqJqr, qqZpy } from '../../api'

const source = ref('zpy') // zpy | jqr
const loading = ref(false)

// 每个 tab 独立缓存：各自记住上次查询的 OE、结果、是否查过、错误
const zpyState = {
  number: ref(''),
  rows: ref([]),
  loaded: ref(false),
  error: ref(''),
}
const jqrState = {
  number: ref(''),
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

// ---------- 机汽人：对齐官网列表页的展示顺序 ----------
const JQR_COLS = [
  // === 左侧供应商信息区 ===
  { key: 'seller_name', label: '供应商' },
  { key: 'city_name', label: '城市' },

  // === 主表格 6 列（对齐机汽人官网） ===
  { key: 'oe_number', label: '配件编码' },
  { key: 'product_name', label: '商品' },
  { key: 'brand_name', label: '品牌' },
  { key: 'quality_name', label: '品质' },
  { key: 'quantity', label: '库存' },
  { key: 'price', label: '价格' },

  // === 右侧状态区 ===
  { key: 'datelastupdate', label: '更新时间' },
  { key: 'enquiry_count', label: '询价次数' },
]

// ---------- 工具函数 ----------

/** 单行值 → 可展示字符串：null/undefined/空→'-'，数组提取 name 拼接，URL 截断。 */
function cellValue(v) {
  if (v === null || v === undefined || v === '') return '-'
  if (Array.isArray(v)) {
    if (v.length === 0) return '-'
    const names = v.map((item) => (item && typeof item === 'object' ? item.name : item))
    return names.join(', ')
  }
  if (typeof v === 'object') {
    try { return JSON.stringify(v) } catch { return String(v) }
  }
  const s = String(v)
  if (s.startsWith('http') && s.length > 60) return s.slice(0, 57) + '...'
  return s
}

// ---------- 动态列：严格按 COLS 定义显示 ----------
const zpyCols = computed(() => ZPY_COLS)
const jqrCols = computed(() => JQR_COLS)

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

// ---------- 切换 tab：只切 source，不重查、不清空 ----------
function switchSource(key) {
  if (key === source.value) return
  source.value = key
  // 输入框自动同步成目标 tab 上次查询的 OE
  // （number 是 computed，getter 会自动从对应 state 取值）
}

// 首次激活不自动查询，等用户输入 OE 点查询；缓存命中时也不重查
// （InfoColumn 已用 v-show 保住 InfoPanel，ManualView 用 keep-alive 包住 4 个子页）
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
            <tr v-for="(r, i) in curZpyRows" :key="i">
              <td v-for="c in zpyCols" :key="c.key">
                {{ cellValue(r[c.key]) }}
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
