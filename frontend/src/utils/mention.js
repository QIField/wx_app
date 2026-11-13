/**
 * @提及（@mention）相关纯函数。
 *
 * 分工：
 *  - 本文件：触发检测、成员匹配排序、光标处插入原子片段、从 DOM 收集 at_ids、气泡高亮。
 *  - ChatComposer.vue：只负责浮层可见性/键盘导航/位置，不掺 DOM 细节。
 *  - 服务端：拿 at_ids（群成员行号）换算 ats=wxid，前端始终不持有 wxid（脱敏契约）。
 */
import { escapeHtml, renderEmojiHtml } from './emoji'
import { displayNameOf, matchPinyinToks } from './format'

/** 微信 @ 分隔符：昵称后必须是 U+2005（四分空格），否则对方收不到提醒。 */
export const AT_SEP = '\u2005'

/** 触发词：半角 @ 或中文输入法常见的全角 ＠，且光标前不允许空白（空白即结束检索）。 */
const TRIGGER_RE = /[@＠]([^\s@＠\u2005]*)$/

/** 气泡高亮：@昵称 后面必须跟 U+2005 或空白，避免把普通邮箱/文本里的 @ 误标蓝。 */
const MENTION_RE = /[@＠]([^@＠\s<]{1,32})(?=[\u2005\s])/g

/** @片段的 DOM 约定：class + data-member-id。插入、退格删除、发送取值三处共用。 */
const CHIP_CLASS = 'mention'
const CHIP_SELECTOR = `.${CHIP_CLASS}[data-member-id]`

/** 是否是我们插入的 @原子片段（contentEditable=false）。 */
function isMentionChip(node) {
  return node?.nodeType === 1 && node.classList.contains(CHIP_CLASS)
}

/** 当前选区；没有选区（未聚焦 / 多端点选区）返回 null。 */
function selectionRange() {
  const sel = window.getSelection()
  return sel && sel.rangeCount ? sel.getRangeAt(0) : null
}

/** 从「光标前的文本」里取出 @ 后的检索词；返回 null 表示不在 @ 上下文。 */
export function extractMentionQuery(textBeforeCaretStr) {
  const m = (textBeforeCaretStr || '').match(TRIGGER_RE)
  return m ? m[1] : null
}

/**
 * 光标之前的全部文本（跨节点）。
 * contenteditable 里光标可能落在任意文本节点，所以用 Range 从容器起点到光标来取，
 * 比只看当前文本节点可靠。
 */
export function textBeforeCaret(root) {
  const r = selectionRange()
  if (!r || !root.contains(r.startContainer)) return ''
  const pre = document.createRange()
  pre.selectNodeContents(root)
  pre.setEnd(r.startContainer, r.startOffset)
  return pre.toString()
}

/**
 * 命中打分（越小越靠前）：
 * 0 昵称前缀 → 1 全拼前缀 → 2 首字母前缀 → 3 昵称包含 → 4 全拼包含（字边界对齐）
 * → 5 首字母包含 → -1 不命中。
 * 中文输入时全拼不会命中，自然走昵称规则；拼音数据由后端 pypinyin 预计算，前端零依赖。
 */
export function scoreMember(member, query) {
  if (!query) return 0
  const name = (member.name || '').toLowerCase()
  const py = (member.pinyin || '').toLowerCase()
  const ini = (member.initials || '').toLowerCase()
  if (name.startsWith(query)) return 0
  if (py.startsWith(query)) return 1
  if (ini.startsWith(query)) return 2
  if (name.includes(query)) return 3
  // 全拼包含改字边界对齐：housheng 不再跨字命中 hang|zhou|sheng|chi 这类误结果
  if (matchPinyinToks(member.pinyin_toks, query)) return 4
  if (ini.includes(query)) return 5
  return -1
}

/** 过滤 + 排序：先按命中质量，同分按姓名（中文按拼音）字典序。 */
export function matchMembers(members, query) {
  const q = (query || '').trim().toLowerCase()
  return (members || [])
    .map((m) => ({ m, s: scoreMember(m, q) }))
    .filter((x) => x.s >= 0)
    .sort((a, b) => a.s - b.s || (a.m.name || '').localeCompare(b.m.name || '', 'zh-Hans-CN'))
    .map((x) => x.m)
}

/** 昵称高亮：只标直接子串命中；拼音命中在拼音行上标，避免名字上出现错位的黄色。
 *  昵称未解析（脱敏契约下 name=null）时用「匿名 {alias}」兜底展示，
 *  否则这一行只剩拼音，用户根本不知道该点谁。 */
export function memberNameHtml(member, query) {
  const name = displayNameOf(member)
  const q = (query || '').toLowerCase()
  const i = q ? name.toLowerCase().indexOf(q) : -1
  if (i < 0) return escapeHtml(name)
  return escapeHtml(name.slice(0, i))
    + `<mark>${escapeHtml(name.slice(i, i + q.length))}</mark>`
    + escapeHtml(name.slice(i + q.length))
}

/** 拼音行「全拼·首字母」：命中前缀标黄，向用户解释"为什么搜到了"。 */
export function memberPinyinHtml(member, query) {
  const py = member.pinyin || ''
  const ini = member.initials || ''
  const q = (query || '').toLowerCase()
  let pyOut = escapeHtml(py)
  let iniOut = escapeHtml(ini)
  if (q) {
    if (py.toLowerCase().startsWith(q)) {
      pyOut = `<mark>${escapeHtml(py.slice(0, q.length))}</mark>${escapeHtml(py.slice(q.length))}`
    } else if (ini.toLowerCase().startsWith(q)) {
      iniOut = `<mark>${escapeHtml(ini.slice(0, q.length))}</mark>${escapeHtml(ini.slice(q.length))}`
    }
  }
  return `${pyOut}<i>·</i>${iniOut}`
}

/**
 * 光标处把已经输入的「@关键词」整体替换成原子片段：
 * 1) 在同一文本节点里删掉 @ 到光标之间内容（中途只插过元素，所以光标与 @ 必然同节点）；
 * 2) 插入 contentEditable=false 的片段，光标进不去、退格一次删干净；
 * 3) 追加 U+2005 分隔符，光标落在其后，用户可继续输入。
 * 片段上带 data-member-id，发送时直接从 DOM 反推 at_ids，不会出现"删了文字但状态没清"。
 */
export function insertMentionAtCursor(root, member) {
  const r = selectionRange()
  if (!r || !member) return false
  const node = r.startContainer
  const off = r.startOffset

  let atIndex = -1
  if (node.nodeType === 3) {
    const before = node.data.slice(0, off)
    atIndex = Math.max(before.lastIndexOf('@'), before.lastIndexOf('＠'))
  }

  const anchor = document.createRange()
  if (node.nodeType === 3) {
    anchor.setStart(node, atIndex >= 0 ? atIndex : off)
    anchor.setEnd(node, off)
  } else {
    anchor.setStart(node, off) // 容器节点（空输入框/两段元素之间）：就地插入
    anchor.setEnd(node, off)
  }
  anchor.deleteContents()
  anchor.collapse(true)

  const chip = document.createElement('span')
  chip.className = CHIP_CLASS
  chip.contentEditable = 'false'
  chip.dataset.memberId = String(member.id)
  chip.textContent = '@' + displayNameOf(member)

  const sep = document.createTextNode(AT_SEP)
  const frag = document.createDocumentFragment()
  frag.appendChild(chip)
  frag.appendChild(sep)
  anchor.insertNode(frag)

  const after = document.createRange()
  after.setStart(sep, 1)
  after.collapse(true)
  const sel = window.getSelection()
  sel.removeAllRanges()
  sel.addRange(after)
  return true
}

/** 从 DOM 反推被 @ 的成员行号：删掉片段即自动移出列表，不维护额外状态。 */
export function collectMentionIds(root) {
  return [...root.querySelectorAll(CHIP_SELECTOR)]
    .map((n) => Number(n.dataset.memberId))
    .filter((id) => Number.isFinite(id))
}

/**
 * 退格原子化：光标紧贴片段时整块删除，避免留下"@"或半截昵称。
 * 返回 true 表示这次退格已由我们消费，调用方应 preventDefault。
 */
export function removeMentionAtCaret() {
  const r = selectionRange()
  if (!r || !r.collapsed) return false
  const node = r.startContainer

  let chip = null
  let sepNode = null // 整段只是分隔符的文本节点：一起删，避免残留隐形字符
  if (isMentionChip(node)) {
    chip = node
  } else if (node.nodeType === 3) {
    const before = node.data.slice(0, r.startOffset)
    // 光标紧贴片段：要么直接在分隔符节点开头，要么按过一次退格停在分隔符末尾
    if (before !== '' && before !== AT_SEP) return false
    const prev = node.previousSibling
    if (isMentionChip(prev)) {
      chip = prev
      if (node.data === AT_SEP) sepNode = node
    }
  }
  if (!chip) return false

  // 先落光标再删：选区是"活"的，删节点时边界会自动前移，光标不会丢在已删除节点上
  const range = document.createRange()
  range.setStartBefore(sepNode || chip)
  range.collapse(true)
  const sel = window.getSelection()
  sel.removeAllRanges()
  sel.addRange(range)
  chip.remove()
  if (sepNode) sepNode.remove()
  return true
}

/** 光标左侧字符的右边界（视口坐标）：用于把浮层贴到 @ 所在位置。
 *  不插临时节点测量，避免把文本节点拆开影响上面的"同节点删除"前提。 */
export function caretAnchorX() {
  const r = selectionRange()
  if (!r) return null
  const node = r.startContainer
  const off = r.startOffset
  if (node.nodeType === 3 && off > 0) {
    const rr = document.createRange()
    rr.setStart(node, off - 1)
    rr.setEnd(node, off)
    const rect = rr.getBoundingClientRect()
    if (rect && rect.width) return rect.right
  }
  const rects = r.getClientRects()
  return rects.length ? rects[0].left : null
}

/** 气泡文本：先按表情渲染（内部已转义），再高亮 @昵称 并去掉分隔符。
 *  与 setComposerFromText 使用的 renderEmojiHtml 分开，避免"重新编辑"时把片段塞回输入框。 */
export function renderMessageHtml(text) {
  return renderEmojiHtml(text)
    .replace(MENTION_RE, '<span class="msg-mention">@$1</span>')
    .replaceAll(AT_SEP, '')
}
