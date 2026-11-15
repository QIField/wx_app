/* app.js — 状态、渲染与交互逻辑（纯前端演示，无真实后端）。
 * 核心：locateUnread() —— 会话视图已激活时再次点击「会话」图标（双击的第二击），
 * 依次定位下一条未读会话，最小滚动把它带进可视区域（不顶到列表最上方）。
 * 该函数与 ConvList.vue 的 defineExpose({ locateUnread }) 一一对应，可平移。 */

/* ---------- 状态（集中管理，视图跟随状态） ---------- */
const state = {
  view: 'chat',           // chat | contacts
  lastLocatedId: null,    // 上一次定位到的会话 id：实现「下一条未读」循环定位
  keyword: '',
  currentId: null,        // 当前选中会话（演示：进入即清零）
  convs: structuredClone(INITIAL_CONVS),
};

/* ---------- 常量 ---------- */
const GRADS = [
  'linear-gradient(135deg,#2f6ff0,#6d4de0)',
  'linear-gradient(135deg,#18a058,#0c6e3d)',
  'linear-gradient(135deg,#f0821e,#d9531e)',
  'linear-gradient(135deg,#8a5cf6,#5b3fd6)',
  'linear-gradient(135deg,#0ea5b7,#036e7d)',
  'linear-gradient(135deg,#e5484d,#b02540)',
];
/* 免打扰铃铛斜杠（真实 ConvList.vue 同款 Lucide 图形） */
const MUTE_SVG =
  '<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13.73 21a2 2 0 0 1-3.46 0"/><path d="M18.63 13A17.89 17.89 0 0 1 18 8"/><path d="M6.26 6.26A5.86 5.86 0 0 0 6 8c0 7-3 9-3 9h14"/><path d="M18 8a6 6 0 0 0-9.33-5"/><line x1="1" y1="1" x2="23" y2="23"/></svg>';
const GROUP_SVG =
  '<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>';

/* ---------- DOM 引用 ---------- */
const $ = (sel) => document.querySelector(sel);
const railChat = $('#railChat');
const railContacts = $('#railContacts');
const railBadge = $('#railBadge');
const chatView = $('#chatView');
const contactsView = $('#contactsView');
const searchInput = $('#searchInput');
const convItems = $('#convItems');
const chatAvatar = $('#chatAvatar');
const chatTitle = $('#chatTitle');
const chatSub = $('#chatSub');
const chatBubbles = $('#chatBubbles');
const chatHint = $('#chatHint');
const toastEl = $('#toast');

/* ---------- 工具 ---------- */
let toastTimer = null;
function toast(text) {
  toastEl.textContent = text;
  toastEl.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastEl.classList.remove('show'), 1800);
}

/** 当前搜索过滤后的会话（真实端对应 ConvList 的 filtered computed）。 */
function visibleConvs() {
  const kw = state.keyword.trim().toLowerCase();
  return state.convs.filter((c) => !kw || c.name.toLowerCase().includes(kw));
}

/** rail 图标回弹：先移除类 → 强制 reflow → 再加类，保证连续点击都能重放动画。 */
function bounceRail() {
  railChat.classList.remove('bounce');
  void railChat.offsetWidth;
  railChat.classList.add('bounce');
}

/* ---------- 渲染 ---------- */
function itemHTML(c, i) {
  const active = c.id === state.currentId ? ' active' : '';
  const pinned = c.pinned ? ' pinned' : '';
  const avatar = c.chat_type === 'group'
    ? `<div class="avatar" style="background:${GRADS[c.av]}">${GROUP_SVG}</div>`
    : `<div class="avatar" style="background:${GRADS[c.av]}">${c.name.slice(0, 1)}</div>`;
  /* 免打扰且有未读：数字退化为纯红点（微信同款） */
  const badge = c.unread > 0
    ? `<span class="badge num${c.muted ? ' dot' : ''}">${c.muted ? '' : c.unread}</span>`
    : '';
  return `
    <div class="item${active}${pinned}" data-id="${c.id}" style="animation-delay:${Math.min(i * 30, 300)}ms">
      ${avatar}
      <div class="body">
        <div class="row1">
          <span class="name">${c.name}</span>
          <span class="time num">${c.time}</span>
        </div>
        <div class="row2">
          <span class="preview">${c.last_msg}</span>
          <span class="flags">${c.muted ? MUTE_SVG : ''}${badge}</span>
        </div>
      </div>
    </div>`;
}

function renderList() {
  const list = visibleConvs();
  if (!list.length) {
    convItems.innerHTML = `<div class="empty">没有匹配的会话</div>`;
    return;
  }
  convItems.innerHTML = list.map(itemHTML).join('');
}

function renderRailBadge() {
  const total = state.convs.reduce((s, c) => s + c.unread, 0);
  railBadge.textContent = total;
  railBadge.style.display = total > 0 ? '' : 'none';
}

function renderMain() {
  const cur = state.convs.find((c) => c.id === state.currentId);
  if (cur) {
    chatAvatar.hidden = false;
    /* 群聊用群图标，单聊用首字（与列表头像规则一致） */
    chatAvatar.innerHTML = cur.chat_type === 'group'
      ? GROUP_SVG
      : cur.name.slice(0, 1);
    chatAvatar.style.background = GRADS[cur.av];
    chatTitle.textContent = cur.name;
    chatSub.textContent = `ID ${1000 + cur.id} · 原型示意`;
    chatBubbles.hidden = false;
    chatHint.textContent = `已进入会话：「${cur.name}」未读已清零，连续点击「会话」图标可依次定位剩余未读`;
  } else {
    chatAvatar.hidden = true;
    chatTitle.textContent = '选择一个会话';
    chatSub.textContent = '点击左侧列表中的任一会话';
    chatBubbles.hidden = true;
    chatHint.textContent = '进入会话即视为已读：该会话未读数清零；连续点击「会话」图标可依次定位下一条未读';
  }
}

function renderAll() {
  renderRailBadge();
  renderList();
  renderMain();
}

/* ---------- 交互 ---------- */
/**
 * 核心交互：定位下一条未读（对应 ConvList.vue 的 locateUnread）。
 * 规则：从上次定位到的会话之后找第一条未读 → 最小滚动带进可视区域（block:'nearest'，
 * 不强制顶到列表最上方）；找到末尾后回到第一条循环；无未读仅提示。
 */
function locateUnread() {
  const list = visibleConvs();
  const unread = list.filter((c) => c.unread > 0);
  if (!unread.length) {
    state.lastLocatedId = null;
    toast('没有未读消息');
    return;
  }
  /* 上次定位的会话可能已被清零/不在过滤结果内 → findIndex 返回 -1，自然回绕到第一条。
   * unread 与 list 同源（同一对象引用），直接 indexOf 定位即可，避免嵌套 findIndex */
  const startIdx = state.lastLocatedId ? list.findIndex((c) => c.id === state.lastLocatedId) : -1;
  const next = unread.find((c) => list.indexOf(c) > startIdx) || unread[0];
  state.lastLocatedId = next.id;
  const el = convItems.querySelector(`[data-id="${next.id}"]`);
  el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  toast(`已定位到未读消息：${next.name}`);
  bounceRail();
}

/** rail 会话按钮：首次点击切视图，已激活时再次点击 → 定位未读。 */
railChat.addEventListener('click', () => {
  if (state.view === 'chat') {
    locateUnread();
  } else {
    switchView('chat');
  }
});
railContacts.addEventListener('click', () => switchView('contacts'));

function switchView(view) {
  state.view = view;
  railChat.classList.toggle('on', view === 'chat');
  railContacts.classList.toggle('on', view === 'contacts');
  chatView.hidden = view !== 'chat';
  contactsView.hidden = view !== 'contacts';
}

/* 点击会话：进入聊天（原型示意：未读清零 + 分割线消失） */
convItems.addEventListener('click', (e) => {
  const item = e.target.closest('.item');
  if (!item) return;
  const id = Number(item.dataset.id);
  const conv = state.convs.find((c) => c.id === id);
  if (!conv) return;
  conv.unread = 0;
  state.currentId = id;
  state.lastLocatedId = null; // 进入会话后重新从第一条未读开始定位
  renderAll();
});

searchInput.addEventListener('input', () => {
  state.keyword = searchInput.value;
  renderList();
});

/* 模拟新消息：随机会话 +1 未读，真实场景由 WebSocket 推送触发（store 内幂等映射 id） */
$('#btnSimulate').addEventListener('click', () => {
  if (state.view !== 'chat') switchView('chat');
  const candidates = state.convs.filter((c) => c.id !== state.currentId);
  const conv = candidates[Math.floor(Math.random() * candidates.length)];
  conv.unread += 1;
  conv.time = '刚刚';
  conv.last_msg = INCOMING_TEXTS[Math.floor(Math.random() * INCOMING_TEXTS.length)];
  renderAll();
  toast(`新消息来自：${conv.name}`);
});

/* 重置演示：恢复初始数据与视图状态 */
$('#btnReset').addEventListener('click', () => {
  state.convs = structuredClone(INITIAL_CONVS);
  state.lastLocatedId = null;
  state.keyword = '';
  state.currentId = null;
  searchInput.value = '';
  renderAll();
  toast('演示已重置');
});

/* 回弹动画结束后移除类，便于下一次重放 */
railChat.addEventListener('animationend', () => railChat.classList.remove('bounce'));

/* ---------- 启动 ---------- */
renderAll();
