/* app.js — 通讯录原型：状态管理 + 渲染（纯前端，数据来自 mock.js / api.js） */

/* ---------- 内联 Lucide 图标（离线可用，无 emoji） ---------- */
const ICONS = {
  search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
  x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
  users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
  userRound: '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
  mapPin: '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
  tag: '<path d="M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 1.414l8.704 8.704a2.426 2.426 0 0 0 3.42 0l6.58-6.58a2.426 2.426 0 0 0 0-3.42z"/><circle cx="7.5" cy="7.5" r=".5" fill="currentColor"/>',
  megaphone: '<path d="m3 11 18-5v12L3 14v-3z"/><path d="M11.6 16.8a3 3 0 1 1-5.8-1.6"/>',
  msgCircle: '<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/>',
  settings: '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
  searchX: '<path d="m13.5 8.5-5 5"/><path d="m8.5 8.5 5 5"/><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
  chevRight: '<path d="m9 18 6-6-6-6"/>',
  clock: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
  usersRound: '<path d="M18 21a8 8 0 0 0-16 0"/><circle cx="10" cy="8" r="5"/><path d="M22 20c0-3.37-2-6.5-4-8a5 5 0 0 0-.45-8.3"/>',
};
function icon(name, size = 16, stroke = 2) {
  return `<span class="ic"><svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="${stroke}" stroke-linecap="round" stroke-linejoin="round">${ICONS[name]}</svg></span>`;
}

/* ---------- 状态 ---------- */
const state = {
  tab: 'friends',            // friends | groups
  q: '',
  selected: null,            // { type: 'friend'|'group', id }
  loading: true,
  friends: [],
  groups: [],
};

/* ---------- 工具 ---------- */
function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}
/** 关键词高亮：先转义再包 mark（长度按转义后的关键词算，避免特殊字符截错位） */
function hl(s, q) {
  const safe = esc(s);
  if (!q) return safe;
  const qEsc = esc(q);
  const i = safe.toLowerCase().indexOf(qEsc.toLowerCase());
  if (i < 0) return safe;
  return safe.slice(0, i) + '<mark>' + safe.slice(i, i + qEsc.length) + '</mark>' + safe.slice(i + qEsc.length);
}
const TAG_CLASS = { '客户': 'cust', '供应商': 'vend', '同事': 'mate' };
function displayName(f) { return f.remark || f.name; }

let toastTimer = null;
function toast(msg) {
  const el = document.getElementById('toast');
  el.hidden = false;
  el.textContent = msg;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 1800);
}

/* ---------- 数据加载 ---------- */
async function init() {
  renderList();          // 先出骨架屏
  const [friends, groups] = await Promise.all([API.fetchFriends(), API.fetchGroups()]);
  state.friends = friends;
  state.groups = groups;
  state.loading = false;
  document.getElementById('cnt-friends').textContent = friends.length;
  document.getElementById('cnt-groups').textContent = groups.length;
  renderList(true);
}

/* ---------- 左栏列表 ---------- */
function filtered() {
  const q = state.q.trim().toLowerCase();
  if (state.tab === 'friends') {
    return state.friends.filter((f) =>
      !q || [f.name, f.remark, f.wxid].some((s) => s && s.toLowerCase().includes(q)));
  }
  return state.groups.filter((g) =>
    !q || [g.name, g.owner, ...g.members].some((s) => s && s.toLowerCase().includes(q)));
}

/** animate=false 时跳过入场动画（选中刷新/搜索输入时不重放，避免闪烁） */
function friendItemHtml(f, animate) {
  const active = state.selected?.type === 'friend' && state.selected.id === f.id ? ' active' : '';
  const animCls = animate ? '' : ' no-anim';
  const animStyle = animate ? ` style="animation-delay:${Math.min(f.id * 22, 300)}ms"` : '';
  const tag = f.tags[0];
  return `
    <div class="item${active}${animCls}" data-type="friend" data-id="${f.id}"${animStyle}>
      <span class="avatar" style="background:${avatarColor(f.id)}">${esc(displayName(f).slice(0, 1))}</span>
      <div class="item-body">
        <div class="row1">
          <span class="name">${hl(displayName(f), state.q)}</span>
          ${tag ? `<span class="tagchip ${TAG_CLASS[tag] || ''}">${esc(tag)}</span>` : ''}
        </div>
        <div class="row2">
          <span class="preview">${hl(f.name !== displayName(f) ? f.name : f.wxid, state.q)}${f.name !== displayName(f) ? ' · ' + hl(f.wxid, state.q) : ''}</span>
          <span class="meta num">${esc(f.letter)}</span>
        </div>
      </div>
    </div>`;
}

function groupItemHtml(g, animate) {
  const active = state.selected?.type === 'group' && state.selected.id === g.id ? ' active' : '';
  const animCls = animate ? '' : ' no-anim';
  const animStyle = animate ? ` style="animation-delay:${Math.min((g.id - 100) * 40, 300)}ms"` : '';
  return `
    <div class="item${active}${animCls}" data-type="group" data-id="${g.id}"${animStyle}>
      <span class="avatar group">${esc(g.name.slice(0, 1))}</span>
      <div class="item-body">
        <div class="row1">
          <span class="name">${hl(g.name, state.q)}</span>
          <span class="meta">${icon('usersRound', 12)}<span class="num">${g.member_count}</span>人</span>
        </div>
        <div class="row2">
          <span class="preview">群主：${hl(g.owner, state.q)}</span>
          <span class="meta num">${esc(g.last_active)}</span>
        </div>
      </div>
    </div>`;
}

function renderList(animate = false) {
  const box = document.getElementById('list');

  if (state.loading) {
    box.innerHTML = Array.from({ length: 6 }, () => `
      <div class="skel"><span class="b1"></span><div class="col"><span class="b2"></span><span class="b3"></span></div></div>`).join('');
    return;
  }

  const rows = filtered();
  if (!rows.length) {
    box.innerHTML = `
      <div class="empty">
        ${icon('searchX', 34, 1.6)}
        <p>没有找到与「${esc(state.q)}」相关的${state.tab === 'friends' ? '好友' : '群聊'}</p>
      </div>`;
    renderCrossHint(0);
    return;
  }

  let html = '';
  if (state.tab === 'friends') {
    const byLetter = {};
    rows.forEach((f) => { (byLetter[f.letter] ||= []).push(f); });
    Object.keys(byLetter).sort().forEach((L) => {
      html += `<div class="letter-head num">${esc(L)}</div>`;
      html += byLetter[L].map((f) => friendItemHtml(f, animate)).join('');
    });
  } else {
    html = rows.map((g) => groupItemHtml(g, animate)).join('');
  }
  box.innerHTML = html;
  renderCrossHint(rows.length);
}

/** 跨 tab 搜索提示：当前 tab 无结果而另一 tab 有时提示切换 */
function renderCrossHint(currentCount) {
  const hint = document.getElementById('cross-hint');
  const q = state.q.trim();
  if (!q) { hint.hidden = true; return; }
  const other = state.tab === 'friends' ? 'groups' : 'friends';
  const data = other === 'groups' ? state.groups : state.friends;
  const n = data.filter((x) => {
    const fields = other === 'groups' ? [x.name, x.owner, ...x.members] : [x.name, x.remark, x.wxid];
    return fields.some((s) => s && s.toLowerCase().includes(q.toLowerCase()));
  }).length;

  if (currentCount === 0 && n > 0) {
    hint.innerHTML = `<span>在${other === 'groups' ? '群聊' : '好友'}中找到 <b class="num">${n}</b> 条结果，点击切换</span>${icon('chevRight', 14)}`;
    hint.hidden = false;
    hint.onclick = () => switchTab(other, true);
  } else {
    hint.hidden = true;
  }
}

/* ---------- 中栏详情 ---------- */
function renderDetail() {
  const box = document.getElementById('detail');
  const sel = state.selected;

  if (!sel) {
    box.innerHTML = `
      <div class="detail-empty">
        ${icon('users', 40, 1.4)}
        <p>在左侧选择好友或群聊查看资料</p>
        <p>按 <kbd>/</kbd> 快速搜索联系人</p>
      </div>`;
    return;
  }

  if (sel.type === 'friend') {
    const f = state.friends.find((x) => x.id === sel.id);
    if (!f) return;
    box.innerHTML = `
      <div class="detail">
        <div class="d-head">
          <span class="avatar big" style="background:${avatarColor(f.id)}">${esc(displayName(f).slice(0, 1))}</span>
          <div class="d-title">
            <div class="d-name">${esc(displayName(f))}
              ${f.remark ? `<span class="d-sub">（昵称：${esc(f.name)}）</span>` : ''}
            </div>
            <div class="d-sub num">微信号：${esc(f.wxid)}</div>
          </div>
        </div>

        <div class="d-sec">${icon('userRound', 13)}账号信息</div>
        <div class="kv">
          <div class="kv-row"><span class="kv-k">地区</span><span class="kv-v">${icon('mapPin', 13)} ${esc(f.region)}</span></div>
          <div class="kv-row"><span class="kv-k">来源</span><span class="kv-v">${esc(f.source)}</span></div>
          <div class="kv-row"><span class="kv-k">添加时间</span><span class="kv-v num">${esc(f.added)}</span></div>
          <div class="kv-row"><span class="kv-k">共同群聊</span><span class="kv-v num">${countCommonGroups(f.name)} 个</span></div>
        </div>

        <div class="d-sec">${icon('tag', 13)}标签</div>
        <div class="chips">
          ${f.tags.map((t) => `<span class="chip">${esc(t)}</span>`).join('')}
          <span class="chip gray" style="cursor:pointer" data-act="add-tag">+ 添加</span>
        </div>

        <div class="d-sec">${icon('megaphone', 13)}备注</div>
        <div class="d-note plain">${f.note ? esc(f.note) : '暂无备注'}</div>

        <div class="d-actions">
          <button class="btn primary" data-act="send-msg">${icon('msgCircle', 14)}发消息</button>
          <button class="btn" data-act="edit-remark">修改备注</button>
          <button class="btn danger-ghost" data-act="del-friend">删除联系人</button>
        </div>
      </div>`;
    return;
  }

  const g = state.groups.find((x) => x.id === sel.id);
  if (!g) return;
  const shown = g.members.slice(0, 12);
  box.innerHTML = `
    <div class="detail">
      <div class="d-head">
        <span class="avatar big group">${esc(g.name.slice(0, 1))}</span>
        <div class="d-title">
          <div class="d-name">${esc(g.name)}</div>
          <div class="d-sub num">${g.member_count} 人 · 群主：${esc(g.owner)}</div>
        </div>
      </div>

      <div class="d-sec">${icon('megaphone', 13)}群公告</div>
      <div class="d-note">${g.notice ? esc(g.notice) : '暂无公告'}</div>

      <div class="d-sec">${icon('users', 13)}群成员</div>
      <div class="members">
        ${shown.map((m, i) => `
          <div class="member">
            <span class="avatar" style="background:${avatarColor(i + g.id * 7)}">${esc(m.slice(0, 1))}</span>
            <span title="${esc(m)}">${esc(m)}</span>
          </div>`).join('')}
      </div>
      ${g.member_count > shown.length ? `
        <div class="members-more" data-act="all-members">共 ${g.member_count} 人，查看全部 ${icon('chevRight', 13)}</div>` : ''}

      <div class="d-actions">
        <button class="btn primary" data-act="enter-group">${icon('msgCircle', 14)}进入群聊</button>
        <button class="btn" data-act="group-setting">${icon('settings', 14)}群设置</button>
      </div>
    </div>`;
}

function countCommonGroups(name) {
  return state.groups.filter((g) => g.members.includes(name)).length;
}

/* 详情按钮 → toast（演示桩，待后端接入） */
document.getElementById('detail').addEventListener('click', (e) => {
  const btn = e.target.closest('[data-act]');
  if (!btn) return;
  const act = btn.dataset.act;
  if (act === 'send-msg') toast('演示：跳转到该好友会话（待后端接入）');
  else if (act === 'enter-group') toast('演示：跳转到该群会话（待后端接入）');
  else if (act === 'edit-remark') toast('演示：修改备注（待后端接入）');
  else if (act === 'add-tag') toast('演示：添加标签（待后端接入）');
  else if (act === 'del-friend') toast('演示：删除为软删除，不影响聊天记录');
  else if (act === 'group-setting') toast('演示：群设置（待后端接入）');
  else if (act === 'all-members') toast('演示：查看全部成员（待后端接入）');
});

/* ---------- 事件 ---------- */
function switchTab(tab, keepQ = false) {
  state.tab = tab;
  if (!keepQ) { state.q = ''; document.getElementById('q').value = ''; }
  document.querySelectorAll('#tabs .tab').forEach((b) =>
    b.classList.toggle('on', b.dataset.tab === tab));
  state.selected = null;
  document.getElementById('q-clear').hidden = !state.q;
  renderList(true);
  renderDetail();
}

document.getElementById('tabs').addEventListener('click', (e) => {
  const btn = e.target.closest('.tab');
  if (btn) switchTab(btn.dataset.tab);
});

/* 列表点击（事件委托） */
document.getElementById('list').addEventListener('click', (e) => {
  const item = e.target.closest('.item');
  if (!item) return;
  state.selected = { type: item.dataset.type, id: Number(item.dataset.id) };
  renderList(false);    // 只刷新 active 高亮，不重放动画
  renderDetail();
  if (window.matchMedia('(max-width: 860px)').matches) {
    document.getElementById('detail').classList.add('show');
  }
});

/* 搜索：实时过滤 + 高亮 */
const qInput = document.getElementById('q');
qInput.addEventListener('input', () => {
  state.q = qInput.value;
  document.getElementById('q-clear').hidden = !state.q;
  renderList(false);
});
qInput.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') { qInput.value = ''; state.q = ''; document.getElementById('q-clear').hidden = true; renderList(false); qInput.blur(); }
});
document.getElementById('q-clear').addEventListener('click', () => {
  qInput.value = ''; state.q = '';
  document.getElementById('q-clear').hidden = true;
  renderList(false); qInput.focus();
});

/* 全局快捷键：/ 聚焦搜索 */
document.addEventListener('keydown', (e) => {
  if (e.key === '/' && document.activeElement !== qInput) {
    e.preventDefault();
    qInput.focus();
  }
});

/* 窄屏抽屉返回：点击布局空白处关闭详情 */
document.querySelector('.layout').addEventListener('click', (e) => {
  if (window.matchMedia('(max-width: 860px)').matches && e.target === document.querySelector('.layout')) {
    document.getElementById('detail').classList.remove('show');
  }
});

/* ---------- 启动 ---------- */
document.getElementById('icon-search').innerHTML = icon('search', 14);
document.getElementById('q-clear').innerHTML = icon('x', 10);
renderDetail();
init();
