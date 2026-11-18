/** 快捷报价手动查询辅助：类型识别 / 改价话术组装（手动查询结果卡与 AI 对话共用）。 */

const VIN_RE = /^[A-HJ-NPR-Z0-9]{17}$/i
const OE_RE = /^[A-Z]{0,3}\d{6,12}$/i

/** 输入 → 查询类型：17 位 VIN（去 I/O/Q）/ OE（≤3 字母前缀+6~12 数字）/ 配件名称，与后端编排同款。 */
export function detectType(q) {
  const s = String(q || '').trim()
  if (VIN_RE.test(s)) return 'vin'
  if (OE_RE.test(s)) return 'oe'
  return 'name'
}

export const TYPE_LABELS = { vin: 'VIN', oe: 'OE', name: '名称' }

/** 发送价：改价覆盖值 _price 优先，未改价回退产品成本价（原型 qPrice 契约）。 */
export function quotePrice(r) {
  if (r && r._price != null) return r._price
  const p = r && r.product
  return (p && p.cost_price) || ''
}

/** 手动查询结果 → 发送话术（原型 quoteText 同构；改价后追加报价行）。 */
export function quoteText(r) {
  const car = r && r.car
  const p = r && r.product
  const lines = []
  if (car) {
    const head = [car.brandName, car.model].filter(Boolean).join(' ')
    const tail = [car.yearPattern ? `${car.yearPattern}款` : '', car.displacement]
      .filter(Boolean).join(' ')
    lines.push(`【${[head, tail].filter(Boolean).join(' ')}】`)
  }
  if (p) {
    const oe = (p.display_number && p.display_number.value) || ''
    lines.push(`${p.product_name || ''}（OE ${oe}）`)
    const brands = (p.child || [])
      .filter((c) => c.brand_name && c.cost_price)
      .map((c) => `${c.brand_name} ¥${c.cost_price}${c.stock > 0 ? '' : '(缺货)'}`)
    if (brands.length) lines.push(brands.join(' / '))
    if (r._edited && quotePrice(r)) lines.push(`报价 ¥${quotePrice(r)}`)
    if (p.store_price) lines.push(`4S对照价 ¥${p.store_price}`)
  }
  return lines.filter(Boolean).join('\n') || '（无匹配产品）'
}

/** 省比：1 - 发送价/4S价，百分比取整；价格缺失或 4S 价非正返回 null。 */
export function savePercent(r) {
  const p = r && r.product
  const mine = Number(quotePrice(r))
  const store = Number(p && p.store_price)
  if (!(mine > 0) || !(store > 0)) return null
  return Math.max(0, Math.round((1 - mine / store) * 100))
}

/** 展示兜底：null/undefined/空串 → '-'，其余 String 化（比价与采购历史表格共用）。 */
export function fmtValue(v) {
  return v === null || v === undefined || v === '' ? '-' : String(v)
}

/** 秒级时间戳 → 本地日期 YYYY-MM-DD（不能用 toISOString：按 UTC 取日期在中国时区会偏移一天）。 */
export function ts2date(ts) {
  const n = Number(ts)
  if (!(n > 0)) return '-'
  const d = new Date(n * 1000)
  const pad = (x) => String(x).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}
