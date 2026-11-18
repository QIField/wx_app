/** 报价分析统计辅助：趋势百分比 / 柱高换算（AnalysisView 展示层纯函数）。 */

/** 当期对上期的变化百分比：prev>0 取整百分比；prev=0 且 cur>0 → null（前端显示「新增」）；双 0 → 0。 */
export function trendPercent(cur, prev) {
  const c = Number(cur) || 0
  const p = Number(prev) || 0
  if (p > 0) return Math.round(((c - p) / p) * 100)
  return c > 0 ? null : 0
}

/** 系列最大值（全 0 返回 0）。 */
export function maxOf(series) {
  const nums = (series || []).map((v) => Number(v) || 0)
  return nums.length ? Math.max(...nums) : 0
}

/** 柱高百分比：v/max*100，>0 时最低 6% 保证可见（max=0 → 0）。 */
export function barPercent(v, max) {
  if (!(max > 0)) return 0
  const n = Number(v) || 0
  if (n <= 0) return 0
  return Math.max(6, Math.min(100, Math.round((n / max) * 100)))
}

/** 趋势徽标文案：▲/▼ + n%（null 显示「新增」，0 显示「持平」）。 */
export function trendBadge(percent) {
  if (percent == null) return { text: '新增', cls: 'up' }
  if (percent === 0) return { text: '持平', cls: '' }
  return percent > 0
    ? { text: `▲ ${percent}%`, cls: 'up' }
    : { text: `▼ ${Math.abs(percent)}%`, cls: 'down' }
}
