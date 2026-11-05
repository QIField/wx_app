/* ===== timeline.js · 消息时间轴分组（纯函数，不依赖组件） ===== */

/* 相邻消息间隔超过 5 分钟才插一条时间分隔线（此前按分钟变化就插，导致刷屏重复）。
   气泡上不再逐条显示时分，完整时间戳悬停气泡可见；标签按远近智能显示。 */
const TIME_GAP = 5 * 60 * 1000
const WEEK_CN = '日一二三四五六'

/** 消息时间 → 展示标签：今天只显示时分，按远近升级为 昨天 / 星期 / 日期 */
export function timeLabel(t) {
  const d = new Date(String(t).replace(' ', 'T'))
  const now = new Date()
  const hm = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  const dayDiff = Math.floor(
    (new Date(now.getFullYear(), now.getMonth(), now.getDate()) -
      new Date(d.getFullYear(), d.getMonth(), d.getDate())) / 86400000
  )
  if (dayDiff <= 0) return hm
  if (dayDiff === 1) return `昨天 ${hm}`
  if (dayDiff < 7) return `星期${WEEK_CN[d.getDay()]} ${hm}`
  const md = `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  return d.getFullYear() === now.getFullYear() ? `${md} ${hm}` : `${d.getFullYear()}-${md} ${hm}`
}

/** 消息数组 → 时间轴行：{type:'time', id, label} 与 {type:'msg', ...m} 交错 */
export function buildTimeline(msgs) {
  const out = []
  let last = null
  for (const m of msgs) {
    const t = m.create_time ? Date.parse(String(m.create_time).replace(' ', 'T')) : NaN
    if (!Number.isNaN(t) && (last === null || t - last >= TIME_GAP)) {
      out.push({ type: 'time', id: 't' + m.id, label: timeLabel(m.create_time) })
    }
    out.push({ type: 'msg', ...m })
    if (!Number.isNaN(t)) last = t
  }
  return out
}
