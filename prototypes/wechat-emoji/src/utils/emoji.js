/** 表情渲染与输入工具：纯函数，可原样平移到 wx_app/frontend/src/utils/emoji.js。
 *
 * 渲染契约：先 HTML 转义再替换表情码，未识别的 [xxx] 原样显示
 * （与微信客户端对未知码的兜底一致），天然防 XSS。
 */
import { WX_FACES, FACE_INDEX, faceUrlOf } from '../data/wxEmojis'

/* [名称] 码正则（名称由受控数组生成，仅需转义正则元字符） */
const FACE_RE = new RegExp(
  '\\[(' + WX_FACES.map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') + ')\\]',
  'g'
)

export function escapeHtml(s) {
  return String(s ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

/** 文本 → 可安全 v-html 的 HTML：`[微笑]` 变表情图，其余原样。 */
export function renderEmojiHtml(text) {
  const safe = escapeHtml(text)
  return safe.replace(FACE_RE, (whole, name) => {
    const url = faceUrlOf(name)
    return `<img class="wx-emoji" src="${url}" alt="${whole}" title="${whole}">`
  })
}

/* ---------- contenteditable 输入区：微信同款"光标处显示表情图" ---------- */

/** 取编辑器内有效光标；不在编辑器内时定位到末尾。 */
function caretRangeIn(root) {
  const sel = window.getSelection()
  if (sel && sel.rangeCount && root.contains(sel.getRangeAt(0).startContainer)) {
    return sel.getRangeAt(0)
  }
  const range = document.createRange()
  range.selectNodeContents(root)
  range.collapse(false)
  if (sel) {
    sel.removeAllRanges()
    sel.addRange(range)
  }
  return range
}

function placeCaret(range) {
  range.collapse(true)
  const sel = window.getSelection()
  if (sel) {
    sel.removeAllRanges()
    sel.addRange(range)
  }
}

/** 选表情后在光标处插入：wx → 表情图 img（data-name 记码），unicode → 字符文本。 */
export function insertEmojiAtCursor(root, { kind, name, char }) {
  if (!root) return
  root.focus()
  const range = caretRangeIn(root)
  range.deleteContents()
  let node
  if (kind === 'wx') {
    node = document.createElement('img')
    node.className = 'wx-emoji'
    node.src = faceUrlOf(name)
    node.alt = name
    node.title = name
    node.dataset.name = name
    node.draggable = false
  } else {
    node = document.createTextNode(char)
  }
  range.insertNode(node)
  range.setStartAfter(node)
  placeCaret(range)
}

/** Shift+Enter 换行：手动插入 <br>，避免浏览器包 div/块级导致序列化歧义。 */
export function insertBreakAtCursor(root) {
  if (!root) return
  root.focus()
  const range = caretRangeIn(root)
  range.deleteContents()
  const br = document.createElement('br')
  range.insertNode(br)
  range.setStartAfter(br)
  placeCaret(range)
}

/** 粘贴仅收纯文本（防富文本/图片破坏内容结构）。 */
export function insertPlainTextAtCursor(root, text) {
  if (!root) return
  root.focus()
  const range = caretRangeIn(root)
  range.deleteContents()
  range.insertNode(document.createTextNode(text))
  placeCaret(range)
}

/** 编辑器内容 → 上行文本：表情图 img 还原为 `[名称]` 码，<br> → \n。 */
export function serializeComposer(root) {
  if (!root) return ''
  const parts = []
  const walk = (el) => {
    for (const child of el.childNodes) {
      if (child.nodeType === 3) parts.push(child.textContent)
      else if (child.nodeType !== 1) continue
      else if (child.tagName === 'IMG' && child.dataset.name) parts.push(`[${child.dataset.name}]`)
      else if (child.tagName === 'BR') parts.push('\n')
      else walk(child)
    }
  }
  walk(root)
  return parts.join('').replace(/\n+$/, '')
}

/* ---------- 最近使用（localStorage 持久化，最多 16 个） ---------- */
const RECENT_KEY = 'wx-emoji-recents'
const RECENT_MAX = 16

export function recentWxFaces() {
  try {
    const list = JSON.parse(localStorage.getItem(RECENT_KEY))
    return Array.isArray(list) ? list.filter((n) => n in FACE_INDEX) : []
  } catch {
    return []
  }
}

export function pushRecentWxFace(name) {
  if (!(name in FACE_INDEX)) return
  const list = recentWxFaces().filter((n) => n !== name)
  list.unshift(name)
  localStorage.setItem(RECENT_KEY, JSON.stringify(list.slice(0, RECENT_MAX)))
}
