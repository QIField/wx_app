/** 通用格式化/工具：时间、关键词高亮。 */

/** 时间显示：MM-DD HH:MM（与 ConvList 一致）。 */
export function fmtTime(t) {
  return t ? String(t).slice(5, 16) : ''
}

export function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[ch]))
}

/** 关键词高亮：先转义再包 mark，返回 HTML 片段（调用方用 v-html + :deep(mark) 定样式）。 */
export function highlight(text, keyword) {
  const safe = escapeHtml(text)
  const kw = (keyword || '').trim()
  if (!kw) return safe
  const kwEsc = escapeHtml(kw)
  const i = safe.toLowerCase().indexOf(kwEsc.toLowerCase())
  if (i < 0) return safe
  return safe.slice(0, i) + '<mark>' + safe.slice(i, i + kwEsc.length) + '</mark>' + safe.slice(i + kwEsc.length)
}

/** 关键词命中：任一字段不区分大小写包含关键词（空字段跳过，空关键词恒命中）。 */
export function matchKeyword(fields, keyword) {
  const kw = (keyword || '').trim().toLowerCase()
  if (!kw) return true
  return fields.some((x) => x && String(x).toLowerCase().includes(kw))
}
