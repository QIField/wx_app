/**
 * @提及交互原型（纯静态 vanilla JS）。
 *
 * 逻辑分区（与将来 Vue 落地一一对应）：
 *  1. 会话/消息渲染          → ChatPanel.vue / MessageRow.vue
 *  2. 输入区与触发检测        → ChatComposer.vue
 *  3. 成员检索与浮层          → MentionPicker.vue + utils/mention.js
 *  4. 序列化与 at_ids 收集    → utils/emoji.js（serializeComposer 扩展）
 */
(() => {
  const M = window.MOCK
  const $ = (s, root = document) => root.querySelector(s)

  const composer = $('#composer')
  const composerWrap = $('#composerWrap')
  const pop = $('#mentionPop')
  const popList = $('#mpList')
  const popCount = $('#mpCount')
  const sendBtn = $('#sendBtn')
  const msgsEl = $('#msgs')
  const convItems = $('#convItems')
  const phEl = $('#composerPh')

  /** @ 分隔符：微信在昵称后追加 U+2005（四分空格），服务端按此识别提醒对象 */
  const AT_SEP = '\u2005'
  /** 触发符：半角 @ 与中文输入法常见的全角 ＠ */
  const AT_TRIGGER_RE = /[@＠]([^\s@＠\u2005]*)$/

  const state = {
    conv: M.conversations[0],
    isGroup: true,
    members: [],
    // 浮层状态
    open: false,
    query: '',
    lastQuery: null,
    items: [],
    active: 0,
  }

  /* ==================== 通用工具 ==================== */

  function escapeHtml(s) {
    return String(s ?? '').replace(/[&<>"']/g, (ch) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[ch]))
  }

  /** 头像底色：同一昵称恒定色相（与项目 anonStyle 同规则） */
  function avatarBg(name) {
    let h = 0
    for (const ch of String(name || '')) h = (h * 31 + ch.charCodeAt(0)) % 360
    return `hsl(${h}, 42%, 56%)`
  }

  /* ==================== 1. 会话列表 ==================== */

  function renderConvs() {
    convItems.innerHTML = M.conversations.map((c) => `
      <button type="button" class="conv-item${c.id === state.conv.id ? ' on' : ''}" data-id="${c.id}">
        <span class="c-ava group" style="background:${c.chat_type === 2 ? '#18a058' : avatarBg(c.name)}">${escapeHtml(c.name.slice(0, 1))}</span>
        <span class="c-main">
          <span class="c-top"><span class="c-name">${escapeHtml(c.name)}</span><span class="c-time num">${escapeHtml(c.last_msg_at)}</span></span>
          <span class="c-sub">${escapeHtml(c.last_msg)}</span>
        </span>
        ${c.unread ? `<span class="c-badge num">${c.unread}</span>` : ''}
      </button>
    `).join('')
    $('#convCount').textContent = String(M.conversations.length).padStart(2, '0')
  }

  convItems.addEventListener('click', (e) => {
    const btn = e.target.closest('.conv-item')
    if (!btn) return
    const conv = M.conversations.find((c) => c.id === Number(btn.dataset.id))
    if (conv) selectConv(conv)
  })

  function selectConv(conv) {
    state.conv = conv
    state.isGroup = conv.chat_type === 2
    state.members = state.isGroup ? (M.membersByConv[conv.id] || []) : []
    closePop()
    composer.innerHTML = ''
    phEl.textContent = state.isGroup
      ? '输入消息，Enter 发送…（输入 @ 提醒群成员）'
      : '输入消息，Enter 发送…'
    const hint = $('.head-hint')
    hint.innerHTML = state.isGroup ? '输入 <b>@</b> 可提醒群成员' : '单聊无需 @提醒'
    hint.classList.toggle('off', !state.isGroup)
    renderConvs()
    renderMessages()
    updateHead()
    syncDraft()
    updateStatus()
    composer.focus()
  }

  function updateHead() {
    const c = state.conv
    $('#peerName').textContent = c.name
    const tag = $('#peerTag')
    tag.textContent = c.chat_type === 2 ? '群聊' : '单聊'
    tag.classList.toggle('single', c.chat_type !== 2)
    $('#peerSub').textContent = c.chat_type === 2 ? `${state.members.length} 人` : ''
  }

  /* ==================== 2. 消息渲染 ==================== */

  function renderMessages(freshLast = false) {
    const list = M.messages[state.conv.id] || []
    msgsEl.innerHTML = list.map(renderMsg).join('')
    if (freshLast && msgsEl.lastElementChild) msgsEl.lastElementChild.classList.add('fresh')
    msgsEl.scrollTop = msgsEl.scrollHeight
  }

  function renderMsg(m) {
    if (m.type === 'time') {
      return `<div class="time-line"><span>${escapeHtml(m.label)}</span></div>`
    }
    const out = m.dir === 2
    const who = out ? M.me.name : m.sender
    return `
      <div class="msg ${out ? 'out' : 'in'}">
        <span class="m-ava" style="background:${out ? '#1d5de4' : avatarBg(who)}">${escapeHtml((who || '?').slice(0, 1))}</span>
        <div class="m-body">
          <div class="m-name">${escapeHtml(who)}${out ? '<span class="m-op">客服</span>' : ''}</div>
          <div class="m-bubble">${renderContent(m.text)}</div>
        </div>
      </div>`
  }

  /** 气泡文本：先转义再高亮 @昵称（以 U+2005 或空格结尾，防误伤普通 @ 文本） */
  function renderContent(text) {
    return escapeHtml(text).replace(/[@＠]([^@＠\s<]{1,24})(?=[\u2005\s])/g, '<span class="mention">$&</span>')
      .replaceAll(AT_SEP, '')
  }

  /* ==================== 3. 成员检索 ==================== */

  /**
   * 命中打分（越小越靠前）：0 昵称前缀 → 1 全拼前缀 → 2 首字母前缀
   * → 3 昵称包含 → 4 全拼包含 → 5 首字母包含 → -1 不命中。
   * 中文输入时 py 不会命中，走昵称规则。
   */
  function scoreOf(m, q) {
    if (!q) return 0
    const name = (m.name || '').toLowerCase()
    const py = (m.pinyin || '').toLowerCase()
    const ini = (m.initials || '').toLowerCase()
    if (name.startsWith(q)) return 0
    if (py.startsWith(q)) return 1
    if (ini.startsWith(q)) return 2
    if (name.includes(q)) return 3
    if (py.includes(q)) return 4
    if (ini.includes(q)) return 5
    return -1
  }

  function filterMembers(query) {
    const q = (query || '').trim().toLowerCase()
    return state.members
      .map((m) => ({ m, s: scoreOf(m, q) }))
      .filter((x) => x.s >= 0)
      .sort((a, b) => a.s - b.s || a.m.name.localeCompare(b.m.name, 'zh-Hans-CN'))
      .map((x) => x.m)
  }

  /** 昵称高亮：只做直接子串命中（拼音命中在拼音行上高亮，避免错位标红） */
  function nameHtml(m, q) {
    const name = m.name || ''
    const i = q ? name.toLowerCase().indexOf(q) : -1
    const tag = m.tag ? `<em class="mp-tag">${escapeHtml(m.tag)}</em>` : ''
    if (i < 0) return escapeHtml(name) + tag
    return escapeHtml(name.slice(0, i))
      + `<mark>${escapeHtml(name.slice(i, i + q.length))}</mark>`
      + escapeHtml(name.slice(i + q.length)) + tag
  }

  /** 拼音行：全拼 · 首字母；命中前缀时标黄，向用户解释"为什么搜到了" */
  function pyHtml(m, q) {
    const py = m.pinyin || ''
    const ini = m.initials || ''
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

  /* ==================== 4. 浮层渲染与键盘导航 ==================== */

  function openPop() {
    if (state.query !== state.lastQuery) {
      state.active = 0
      state.lastQuery = state.query
    }
    state.items = filterMembers(state.query)
    state.active = Math.min(state.active, Math.max(0, state.items.length - 1))
    state.open = true
    renderPop()
    placePop()
    pop.hidden = false
    updateStatus()
  }

  function renderPop() {
    popCount.textContent = state.query
      ? `${state.items.length} / ${state.members.length}`
      : `${state.members.length} 人`
    if (!state.items.length) {
      popList.innerHTML = `<div class="mp-empty">未找到「${escapeHtml(state.query)}」，换个关键词试试</div>`
      return
    }
    popList.innerHTML = state.items.map((m, i) => `
      <button type="button" class="mp-row${i === state.active ? ' on' : ''}" data-id="${m.id}" role="option" aria-selected="${i === state.active}">
        <span class="mp-ava" style="background:${avatarBg(m.name)}">${escapeHtml((m.name || '?').slice(0, 1))}</span>
        <span class="mp-main">
          <span class="mp-name">${nameHtml(m, state.query)}</span>
          <span class="mp-py">${pyHtml(m, state.query)}</span>
        </span>
        <span class="mp-enter">↵</span>
      </button>
    `).join('')
    const on = popList.querySelector('.mp-row.on')
    if (on) on.scrollIntoView({ block: 'nearest' })
  }

  /** 浮层贴近 @ 所在位置，不遮住正在输入的文字；靠右时向左翻折 */
  function placePop() {
    const wrapW = composerWrap.clientWidth
    const w = Math.min(320, wrapW - 8)
    pop.style.width = `${w}px`
    const x = caretAnchorX()
    const left = x == null ? 8 : (x - composerWrap.getBoundingClientRect().left) - 14
    pop.style.left = `${Math.max(4, Math.min(left, wrapW - w - 4))}px`
  }

  /** 取光标左侧字符的右边界（跨浏览器比 collapsed range 更可靠） */
  function caretAnchorX() {
    const sel = window.getSelection()
    if (!sel || !sel.rangeCount) return null
    const r = sel.getRangeAt(0)
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

  function setActive(i) {
    state.active = Math.max(0, Math.min(i, state.items.length - 1))
    const rows = popList.querySelectorAll('.mp-row')
    rows.forEach((r, idx) => {
      const on = idx === state.active
      r.classList.toggle('on', on)
      r.setAttribute('aria-selected', String(on))
    })
    rows[state.active]?.scrollIntoView({ block: 'nearest' })
  }

  function closePop() {
    if (!state.open) return
    state.open = false
    state.query = ''
    state.lastQuery = null
    state.items = []
    pop.hidden = true
    popList.innerHTML = ''
    updateStatus()
  }

  /* 点选：mousedown 阻止默认，输入框不丢焦点、光标不跳走 */
  popList.addEventListener('mousedown', (e) => {
    const row = e.target.closest('.mp-row')
    if (!row) return
    e.preventDefault()
    const m = state.members.find((x) => x.id === Number(row.dataset.id))
    if (m) insertMention(m)
    closePop()
  })

  popList.addEventListener('mousemove', (e) => {
    const row = e.target.closest('.mp-row')
    if (!row) return
    const idx = Number([...popList.querySelectorAll('.mp-row')].indexOf(row))
    if (idx !== state.active) setActive(idx)
  })

  /* ==================== 5. 输入区：触发 / 插入 / 序列化 ==================== */

  /** 光标的全部前置文本（跨节点），用于识别最后一个 @ 触发词 */
  function textBeforeCaret() {
    const sel = window.getSelection()
    if (!sel || !sel.rangeCount) return ''
    const r = sel.getRangeAt(0)
    if (!composer.contains(r.startContainer)) return ''
    const pre = document.createRange()
    pre.selectNodeContents(composer)
    pre.setEnd(r.startContainer, r.startOffset)
    return pre.toString()
  }

  function onInput() {
    syncDraft()
    if (!state.isGroup) return
    const m = textBeforeCaret().match(AT_TRIGGER_RE)
    if (!m) {
      closePop()
      return
    }
    state.query = m[1]
    openPop()
  }

  composer.addEventListener('input', onInput)

  composer.addEventListener('keydown', (e) => {
    // 中文输入法选词回车/方向键不参与交互
    if (e.isComposing || e.keyCode === 229) return

    if (state.open) {
      if (e.key === 'ArrowDown') { e.preventDefault(); setActive(state.active + 1); return }
      if (e.key === 'ArrowUp') { e.preventDefault(); setActive(state.active - 1); return }
      if ((e.key === 'Enter' || e.key === 'Tab') && state.items.length) {
        e.preventDefault()
        insertMention(state.items[state.active])
        closePop()
        return
      }
      if (e.key === 'Escape') { e.preventDefault(); closePop(); return }
    }

    if (e.key === 'Backspace' && removeMentionAtCaret()) {
      e.preventDefault()
      syncDraft()
      updateStatus()
      return
    }

    if (e.key === 'Enter') {
      e.preventDefault()
      if (e.shiftKey) {
        insertBreak()
        return
      }
      onSend()
    }
  })

  /* 焦点离开输入区（点到别处）才收起，点浮层本身不收起（mousedown 已阻止默认） */
  document.addEventListener('mousedown', (e) => {
    if (!state.open) return
    if (pop.contains(e.target) || composer.contains(e.target)) return
    closePop()
  })

  /** 退格原子化：整块删除 @昵称，不留半截文字 */
  function removeMentionAtCaret() {
    const sel = window.getSelection()
    if (!sel || !sel.rangeCount || !sel.isCollapsed) return false
    const r = sel.getRangeAt(0)
    let node = r.startContainer
    if (node.nodeType === 1 && node.classList.contains('mention')) {
      node.remove()
      return true
    }
    if (node.nodeType === 3 && r.startOffset === 0) {
      const prev = node.previousSibling
      if (prev && prev.nodeType === 1 && prev.classList.contains('mention')) {
        prev.remove()
        return true
      }
    }
    return false
  }

  /** Shift+Enter 换行：优先用原生命令（能正确处理光标与换行节点） */
  function insertBreak() {
    if (!document.execCommand('insertLineBreak')) {
      const sel = window.getSelection()
      if (!sel || !sel.rangeCount) return
      const r = sel.getRangeAt(0)
      r.deleteContents()
      const br = document.createElement('br')
      r.insertNode(br)
      r.setStartAfter(br)
      r.collapse(true)
      sel.removeAllRanges()
      sel.addRange(r)
    }
    syncDraft()
  }

  /**
   * 插入 @昵称：
   * 1) 在同一文本节点内把已输入的 "@关键词" 删掉（光标与 @ 必然同节点，因为中途只插过元素）
   * 2) 插入不可编辑的原子片段 <span class="mention" data-member-id>@昵称</span>
   * 3) 追加 U+2005 分隔符，光标落在其后，后续输入自然续写
   */
  function insertMention(m) {
    const sel = window.getSelection()
    if (!sel || !sel.rangeCount) return
    const r = sel.getRangeAt(0)
    const node = r.startContainer
    const off = r.startOffset

    let atIndex = -1
    if (node.nodeType === 3) {
      const before = node.data.slice(0, off)
      atIndex = Math.max(before.lastIndexOf('@'), before.lastIndexOf('＠'))
    }

    const anchor = document.createRange()
    if (atIndex >= 0) anchor.setStart(node, atIndex)
    else anchor.setStart(node.nodeType === 3 ? node : composer, node.nodeType === 3 ? off : composer.childNodes.length)
    anchor.setEnd(node.nodeType === 3 ? node : composer, node.nodeType === 3 ? off : composer.childNodes.length)
    anchor.deleteContents()
    anchor.collapse(true)

    const chip = document.createElement('span')
    chip.className = 'mention'
    chip.contentEditable = 'false'
    chip.dataset.memberId = String(m.id)
    chip.textContent = '@' + m.name

    const sep = document.createTextNode(AT_SEP)
    const frag = document.createDocumentFragment()
    frag.appendChild(chip)
    frag.appendChild(sep)
    anchor.insertNode(frag)

    const after = document.createRange()
    after.setStart(sep, 1)
    after.collapse(true)
    sel.removeAllRanges()
    sel.addRange(after)

    syncDraft()
    updateStatus()
    console.info('[mock mention]', { member_id: m.id, name: m.name })
  }

  /** 输入区 → 上行文本：mention 片段还原为 "@昵称+U+2005"，<br> → 换行 */
  function serializeComposer(root) {
    const parts = []
    const walk = (el) => {
      for (const c of el.childNodes) {
        if (c.nodeType === 3) parts.push(c.nodeValue)
        else if (c.nodeType !== 1) continue
        else if (c.tagName === 'BR') parts.push('\n')
        else if (c.classList && c.classList.contains('mention')) parts.push(c.textContent)
        else walk(c)
      }
    }
    walk(root)
    return parts.join('').replace(/\n+$/, '')
  }

  /** 从 DOM 反推被 @ 的成员（删掉片段即自动从 at_ids 移除，无脏状态） */
  function collectMentionIds(root) {
    return [...root.querySelectorAll('.mention[data-member-id]')].map((n) => Number(n.dataset.memberId))
  }

  function syncDraft() {
    const text = serializeComposer(composer)
    sendBtn.disabled = !text.trim()
    composerWrap.classList.toggle('filled', Boolean(text.trim()))
  }

  /* ==================== 6. 发送 ==================== */

  function onSend() {
    // 不做 trim：末尾 U+2005 是 @ 分隔符，trim 会把它吃掉导致微信侧识别不到提醒
    const content = serializeComposer(composer)
    if (!content.trim()) return
    const atIds = collectMentionIds(composer)

    composer.innerHTML = ''
    closePop()
    syncDraft()
    updateStatus()

    M.messages[state.conv.id].push({ dir: 2, sender: M.me.name, text: content, atIds })
    renderMessages(true)
    state.conv.last_msg = content.replaceAll(AT_SEP, '').trim()
    state.conv.last_msg_at = '刚刚'
    renderConvs()

    console.info('[mock send] payload =', { content, at_ids: atIds })
  }

  sendBtn.addEventListener('click', onSend)

  /* ==================== 7. 右侧实时状态 ==================== */

  function updateStatus() {
    $('#stConv').textContent = `${state.isGroup ? '群聊' : '单聊'} · ${state.conv.name}`
    $('#stQuery').textContent = state.open ? `@${state.query}` : '—'
    $('#stMatch').textContent = state.open ? `${state.items.length} / ${state.members.length}` : '—'
    const names = [...composer.querySelectorAll('.mention')].map((n) => n.textContent.replace(/^[@＠]/, ''))
    $('#stAts').textContent = names.length ? names.join('、') : '—'
  }

  /* ==================== 8. 启动 ==================== */

  renderConvs()
  selectConv(M.conversations[0])
  setTimeout(() => composer.focus(), 60)
})()
