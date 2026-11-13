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

/** 拼音命中（字边界对齐）：关键词必须从某个「字」的拼音开头连续拼出。
 *  后端已预算逐字拼音 toks（张峰 → ['zhang','feng']），前端零依赖直接用。
 *  不用全拼子串匹配的原因：hang|zhou|sheng|chi 拼接串里 housheng 跨 zhou|sheng
 *  边界也能 includes 命中，导致「杭州圣驰汽配」混进「后生」的搜索结果。 */
export function matchPinyinToks(toks, keyword) {
  const kw = (keyword || '').trim().toLowerCase()
  if (!kw || !Array.isArray(toks) || !toks.length) return false
  for (let i = 0; i < toks.length; i++) {
    let seg = ''
    for (let j = i; j < toks.length; j++) {
      seg += toks[j]
      if (seg.length >= kw.length) {
        // 前缀已定：相等即命中，否则再拼也不会命中
        if (seg.startsWith(kw)) return true
        break
      }
    }
  }
  return false
}

/** 搜索框通用命中：原文/首字母子串 + 逐字拼音边界对齐。fields 与 toks 传数据行的字段。 */
export function matchName(fields, toks, keyword) {
  return matchKeyword(fields, keyword) || matchPinyinToks(toks, keyword)
}

/* ==================== 匿名展示（wxid 脱敏契约） ====================
 * 出参不含 wxid；名称未解析（name 为空）时以「匿名 + 编码」代称，
 * 头像画匿名图标。编码（alias）由后端 HMAC 派生：同码同人、不可逆。
 */

/** 展示名：name 缺失 → 「匿名 {alias}」（alias 缺失时兜底「匿名」）。 */
export function displayNameOf(item) {
  if (!item) return ''
  return item.name || (item.alias ? `匿名 ${item.alias}` : '匿名')
}

/** 名称是否已解析（决定头像走匿名图标还是首字/真实图）。 */
export function nameResolved(item) {
  return Boolean(item && item.name)
}

/** 匿名头像稳定色相：同一 alias 恒定，不同 alias 互异（群聊可区分）。 */
export function anonHue(alias) {
  let h = 0
  for (const ch of String(alias || '')) h = (h * 31 + ch.charCodeAt(0)) % 360
  return h
}

/** 匿名头像内联样式（背景色相由 alias 决定）。 */
export function anonStyle(alias) {
  return { background: `hsl(${anonHue(alias)}, 42%, 56%)` }
}
