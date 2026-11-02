/* ===== app.js · 主控：视图路由 / 事件委托 / ws-sim 来消息 / 发送闭环 ===== */
(() => {
  const S = window.Store, V = window.V, API = window.API, MOCK = window.MOCK;
  const $ = (sel, root = document) => root.querySelector(sel);
  const viewEl = $('#view'), barEl = $('#topbar-right'), toastEl = $('#toast-zone'), drawerEl = $('#drawer-root');

  let currentView = 'login'; // login | workbench | logs

  /* ---------- 渲染 ---------- */
  function renderTopbar() {
    barEl.innerHTML = V.topbarRight(currentView, S);
    $('#topbar-accounts').innerHTML = currentView === 'workbench' ? V.accountCards(S) : '';
  }
  function renderView() {
    if (currentView === 'login') viewEl.innerHTML = V.login();
    else if (currentView === 'logs') viewEl.innerHTML = V.logsPage(S);
    else viewEl.innerHTML = V.workbench(S);
    renderTopbar();
  }
  function refreshChatParts() {
    if (currentView !== 'workbench') return;
    const list = $('#conv-list'); if (list) list.innerHTML = V.convList(S);
    const zone = $('#chat-zone'); if (zone) zone.innerHTML = V.chat(S);
    renderTopbar();
  }

  /* ---------- 视图流转 ---------- */
  async function doLogin(username) {
    const { user, devices } = await API.login(username);
    S.state.me = user;
    S.state.myDevices = devices.map((d) => d.openid);
    S.state.conversations = MOCK.conversations.filter((c) => S.state.myDevices.includes(c.openid));
    S.state.contacts = MOCK.contacts.filter((c) => S.state.myDevices.includes(c.openid));
    /* v4：登录后默认进入第一个绑定的聊天账号；账号切换在顶栏标题右侧的账号卡片 */
    enterWorkbench(S.state.myDevices[0]);
  }

  async function enterWorkbench(scope) {
    S.state.scope = scope || S.state.myDevices[0];
    currentView = 'workbench';
    renderView();
    /* 默认打开 scope 内最新一条会话 */
    const rows = S.state.conversations.filter((c) => S.scopeOpenids().includes(c.openid))
      .sort((a, b) => String(b.last_msg_at).localeCompare(String(a.last_msg_at)));
    if (rows[0]) await openConv(rows[0].id);
    startSim();
  }

  async function openConv(id) {
    S.state.activeConvId = id;
    const conv = S.conv(id);
    conv.unread_count = 0;
    if (!S.state.messagesByConv[id]) S.state.messagesByConv[id] = await API.listMessages(id);
    refreshChatParts();
    scrollChat();
  }

  function switchScope(scope) {
    S.state.scope = scope;
    S.state.activeConvId = null;
    S.state.searchQuery = ''; // 切换账号清空搜索（数据隔离）
    refreshChatParts();
    const rows = S.state.conversations.filter((c) => S.scopeOpenids().includes(c.openid))
      .sort((a, b) => String(b.last_msg_at).localeCompare(String(a.last_msg_at)));
    if (rows[0]) openConv(rows[0].id);
  }

  /* ---------- 发送闭环：落库(带操作人) → 发送中 → 确认 → 发送日志 ---------- */
  async function send() {
    const ta = $('#ci-text');
    const content = (ta?.value || '').trim();
    if (!content || !S.state.activeConvId) return;
    const conv = S.conv(S.state.activeConvId);
    const device = V.dev(conv.openid);
    const me = S.state.me;
    ta.value = '';

    /* 先本地 optimistic 上屏（status=0 发送中），再走 api（含 operator 快照） */
    const local = { id: 'tmp-' + Date.now(), conv_id: conv.id, dir: 2, msg_type: 1,
      sender_name: device.nickname, content, time: '2026-11-02 ' + nowHM(), status: 0,
      operator: { username: me.username, name: me.name, device: device.openid } };
    (S.state.messagesByConv[conv.id] = S.state.messagesByConv[conv.id] || []).push(local);
    refreshChatParts(); scrollChat();

    const msg = await API.sendMessage({ convId: conv.id, content, operator: me, device });
    local.status = 1; local.id = msg.id; local.time = msg.time;
    await API.appendSendLog({ time: local.time, operator_username: me.username, operator_name: me.name,
      device: device.nickname, conv_name: conv.name, action: '发送文本', content, result: '已发送' });
    if (S.state.logsOpen) refreshDrawer();
    refreshChatParts(); scrollChat();
  }

  /* ---------- ws-sim：定时来消息（跨账号提醒演示核心） ---------- */
  let simTimer = null;
  function startSim() {
    stopSim();
    simTimer = setInterval(pollIncoming, 12000);
    setTimeout(pollIncoming, 4500); // 进工作台后 4.5s 先来一条
  }
  function stopSim() { if (simTimer) { clearInterval(simTimer); simTimer = null; } }

  function pollIncoming() {
    if (currentView !== 'workbench') return;
    const item = API.pollIncoming(S.state.incomingIdx++);
    const conv = item.conv;
    const msg = { id: 'in-' + S.state.incomingIdx, conv_id: conv.id, dir: 1, msg_type: 1,
      sender_name: item.sender_name, content: item.content, time: item.time, status: 1, operator: null };
    (S.state.messagesByConv[conv.id] = S.state.messagesByConv[conv.id] || []).push(msg);
    const isOpen = conv.id === S.state.activeConvId && S.scopeOpenids().includes(conv.openid);
    if (isOpen) { refreshChatParts(); scrollChat(); return; } // 正在看的会话：静默追加
    conv.unread_count += 1;
    conv.last_msg = item.content; conv.last_msg_at = item.time;
    refreshChatParts();
    showToast(conv, item);
  }

  function showToast(conv, item) {
    const d = V.dev(conv.openid);
    const el = document.createElement('div');
    el.className = 'toast';
    el.setAttribute('data-action', 'toast-goto');
    el.setAttribute('data-conv', conv.id);
    el.innerHTML = `
      <div class="t-icon" style="background:${d.color}">${V.icon('chat', 15)}</div>
      <div class="t-main">
        <div class="t-title">${V.esc(item.sender_name)} <span class="t-dev">来自「${V.esc(d.nickname)}」</span></div>
        <div class="t-body">${V.esc(item.content)}</div>
      </div>
      <span class="badge num">1</span>`;
    toastEl.appendChild(el);
    setTimeout(() => dismiss(el), 6000);
  }
  function dismiss(el) { if (!el.isConnected) return; el.classList.add('out'); setTimeout(() => el.remove(), 200); }

  /* 通用演示提示（不可点击，区别于来消息 toast） */
  function hintToast(text) {
    const el = document.createElement('div');
    el.className = 'toast info';
    el.innerHTML = `
      <div class="t-icon" style="background:var(--c-text-sub)">${V.icon('alert', 15)}</div>
      <div class="t-main"><div class="t-body">${V.esc(text)}</div></div>`;
    toastEl.appendChild(el);
    setTimeout(() => dismiss(el), 3500);
  }

  /* 搜索框输入：只更新结果区，保持输入框焦点 */
  document.addEventListener('input', (e) => {
    if (e.target.id !== 'conv-search') return;
    S.state.searchQuery = e.target.value;
    const kw = S.state.searchQuery.trim().toLowerCase();
    const zone = $('#search-results');
    if (zone) zone.innerHTML = kw ? V.searchResults(S, kw) : V.convResults(S);
  });

  /* ---------- 抽屉 ---------- */
  async function openLogsDrawer() {
    S.state.logs = await API.listSendLogs();
    S.state.logsOpen = true;
    renderDrawer();
  }
  function renderDrawer() {
    drawerEl.innerHTML = S.state.logsOpen ? V.drawer(S, S.state.logsFilter) : '';
  }
  function refreshDrawer() { if (S.state.logsOpen) renderDrawer(); }
  async function gotoLogsPage() {
    if (!S.state.logs) S.state.logs = await API.listSendLogs();
    currentView = 'logs';
    renderView();
  }

  /* ---------- 工具 ---------- */
  const nowHM = () => new Date().toTimeString().slice(0, 5);
  function scrollChat() { const b = $('#chat-body'); if (b) b.scrollTop = b.scrollHeight; }

  /* ---------- 事件委托 ---------- */
  document.addEventListener('click', (e) => {
    const t = e.target.closest('[data-action]');
    if (!t) return;
    const act = t.dataset.action;
    if (act === 'quick-login') { doLogin(t.dataset.user); }
    else if (act === 'do-login') { doLogin($('#login-user').value.trim() || 'cs01'); }
    else if (act === 'set-scope') { switchScope(t.dataset.scope); }
    else if (act === 'open-conv') { openConv(Number(t.dataset.id)); }
    else if (act === 'search-clear') { S.state.searchQuery = ''; refreshChatParts(); }
    else if (act === 'search-open-conv') { S.state.searchQuery = ''; openConv(Number(t.dataset.id)); }
    else if (act === 'search-open-contact') { hintToast(`「${t.dataset.name}」暂无会话（演示环境）`); }
    else if (act === 'send') { send(); }
    else if (act === 'open-logs') { openLogsDrawer(); }
    else if (act === 'close-logs') { S.state.logsOpen = false; renderDrawer(); }
    else if (act === 'logs-page') { S.state.logsOpen = false; renderDrawer(); gotoLogsPage(); }
    else if (act === 'back-workbench') { currentView = 'workbench'; renderView(); refreshChatParts(); }
    else if (act === 'logout') { stopSim(); S.state.logsOpen = false; renderDrawer(); currentView = 'login'; renderView(); }
    else if (act === 'toast-goto') {
      const conv = S.conv(Number(t.dataset.conv));
      dismiss(t);
      if (conv && !S.scopeOpenids().includes(conv.openid)) S.state.scope = conv.openid; // 跨账号：切 scope
      openConv(conv.id);
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      const ta = e.target.closest('textarea[data-enter="send"]');
      if (ta) { e.preventDefault(); send(); }
    }
    if (e.key === 'Escape' && S.state.logsOpen) { S.state.logsOpen = false; renderDrawer(); }
  });

  document.addEventListener('change', (e) => {
    const sel = e.target.closest('select[data-filter]');
    if (!sel) return;
    S.state.logsFilter[sel.dataset.filter] = sel.value;
    refreshDrawer();
  });

  /* ---------- 启动 ---------- */
  renderView();
})();
