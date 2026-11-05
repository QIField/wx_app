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

/** 转账消息识别：标题或摘要含"转账"即视为转账卡片，金额从摘要提取。
 *
 * 返回 { amount, desc }（amount 千分位原样保留，解析不到为空串；desc 为摘要原文，
 * 供卡片金额缺失时兜底），非转账返回 null。
 * 转账卡片与复制全文都不落 url——收款只能在手机上操作，桌面端不留敏感链接。
 */
export function transferInfoOf(m) {
  if (m.msg_type !== 5) return null
  const app = appInfoOf(m)
  if (!(app.title || '').includes('转账') && !(app.desc || '').includes('转账')) return null
  const amount = ((app.desc || '').match(/([\d,]+(?:\.\d{1,2})?)\s*元/) || [])[1] || ''
  return { amount, desc: app.desc || '' }
}

/** 被引用内容是媒体 XML 时转展示标签（引用也支持引用图片/文件等）。 */
function referLabelOf(xml) {
  const root = parseXml(xml)
  if (!root) return '[引用]'
  const tag = (root.nodeName || '').toLowerCase()
  const has = (name) => !!root.getElementsByTagName(name)?.length
  if (tag === 'msg') {
    if (has('img')) return '[图片]'
    if (has('videomsg')) return '[视频]'
    if (has('voicemsg')) return '[语音]'
    if (has('emoji')) return '[表情]'
    const app = root.getElementsByTagName('appmsg')?.[0]
    if (app) {
      const sub = (app.getElementsByTagName('type')[0]?.textContent || '').trim()
      return sub === '6' ? '[文件]' : '[链接]'
    }
  }
  return '[引用]'
}

/** 引用消息信息 → {reply, name, text}；非引用返回 null。
 *
 * 新消息后端存好 payload.quote；历史数据（按链接入库的 msg_type=5）
 * 只有 content 里的原始 XML，这里解析 refermsg 兜底。
 */
export function quoteInfoOf(m) {
  const saved = m.payload?.quote
  if (saved && (saved.reply || saved.text || saved.name)) return saved
  if (![5, 8].includes(m.msg_type)) return null
  const root = parseXml(m.content)
  const refer = root?.getElementsByTagName?.('refermsg')?.[0]
  if (!refer) return null
  const pick = (el, tag) => (el?.getElementsByTagName(tag)[0]?.textContent || '').trim()
  const raw = pick(refer, 'content')
  return {
    reply: pick(root.getElementsByTagName('appmsg')[0], 'title'),
    name: pick(refer, 'displayname'),
    text: raw.startsWith('<') ? referLabelOf(raw) : raw,
  }
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

/* 引用消息全文：回复正文 + 引用行（回复为空不留空行） */
function quoteTextOf(q) {
  const reply = (q.reply || '').trim()
  const quoted = [q.name, q.text].filter(Boolean).join('：')
  return [reply, quoted && `引用 ${quoted}`].filter(Boolean).join('\n')
}

/* 消息类型 → 全文提取器：新增类型取值在此挂函数（无文本可取的类型不挂，返回空串） */
const TEXT_OF = {
  1: (m) => String(m.content ?? ''),
  3: fileTitleOf,
  5: (m) => {
    const t = transferInfoOf(m)
    if (t) return t.amount ? `转账 ¥${t.amount}（请在手机上确认收款）` : `转账：${t.desc}`
    const app = appInfoOf(m)
    return [app.title, app.desc, app.url].filter(Boolean).join('\n')
  },
}

/** 整条消息的可复制全文：右键复制/后续转发等操作的统一取值口。
 *
 * 引用消息带回复与被引原文，链接卡片取 标题/摘要/链接，文件取文件名；
 * 纯媒体（图片/语音/视频/表情）无文本可取，返回空串（菜单据此置灰，
 * 媒体操作后续单独扩展）。 */
export function msgTextOf(m) {
  if (!m) return ''
  const quote = quoteInfoOf(m)
  if (quote) return quoteTextOf(quote)
  return (TEXT_OF[m.msg_type] || (() => ''))(m)
}
