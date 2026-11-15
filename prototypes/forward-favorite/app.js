/**
 * 转发与收藏 · 交互逻辑
 *
 * 结构：state（状态）→ render*（视图）→ 事件绑定（交互）
 * 数据源：window.MOCK（mock.js）+ window.API（api.js 接口桩）
 */
'use strict';

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

/* ==================== 内联 SVG 图标（统一描边风格） ==================== */
const ICO = {
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M20 6 9 17l-5-5"/></svg>',
  star: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="m12 3 2.7 5.7 6.3.8-4.6 4.3 1.2 6.2-5.6-3-5.6 3 1.2-6.2L3 9.5l6.3-.8Z"/></svg>',
  trash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>',
  eye: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>',
  doc: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6M9 13h6M9 17h6"/></svg>',
  mic: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10a7 7 0 0 0 14 0M12 19v3"/></svg>',
  link: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/></svg>',
  img: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.5-3.5L9 20"/></svg>',
  send: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 12v7a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-7"/><path d="M16 6l-4-4-4 4M12 2v13"/></svg>',
  src: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2Z"/></svg>',
};

/* ==================== 状态 ==================== */
const state = {
  convId: 21,
  leftTab: 'conv',       // conv | fav
  favFilter: 'all',
  favSelected: null,     // 收藏条目 id
  multi: false,          // 多选模式
  picked: new Set(),     // 当前会话勾选的消息 id
  picker: null,          // { targets:Set, pending:{convId, msgIds, favId} }
  modeConfirm: null,     // { targets, pending, mode } 转发方式二次确认
  justSwitched: false,   // 刚切换会话（用于瀑布浮现动画）
};

/* 头像底色（按姓名散列取色，保持稳定） */
const AVA_COLORS = ['#1d5de4', '#18a058', '#f0821e', '#8250df', '#d9445f', '#0e8aa5', '#b3562e', '#4f6bed'];
function avaColor(name) {
  let h = 0;
  for (const ch of String(name)) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return AVA_COLORS[h % AVA_COLORS.length];
}

const convById = (id) => window.MOCK.conversations.find((c) => c.id === id);
const visibleMsgs = (cid) => (window.MOCK.messages[cid] || []).filter((m) => !m._deleted);
const favItems = () => window.MOCK.favorites.filter((f) => !f.deleted);

/* ==================== Toast ==================== */
let toastTimer = null;
function toast(text, action = null) {
  const el = $('#toast');
  el.innerHTML = esc(text) + (action ? `<button class="t-act">${esc(action.label)}</button>` : '');
  if (action) $('.t-act', el).addEventListener('click', () => { hideToast(); action.run(); });
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(hideToast, action ? 5000 : 2200);
}
function hideToast() { $('#toast').classList.remove('show'); }

/* 重放 CSS 进场动画：hidden 切换不会自动重启 animation，需强制 reflow */
function replayAnim(el) {
  el.style.animation = 'none';
  void el.offsetWidth;
  el.style.animation = '';
}

/* ==================== 左栏：会话列表 ==================== */
function renderConvList() {
  const html = window.MOCK.conversations.map((c) => {
    const isGroup = c.chat_type === 2;
    const name1 = (c.name || '?')[0];
    return `
      <button class="conv-item ${c.id === state.convId ? 'on' : ''}" data-id="${c.id}">
        <span class="c-ava ${isGroup ? 'group' : ''}" style="background:${avaColor(c.name)}">${isGroup ? esc(c.name.slice(0, 2)) : esc(name1)}</span>
        <span class="c-main">
          <span class="c-top"><span class="c-name">${esc(c.name)}</span><span class="c-time num">${esc(c.last_msg_at)}</span></span>
          <span class="c-sub">${esc(c.last_msg)}</span>
        </span>
        ${c.unread ? `<span class="c-badge num">${c.unread}</span>` : ''}
      </button>`;
  }).join('');
  $('#convItems').innerHTML = html;
  $$('#convItems .conv-item').forEach((el) => {
    el.addEventListener('click', () => {
      state.convId = Number(el.dataset.id);
      exitMulti();
      state.leftTab = 'conv';
      state.justSwitched = true; // 触发一次瀑布浮现
      syncLeftTabs();
      renderAll();
    });
  });
}

/* ==================== 左栏：收藏列表 ==================== */
const FAV_TYPES = [
  { key: 'all', label: '全部' },
  { key: 'text', label: '文字' },
  { key: 'image', label: '图片' },
  { key: 'voice', label: '语音' },
  { key: 'link', label: '链接' },
  { key: 'note', label: '笔记' },
];

function favPreview(f) {
  if (f.type === 'text') return f.content;
  if (f.type === 'image') return `[图片] ${f.title || ''}`;
  if (f.type === 'voice') return `[语音] ${f.duration}`;
  if (f.type === 'link') return f.title;
  if (f.type === 'note') return f.title;
  return '[消息]';
}
function favIcon(type) {
  return { text: ICO.doc, image: ICO.img, voice: ICO.mic, link: ICO.link, note: ICO.doc }[type] || ICO.doc;
}

function renderFavList() {
  // 分类 chips
  $('#favChips').innerHTML = FAV_TYPES.map((t) =>
    `<button type="button" class="chip ${state.favFilter === t.key ? 'on' : ''}" data-k="${t.key}">${t.label}</button>`
  ).join('');
  $$('#favChips .chip').forEach((el) => el.addEventListener('click', () => {
    state.favFilter = el.dataset.k;
    renderFavList();
  }));

  // 列表
  const items = favItems().filter((f) => state.favFilter === 'all' || f.type === state.favFilter);
  $('#favItems').innerHTML = items.length
    ? items.map((f) => `
      <button class="fav-item ${state.favSelected === f.id ? 'on' : ''}" data-id="${f.id}">
        <span class="f-ico">${favIcon(f.type)}</span>
        <span class="f-main">
          <span class="f-line1">${esc(favPreview(f))}</span>
          <span class="f-line2 num">${esc(f.source)} · ${esc(f.time)}</span>
        </span>
      </button>`).join('')
    : `<div class="f-empty">${ICO.star}<p>暂无此类收藏</p></div>`;

  $$('#favItems .fav-item').forEach((el) => el.addEventListener('click', () => {
    state.favSelected = el.dataset.id;
    renderFavList();
    renderFavDetail();
  }));

  // 顶栏徽标
  $('#favBadge').textContent = favItems().length;
}

/* ==================== 中栏：收藏详情 ==================== */
function renderFavDetail() {
  const wrap = $('#favDetail');
  const f = favItems().find((x) => x.id === state.favSelected);
  if (!f) {
    wrap.innerHTML = `
      <div class="fd-empty">
        ${ICO.star}
        <p>在聊天中右键消息 → 收藏，内容会出现在这里</p>
      </div>`;
    return;
  }

  let body = '';
  if (f.type === 'text') body = `<div class="fd-text">${esc(f.content)}</div>`;
  if (f.type === 'image') body = `
    <div class="fd-image">
      ${FD_IMAGE_SVG}
      <div class="fd-caption">${esc(f.title || '图片')}</div>
    </div>`;
  if (f.type === 'voice') body = `
    <div class="fd-voice" id="fdVoice">
      ${ICO.mic}
      <span class="v-dur">${esc(f.duration)}</span>
      <span class="v-wave">${Array.from({ length: 14 }, (_, i) => `<i style="height:${3 + ((i * 7) % 9)}px"></i>`).join('')}</span>
    </div>`;
  if (f.type === 'link') body = `
    <div class="fd-link">
      <div class="l-bar">${ICO.link}</div>
      <div class="l-main">
        <div class="l-title">${esc(f.title)}</div>
        <div class="l-desc">${esc(f.desc || '')}</div>
      </div>
    </div>`;
  if (f.type === 'note') body = `
    <div class="fd-note">
      <div class="n-title">${esc(f.title)}</div>
      <div class="n-text">${esc(f.excerpt || '')}</div>
    </div>`;

  wrap.innerHTML = `
    <div class="fd-card">
      <div class="fd-body">${body}</div>
      <div class="fd-meta">
        <span class="fd-src">${ICO.src} 来源：${esc(f.source)} · ${esc(f.time)}</span>
        ${f.tags && f.tags.length ? `<span class="fd-tags">${f.tags.map((t) => `<span class="t">${esc(t)}</span>`).join('')}</span>` : ''}
      </div>
      <div class="fd-actions">
        <button type="button" class="btn ghost" id="fdDel">${ICO.trash.replace('<svg', '<svg width="13" height="13" style="vertical-align:-2px;margin-right:4px"')}删除</button>
        <button type="button" class="btn primary" id="fdForward">${ICO.send.replace('<svg', '<svg width="13" height="13" style="vertical-align:-2px;margin-right:4px"')}转发给朋友</button>
      </div>
    </div>`;

  $('#fdForward').addEventListener('click', () => openPicker({ convId: state.convId, favId: f.id }));
  $('#fdDel').addEventListener('click', () => askConfirm({
    title: '删除这条收藏？',
    text: '删除后移入回收站，可在管理端恢复（软删除）。',
    ok: async () => {
      await window.API.deleteFavorite(f.id);
      state.favSelected = null;
      renderFavList();
      renderFavDetail();
      toast('已删除 · 可在回收站恢复');
    },
  }));
  const vBtn = $('#fdVoice');
  if (vBtn) vBtn.addEventListener('click', () => toast('语音播放为演示占位'));
}

/* 收藏图片详情的内联 SVG 插画（离线可用，非外链占位图） */
const FD_IMAGE_SVG = `
<svg viewBox="0 0 480 300" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="fdsky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#3a6fd8"/><stop offset="1" stop-color="#9db9f5"/>
    </linearGradient>
  </defs>
  <rect width="480" height="300" fill="url(#fdsky)"/>
  <circle cx="380" cy="70" r="34" fill="#ffe9a8"/>
  <path d="M0 220 L110 120 L190 210 L260 150 L340 230 L480 170 L480 300 L0 300 Z" fill="#274a86"/>
  <path d="M0 260 L90 200 L200 262 L300 215 L410 268 L480 240 L480 300 L0 300 Z" fill="#16233c"/>
  <rect x="60" y="236" width="90" height="46" rx="4" fill="#d9dee9"/>
  <rect x="70" y="246" width="26" height="20" rx="2" fill="#5a7dc9"/>
  <rect x="104" y="246" width="26" height="20" rx="2" fill="#5a7dc9"/>
</svg>`;

/* ==================== 中栏：聊天窗 ==================== */
function renderChat() {
  const conv = convById(state.convId);
  const isGroup = conv.chat_type === 2;

  $('#peerName').textContent = conv.name;
  $('#peerTag').textContent = isGroup ? '群聊' : '单聊';
  $('#peerSub').textContent = isGroup && conv.member_count ? `${conv.member_count} 位成员` : (conv.alias ? `ID ${conv.alias}` : '');

  const frag = document.createDocumentFragment();
  const msgs = visibleMsgs(state.convId);
  const reveal = state.justSwitched; // 切会话时瀑布浮现一次
  state.justSwitched = false;
  let rowCount = 0;

  if (!msgs.length) {
    const empty = document.createElement('div');
    empty.className = 'f-empty';
    empty.innerHTML = '<p>暂无消息</p>';
    $('#msgs').replaceChildren(empty);
    return;
  }

  for (const m of msgs) {
    if (m.type === 'time') {
      const t = document.createElement('div');
      t.className = 'time-chip';
      t.innerHTML = `<span>${esc(m.label)}</span>`;
      frag.appendChild(t);
      continue;
    }

    const row = document.createElement('div');
    row.className = `msg-row dir${m.dir}` + (state.picked.has(m.id) ? ' picked' : '');
    row.dataset.id = m.id;
    if (reveal) {
      // 页面加载编排：仅切换会话这一瞬间，按行递进 30ms，封顶 320ms
      row.classList.add('reveal');
      row.style.animationDelay = `${Math.min(rowCount * 30, 320)}ms`;
      rowCount++;
    }

    const sender = m.sender || '';
    const checkbox = state.multi
      ? `<span class="m-check">${ICO.check}</span>`
      : '';
    const name = isGroup && m.dir === 1 ? `<span class="m-sender">${esc(sender)}</span>` : '';

    let bubbleHtml = '';
    if (m.type === 'forward_card') {
      const c = m.card;
      bubbleHtml = `
        <div class="fwd-card" data-act="view">
          <div class="fwd-title">${esc(c.title)}</div>
          <div class="fwd-preview">${c.preview.map((p) => `<span>${esc(p)}</span>`).join('')}</div>
          <div class="fwd-foot">${ICO.eye} 查看 ${c.count} 条转发消息</div>
        </div>`;
    } else {
      // @ 提及原子片段高亮（U+2005 分隔，延续项目规范）
      bubbleHtml = `<div class="bubble">${esc(m.text).replace(/@([^@\u2005]+)\u2005/g, '<span class="at-frag">@$1\u2005</span>')}</div>`;
    }

    row.innerHTML = `
      ${checkbox}
      <span class="m-ava" style="background:${avaColor(sender)}">${esc(sender[0] || '?')}</span>
      <span class="m-main">${name}${bubbleHtml}</span>`;

    // 右键 / 长按 → 气泡菜单
    row.addEventListener('contextmenu', (e) => { e.preventDefault(); openCtxMenu(e.clientX, e.clientY, m, row); });
    row.addEventListener('pointerdown', (e) => {
      if (e.button !== 0) return;
      const timer = setTimeout(() => openCtxMenu(e.clientX, e.clientY, m, row), 480);
      const clear = () => clearTimeout(timer);
      row.addEventListener('pointerup', clear, { once: true });
      row.addEventListener('pointerleave', clear, { once: true });
    });

    // 多选模式下点击整行切换勾选
    if (state.multi) {
      row.addEventListener('click', () => togglePick(m.id));
    } else if (m.type === 'forward_card') {
      $('.fwd-card', row).addEventListener('click', () => openViewer(m.card));
    }

    frag.appendChild(row);
  }
  $('#msgs').replaceChildren(frag);
  $('#msgs').scrollTop = $('#msgs').scrollHeight;
}

/* ==================== 多选模式 ==================== */
function enterMulti(firstMsgId) {
  state.multi = true;
  state.picked = new Set(firstMsgId ? [firstMsgId] : []);
  $('#multiBar').hidden = false;
  $('#mbAll').checked = false;
  renderChat();
  syncMultiBar();
}
function exitMulti() {
  state.multi = false;
  state.picked = new Set();
  $('#multiBar').hidden = true;
  renderChat();
  syncMultiBar();
}
function togglePick(id) {
  state.picked.has(id) ? state.picked.delete(id) : state.picked.add(id);
  renderChat();
  syncMultiBar();
}
function syncMultiBar() {
  const n = state.picked.size;
  $('#mbCount').textContent = `已选 ${n} 条`;
  $('#mbForward').disabled = n === 0;
}

/* ==================== 气泡右键菜单（微信同款深色） ==================== */
const MENU_ITEMS = [
  { key: 'copy', label: '复制' },
  { key: 'forward', label: '转发', isNew: true },
  { key: 'fav', label: '收藏', isNew: true },
  { key: 'multi', label: '多选' },
  { key: 'del', label: '删除', danger: true },
];

function openCtxMenu(x, y, msg, row) {
  if (state.multi) return;          // 多选模式下不再弹菜单
  hideCtxMenu();
  $$('.msg-row.menu-open').forEach((el) => el.classList.remove('menu-open'));
  row.classList.add('menu-open');

  const menu = $('#ctxMenu');
  menu.innerHTML = MENU_ITEMS.map((it) => `
    <button type="button" data-k="${it.key}" class="${it.danger ? 'is-danger' : ''}">
      ${it.label}${it.isNew ? '<em class="new-badge">新</em>' : ''}
    </button>`).join('');
  menu.hidden = false;
  replayAnim(menu); // 菜单每次弹出都重放动画

  // 边缘翻转：保证菜单完整可见
  const mw = menu.offsetWidth, mh = menu.offsetHeight;
  menu.style.left = Math.min(x, window.innerWidth - mw - 8) + 'px';
  menu.style.top = Math.min(y, window.innerHeight - mh - 8) + 'px';

  $$('#ctxMenu button').forEach((btn) => btn.addEventListener('click', () => {
    hideCtxMenu();
    row.classList.remove('menu-open');
    handleMenu(btn.dataset.k, msg);
  }));
}
function hideCtxMenu() { $('#ctxMenu').hidden = true; }

async function handleMenu(key, msg) {
  switch (key) {
    case 'copy': {
      const text = msg.text || (msg.card ? msg.card.preview.join('\n') : '');
      await navigator.clipboard?.writeText(text).catch(() => {});
      toast('已复制到剪贴板');
      break;
    }
    case 'forward':
      openPicker({ convId: state.convId, msgIds: [msg.id] });
      break;
    case 'fav': {
      const item = await window.API.addFavorite({ convId: state.convId, msgId: msg.id });
      renderFavList();
      toast(`已收藏 · 来自「${item.source}」`, { label: '查看', run: () => switchLeftTab('fav') });
      break;
    }
    case 'multi':
      enterMulti(msg.id);
      break;
    case 'del':
      askConfirm({
        title: '删除这条消息？',
        text: '删除后移入回收站，可在管理端恢复（软删除）。',
        ok: async () => {
          await window.API.deleteMessages(state.convId, [msg.id]);
          state.picked.delete(msg.id);
          renderConvList();
          renderChat();
          syncMultiBar();
          toast('已删除 · 可在回收站恢复');
        },
      });
      break;
  }
}

/* ==================== 合并转发回看（快照） ==================== */
function openViewer(card) {
  $('#crTitle').textContent = card.title;
  $('#crBody').innerHTML = card.snapshot.map((m) => `
    <div class="cr-line">
      <div class="who">${esc(m.sender)}</div>
      <div class="what">${esc(m.text)}</div>
    </div>`).join('');
  $('#viewerMask').hidden = false;
}

/* ==================== 确认弹窗 ==================== */
let confirmCb = null;
function askConfirm({ title, text, ok }) {
  $('#cfTitle').textContent = title;
  $('#cfText').textContent = text;
  confirmCb = ok;
  $('#confirmMask').hidden = false;
}

/* ==================== 转发选择器 ==================== */
function openPicker(pending) {
  state.picker = { targets: new Set(), pending };
  $('#fpSearch').value = '';
  $('#fpTip').textContent = pending.favId
    ? '转发收藏内容到目标会话'
    : '选好后点击发送';
  renderRecentRow();
  renderPickerList('');
  syncPickerFoot();
  $('#pickerMask').hidden = false;
  replayAnim($('.fp', $('#pickerMask')));
  setTimeout(() => $('#fpSearch').focus(), 30);
}
function closePicker() { $('#pickerMask').hidden = true; state.picker = null; }

function renderRecentRow() {
  const row = $('#fpRecentRow');
  row.innerHTML = window.MOCK.recentForwardIds
    .map((id) => convById(id))
    .filter(Boolean)
    .map((c) => `
      <div class="r-item" data-id="${c.id}">
        <span class="c-ava" style="background:${avaColor(c.name)}">${esc(c.name[0])}</span>
        <span>${esc(c.name)}</span>
      </div>`).join('');
  $$('.r-item', row).forEach((el) => el.addEventListener('click', () => {
    toggleTarget(Number(el.dataset.id));
    renderRecentRow();
    renderPickerList($('#fpSearch').value.trim());
    syncPickerFoot();
  }));
  // 同步选中态
  $$('.r-item', row).forEach((el) => {
    if (state.picker?.targets.has(Number(el.dataset.id))) el.classList.add('picked');
  });
}

/**
 * 三路搜索：昵称 > 全拼 > 首字母，按匹配优先级排序（延续 @ 功能规范）。
 * 群聊仅按名称匹配。
 */
function searchTargets(q) {
  if (!q) return window.MOCK.conversations.filter((c) => c.id !== state.convId);
  const lower = q.toLowerCase();
  const scored = [];
  for (const c of window.MOCK.conversations) {
    if (c.id === state.convId) continue;
    let rank = -1;
    if (c.name.toLowerCase().includes(lower)) rank = 0;
    else if (c.pinyin && c.pinyin.includes(lower)) rank = 1;
    else if (c.initials && c.initials.startsWith(lower)) rank = 2;
    if (rank >= 0) scored.push({ c, rank });
  }
  scored.sort((a, b) => a.rank - b.rank);
  return scored.map((s) => s.c);
}

function renderPickerList(q) {
  const list = $('#fpList');
  const targets = searchTargets(q);

  if (!targets.length) {
    list.innerHTML = `<div class="fp-nomore">没有匹配的会话</div>`;
    return;
  }

  // 空搜索时按拼音首字母分组（仿微信联系人字母索引）
  let html = '';
  if (!q) {
    const groups = new Map();
    for (const c of targets) {
      const letter = (c.pinyin ? c.pinyin[0] : c.name[0]).toUpperCase();
      if (!groups.has(letter)) groups.set(letter, []);
      groups.get(letter).push(c);
    }
    for (const [letter, arr] of [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0]))) {
      html += `<div class="fp-group num">${letter}</div>`;
      html += arr.map((c) => pickerRowHtml(c)).join('');
    }
  } else {
    html = targets.map((c) => pickerRowHtml(c)).join('');
  }
  list.innerHTML = html;

  $$('.fp-row', list).forEach((el) => el.addEventListener('click', () => {
    toggleTarget(Number(el.dataset.id));
    renderPickerList(q);
    renderRecentRow();
    syncPickerFoot();
  }));
}

function pickerRowHtml(c) {
  const isGroup = c.chat_type === 2;
  const picked = state.picker?.targets.has(c.id);
  return `
    <button class="fp-row ${picked ? 'picked' : ''}" data-id="${c.id}">
      <span class="c-ava ${isGroup ? 'group' : ''}" style="background:${avaColor(c.name)}">${isGroup ? esc(c.name.slice(0, 2)) : esc(c.name[0])}</span>
      <span class="fp-name">${esc(c.name)}</span>
      ${isGroup ? '<span class="tag">群聊</span>' : ''}
      <span class="fp-box">${ICO.check}</span>
    </button>`;
}

function toggleTarget(id) {
  const t = state.picker.targets;
  t.has(id) ? t.delete(id) : t.add(id);
}

function syncPickerFoot() {
  const n = state.picker.targets.size;
  const pending = state.picker.pending;
  const multiMsgs = !pending.favId && pending.msgIds.length > 1;

  // 微信逻辑：多选消息必须先选转发方式，选择器内不再放 radio
  $('#fpTip').textContent = pending.favId
    ? '转发收藏内容到目标会话'
    : multiMsgs
      ? '发送后将选择转发方式'
      : '选好后点击发送';

  const btn = $('#fpSend');
  btn.textContent = `发送(${n})`;
  btn.disabled = n === 0;
}

/* 发送：多选消息 → 无论几个目标都先选转发方式；单条消息直接发送 */
function onPickerSend() {
  const { targets, pending } = state.picker;
  if (!targets.size) return;
  const multiMsgs = !pending.favId && pending.msgIds.length > 1;

  if (multiMsgs) {
    state.modeConfirm = { targets, pending, mode: 'merge' };
    $('#fmSub').textContent = `将 ${pending.msgIds.length} 条消息转发给 ${targets.size} 个会话`;
    $$('.fm-opt').forEach((el) => el.classList.toggle('on', el.dataset.mode === 'merge'));
    $('#pickerMask').hidden = true;
    $('#modeMask').hidden = false;
    replayAnim($('.fm', $('#modeMask')));
    return;
  }
  // 单条消息：普通气泡直接送达，无需选择方式
  doForward('single');
}

async function doForward(mode) {
  const { targets, pending } = state.modeConfirm || state.picker;

  await window.API.forwardMessages({
    convId: pending.convId,
    msgIds: pending.msgIds || [],
    favId: pending.favId || null,
    targetIds: [...targets],
    mode,
  });

  const firstTarget = convById([...targets][0]);
  const names = [...targets].map((id) => convById(id)?.name).filter(Boolean);
  $('#modeMask').hidden = true;
  state.modeConfirm = null;
  closePicker();
  exitMulti();
  renderConvList();
  renderChat();
  renderFavList();

  toast(
    names.length === 1 ? `已转发给 ${names[0]}` : `已转发给 ${names.length} 个会话`,
    { label: '查看', run: () => { state.convId = firstTarget.id; renderConvList(); renderChat(); } }
  );
}

/* ==================== 左栏 Tab 切换 ==================== */
function switchLeftTab(tab) {
  state.leftTab = tab;
  syncLeftTabs();
}
function syncLeftTabs() {
  $$('#leftTabs button').forEach((b) => b.classList.toggle('on', b.dataset.tab === state.leftTab));
  $('#paneConv').hidden = state.leftTab !== 'conv';
  $('#paneFav').hidden = state.leftTab !== 'fav';
  $('#viewChat').hidden = state.leftTab !== 'conv';
  $('#viewFav').hidden = state.leftTab !== 'fav';
  if (state.leftTab === 'conv') { renderConvList(); renderChat(); }
  if (state.leftTab === 'fav') { renderFavList(); renderFavDetail(); }
}

/* ==================== 总渲染 ==================== */
function renderAll() {
  renderConvList();
  renderChat();
  renderFavList();
}

/* ==================== 事件绑定 ==================== */
function bindEvents() {
  // 左栏 Tab
  $$('#leftTabs button').forEach((b) => b.addEventListener('click', () => switchLeftTab(b.dataset.tab)));

  // 多选操作条
  $('#mbCancel').addEventListener('click', exitMulti);
  $('#mbAll').addEventListener('change', (e) => {
    const ids = visibleMsgs(state.convId).filter((m) => m.type !== 'time').map((m) => m.id);
    state.picked = e.target.checked ? new Set(ids) : new Set();
    renderChat();
    syncMultiBar();
  });
  $('#mbForward').addEventListener('click', () => {
    if (!state.picked.size) return;
    openPicker({ convId: state.convId, msgIds: [...state.picked] });
  });

  // 转发选择器
  $('#fpClose').addEventListener('click', closePicker);
  $('#fpCancel').addEventListener('click', closePicker);
  $('#fpSend').addEventListener('click', onPickerSend);
  $('#fpSearch').addEventListener('input', (e) => renderPickerList(e.target.value.trim()));

  // 转发方式确认（微信同款：选完人再选方式）
  $$('.fm-opt').forEach((el) => el.addEventListener('click', () => {
    state.modeConfirm.mode = el.dataset.mode;
    $$('.fm-opt').forEach((o) => o.classList.toggle('on', o === el));
  }));
  $('#fmOk').addEventListener('click', () => {
    if (state.modeConfirm) doForward(state.modeConfirm.mode);
  });
  // 取消 = 退回选择器继续挑人
  const backToPicker = () => {
    $('#modeMask').hidden = true;
    $('#pickerMask').hidden = false;
  };
  $('#fmCancel').addEventListener('click', backToPicker);

  // 快照回看
  $('#crClose').addEventListener('click', () => { $('#viewerMask').hidden = true; });

  // 确认弹窗
  $('#cfCancel').addEventListener('click', () => { $('#confirmMask').hidden = true; confirmCb = null; });
  $('#cfOk').addEventListener('click', async () => {
    $('#confirmMask').hidden = true;
    if (confirmCb) await confirmCb();
    confirmCb = null;
  });

  // 遮罩点击关闭 + Esc 兜底（方式确认页 Esc 退回选择器）
  [$('#pickerMask'), $('#viewerMask'), $('#confirmMask')].forEach((mask) => {
    mask.addEventListener('click', (e) => { if (e.target === mask) mask.hidden = true; });
  });
  $('#modeMask').addEventListener('click', (e) => { if (e.target === $('#modeMask')) backToPicker(); });
  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    hideCtxMenu();
    [$('#pickerMask'), $('#viewerMask'), $('#confirmMask')].forEach((m) => { m.hidden = true; });
    if (!$('#modeMask').hidden) backToPicker();
  });
  document.addEventListener('click', (e) => {
    // 点击菜单/消息行以外区域关闭右键菜单
    if (!e.target.closest('.ctxmenu') && !e.target.closest('.msg-row')) {
      hideCtxMenu();
      $$('.msg-row.menu-open').forEach((el) => el.classList.remove('menu-open'));
    }
  });
}

/* ==================== 启动 ==================== */
function init() {
  // 为存量消息补发稳定 id（真实接口出参自带 id，此处仅演示兜底）
  for (const [cid, list] of Object.entries(window.MOCK.messages)) {
    list.forEach((m, i) => { if (!m.id) m.id = `${cid}-${i}`; });
  }
  bindEvents();
  renderAll();
  renderFavDetail();
}
init();
