/* ===== textSelection.js · 聊天区自定义文本选中引擎 =====
 *
 * .msgs 区已禁用浏览器原生选择（user-select:none），由本引擎接管全部选中交互：
 * - 仅当用户在文本容器（.content / .q-text）内左键拖动位移 ≥3px 才形成选中（点击不清选）
 * - 高亮走 CSS Custom Highlight API（Chrome/Edge 105+ / FF 139+ / Safari 17.2+）：
 *   不包裹 span、不破坏 v-html/表情图结构，Range 自动跟随滚动与缩放
 * - 右键不清除选中（mousedown 只认左键）；复制归属用 msgId 对比判断
 * - 点击文本容器清除选中；点击气泡非文本区域（padding/头像/空白/卡片）保留选中
 *
 * 全局同一时刻只有一个选中（模块级单例）；不支持 Highlight API 时引擎不激活，
 * 复制行为退化为全文兜底（可接受降级，避免双路径并存）。
 */

const HL_NAME = 'chat-text-sel'
const CLICK_EPS = 3 // 位移阈值：小于视为纯点击

/* ---------- 可用性检测 ---------- */
export function isSupported() {
  return typeof window !== 'undefined'
    && typeof window.Highlight !== 'undefined'
    && !!window.CSS?.highlights
}

/* ---------- 单例选中状态 ----------
 * sel:    { msgId, text, range, containerEl } | null —— text 在定型瞬间快照，复制不依赖 Range 存活
 * drag:   拖动中的临时状态（anchor/last 端点 + 一次性挂载的 document 监听） */
let sel = null
let drag = null

/** 读取当前选中；容器已被 DOM 重建（切会话/消息刷新）时自愈清空 */
export function getSelectionState() {
  if (sel && (!sel.containerEl.isConnected || !sel.containerEl.contains(sel.range.startContainer))) {
    clearSelection()
  }
  return sel
}

export function clearSelection() {
  // 无条件删高亮（幂等）：拖动中已设高亮但最终 collapsed/未形成选中时同样要清掉，防残留
  window.CSS?.highlights?.delete(HL_NAME)
  sel = null
}

/** 右键复制取值：选中归属该消息才返回片段文本，否则空串（调用方兜底全文） */
export function copyFragmentOf(msgId) {
  return fragmentOf(getSelectionState(), msgId)
}

/** 纯函数版归属判断（供单测注入） */
export function fragmentOf(state, msgId) {
  return state && state.msgId === msgId ? state.text : ''
}

/* ---------- caret 归一：caretPositionFromPoint（标准）优先，caretRangeFromPoint 兜底 ---------- */
function caretFromPoint(x, y) {
  if (document.caretPositionFromPoint) {
    const pos = document.caretPositionFromPoint(x, y)
    return pos ? { node: pos.offsetNode, offset: pos.offset } : null
  }
  if (document.caretRangeFromPoint) {
    const r = document.caretRangeFromPoint(x, y)
    return r ? { node: r.startContainer, offset: r.startOffset } : null
  }
  return null
}

/* 两个 caret 的 document 顺序：a 在 b 前返回 <0 */
function compareCaret(a, b) {
  const ra = document.createRange()
  ra.setStart(a.node, a.offset)
  ra.setEnd(a.node, a.offset)
  const rb = document.createRange()
  rb.setStart(b.node, b.offset)
  rb.setEnd(b.node, b.offset)
  return ra.compareBoundaryPoints(Range.START_TO_START, rb)
}

/* 容器内第一个/最后一个文本节点边界（clamp 与拖动越界兜底用） */
function boundaryOf(el, first) {
  const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT)
  let node = null
  if (first) {
    node = walker.nextNode()
    if (node) return { node, offset: 0 }
  } else {
    while (walker.nextNode()) node = walker.currentNode
    if (node) return { node, offset: node.nodeValue.length }
  }
  return null
}

/* 把拖动端点约束在起始容器文本范围内：出容器则按方向取容器首/尾（实现跨气泡拖动 clamp）。
   首尾文本边界在 mousedown 时预计算缓存于 drag，mousemove 高频路径不再每次 TreeWalker 全遍历 */
function clampCaretInto(caret, drag) {
  const { head, tail } = drag
  if (!head || !tail) return null
  if (caret && caret.node && drag.containerEl.contains(caret.node)) return caret
  if (!caret || !caret.node) return head
  return compareCaret(caret, head) < 0 ? head : tail
}

/* 用 anchor/last 两个端点构造文档序 Range（自动处理前后向） */
function buildRange(anchor, last, drag) {
  const a = clampCaretInto(anchor, drag)
  const b = clampCaretInto(last, drag)
  if (!a || !b) return null
  const range = document.createRange()
  if (compareCaret(a, b) <= 0) {
    range.setStart(a.node, a.offset)
    range.setEnd(b.node, b.offset)
  } else {
    range.setStart(b.node, b.offset)
    range.setEnd(a.node, a.offset)
  }
  return range
}

/* ---------- 拖动状态机：mousedown（左键，文本容器内）→ mousemove → mouseup ---------- */
export function onTextMouseDown(e, msgId) {
  if (!isSupported() || e.button !== 0) return
  const containerEl = e.currentTarget
  const anchor = caretFromPoint(e.clientX, e.clientY)
  if (!anchor || !anchor.node) return
  drag = {
    msgId,
    containerEl,
    anchor,
    startX: e.clientX,
    startY: e.clientY,
    range: null,
    // 容器首/尾文本边界一次预计算：拖动越界 clamp 的高频路径零遍历
    head: boundaryOf(containerEl, true),
    tail: boundaryOf(containerEl, false),
  }
  document.addEventListener('mousemove', onDragMove)
  document.addEventListener('mouseup', onDragEnd)
}

function onDragMove(e) {
  if (!drag) return
  const last = caretFromPoint(e.clientX, e.clientY)
  if (!last || !last.node) return
  const range = buildRange(drag.anchor, last, drag)
  if (!range) return
  drag.range = range
  window.CSS.highlights.set(HL_NAME, new window.Highlight(range))
}

function onDragEnd(e) {
  document.removeEventListener('mousemove', onDragMove)
  document.removeEventListener('mouseup', onDragEnd)
  const d = drag
  drag = null
  if (!d) return
  const moved = Math.hypot(e.clientX - d.startX, e.clientY - d.startY)
  if (moved < CLICK_EPS) {
    // 纯点击文本区：清除已有选中（点非文本区域不经过这里，选中保留）
    clearSelection()
    return
  }
  const range = d.range || buildRange(d.anchor, caretFromPoint(e.clientX, e.clientY) || d.anchor, d)
  if (!range || range.collapsed) {
    clearSelection()
    return
  }
  window.CSS.highlights.set(HL_NAME, new window.Highlight(range))
  sel = {
    msgId: d.msgId,
    text: extractRangeText(range),
    range,
    containerEl: d.containerEl,
  }
}

/* ---------- 双击选词（英文词/连续数字/连续 CJK），仅作用于单个文本节点 ---------- */
export function onTextDblClick(e, msgId) {
  if (!isSupported() || e.button !== 0) return
  const containerEl = e.currentTarget
  const caret = caretFromPoint(e.clientX, e.clientY)
  if (!caret || caret.node.nodeType !== 3 || !containerEl.contains(caret.node)) {
    clearSelection()
    return
  }
  const text = caret.node.nodeValue
  const w = wordRangeAt(text, caret.offset) || (caret.offset > 0 ? wordRangeAt(text, caret.offset - 1) : null)
  if (!w) {
    clearSelection()
    return
  }
  const range = document.createRange()
  range.setStart(caret.node, w.start)
  range.setEnd(caret.node, w.end)
  window.CSS.highlights.set(HL_NAME, new window.Highlight(range))
  sel = { msgId, text: extractRangeText(range), range, containerEl }
}

/* ---------- 全局生命周期：Esc 清选 / 失焦清选 ---------- */
function onKeydown(e) {
  if (e.key === 'Escape') clearSelection()
}

export function attachTextSelection() {
  document.addEventListener('keydown', onKeydown)
  window.addEventListener('blur', clearSelection)
}

export function detachTextSelection() {
  document.removeEventListener('keydown', onKeydown)
  window.removeEventListener('blur', clearSelection)
  document.removeEventListener('mousemove', onDragMove)
  document.removeEventListener('mouseup', onDragEnd)
  clearSelection()
}

/* ---------- 文本提取：遍历 Range 内容，表情图读 alt 还原 [码] ----------
 * segs 结构 [{type:'text', value}] / [{type:'emoji', value}]（value 已含方括号），纯函数可测 */
export function textFromSegments(segs) {
  return segs.map((s) => s.value).join('')
}

function rangeToSegments(range) {
  const frag = range.cloneContents()
  const segs = []
  const walk = (node) => {
    for (const child of node.childNodes) {
      if (child.nodeType === 3) {
        segs.push({ type: 'text', value: child.nodeValue })
      } else if (child.nodeType === 1) {
        if (child.tagName === 'IMG' && child.classList.contains('wx-emoji')) {
          segs.push({ type: 'emoji', value: child.getAttribute('alt') || '' })
        } else {
          walk(child)
        }
      }
    }
  }
  walk(frag)
  return segs
}

export function extractRangeText(range) {
  return textFromSegments(rangeToSegments(range))
}

/* ---------- 纯函数：词边界扩展（双击选词） ----------
 * 英文/数字/下划线连续段或 CJK 连续段；offset 落空白/标点返回 null。
 * 文本序列与 offset 同坐标系（单文本节点内） */
export function wordRangeAt(text, offset) {
  if (!text || offset < 0 || offset >= text.length) return null
  const isWord = (c) => /[A-Za-z0-9_]/.test(c)
  const isCJK = (c) => /[\u4e00-\u9fff]/.test(c)
  const kind = isWord(text[offset]) ? isWord : isCJK(text[offset]) ? isCJK : null
  if (!kind) return null
  let s = offset
  let e = offset + 1
  while (s > 0 && kind(text[s - 1])) s--
  while (e < text.length && kind(text[e])) e++
  return { start: s, end: e }
}
