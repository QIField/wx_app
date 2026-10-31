/** 消息内容工具：微信 XML 消息的识别与卡片信息解析。
 *
 * 新消息由后端在 payload.app 里存好结构化卡片信息；历史数据只有
 * content 里的原始 XML，这里用 DOMParser 兜底解析（解析失败按普通文本）。
 */

/** 解析 XML 文本为文档根节点；非 XML 或解析失败返回 null。 */
function parseXml(text) {
  const raw = String(text ?? '').trim()
  if (!raw.startsWith('<')) return null
  try {
    const doc = new DOMParser().parseFromString(raw, 'text/xml')
    return doc.querySelector('parsererror') ? null : doc.documentElement
  } catch {
    return null
  }
}

/** 消息是否实为微信系统 XML（拍一拍/撤回通知/好友验证等），前端按灰条兜底。 */
export function isSystemXml(m) {
  if (m.msg_type !== 1) return false
  const root = parseXml(m.content)
  return !!root && ['msg', 'sysmsg'].includes((root.nodeName || '').toLowerCase())
}

/** 链接/文件卡片信息：payload.app 优先，旧数据从 content XML 解析。 */
export function appInfoOf(m) {
  const app = m.payload?.app
  if (app && (app.title || app.url || app.desc)) return app
  const root = parseXml(m.content)
  const node = root?.getElementsByTagName?.('appmsg')?.[0]
  if (!node) return {}
  const pick = (tag) => (node.getElementsByTagName(tag)[0]?.textContent || '').trim()
  return { title: pick('title'), desc: pick('des'), url: pick('url') }
}

/** 文件消息的显示名：普通文件名直接用，appmsg 文件取卡片标题。 */
export function fileTitleOf(m) {
  const raw = String(m.content ?? '').trim()
  if (raw && !raw.startsWith('<')) return raw
  return appInfoOf(m).title || '[文件]'
}

/** 撤回的消息能否重新编辑：仅自己发的纯文本（微信同款限制）。 */
export function canReEdit(m) {
  return !!m.payload?.revoked && m.direction === 2 && !!m.content && !isSystemXml(m)
}

/** 链接域名：卡片页脚展示。 */
export function hostOf(url) {
  try {
    return new URL(url).hostname
  } catch {
    return ''
  }
}
