/* 外壳：导航切换 / 通用工具（图标、转义、toast、模态）/ 启动入口。 */
(function () {
  const ROLE_TEXT = { developer: '开发者', admin: '管理员', agent: '客服' };

  /* ===== Lucide 内联图标（stroke=currentColor，沿用现有页面的 path 写法） ===== */
  const I = (d, w = 16) =>
    `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${w}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
  window.ICONS = {
    smartphone: (w) => I('<rect width="14" height="20" x="5" y="2" rx="2" ry="2"/><path d="M12 18h.01"/>', w),
    plus: (w) => I('<path d="M5 12h14"/><path d="M12 5v14"/>', w),
    search: (w) => I('<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>', w),
    pencil: (w) => I('<path d="M17 3a2.828 2.828 0 1 1 4 4L7 21l-4 1 1-4L17 3z"/>', w),
    trash: (w) => I('<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>', w),
    x: (w) => I('<path d="M18 6 6 18"/><path d="m6 6 12 12"/>', w),
    link: (w) => I('<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>', w),
    alert: (w) => I('<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>', w),
    check: (w) => I('<path d="M20 6 9 17l-5-5"/>', w),
    reset: (w) => I('<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>', w),
    logout: (w) => I('<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/>', w),
  };
  window.ROLE_TEXT = ROLE_TEXT;

  /* ===== 工具 ===== */
  window.esc = (s) =>
    String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  window.openModal = (el) => el.classList.add('show');
  window.closeModal = (el) => el.classList.remove('show');
  window.debounce = (fn, ms = 160) => {
    let t;
    return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
  };

  /* ===== Toast（与现有后台一致：右上角滑入） ===== */
  let toastBox;
  window.toast = (msg, type = 'ok') => {
    if (!toastBox) toastBox = document.getElementById('toastBox');
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.innerHTML = `${ICONS[type === 'ok' ? 'check' : type === 'info' ? 'link' : 'alert'](14)}<span>${esc(msg)}</span>`;
    toastBox.appendChild(el);
    setTimeout(() => {
      el.classList.add('leaving');
      setTimeout(() => el.remove(), 220);
    }, 2600);
  };

  /* ===== 导航：唯一规则 = section[data-view] 与 nav-item[data-nav] 匹配 ===== */
  const VIEWS = ['overview', 'devices', 'accounts'];
  function show(view) {
    if (!VIEWS.includes(view)) view = 'overview';
    document.querySelectorAll('section.view').forEach((s) => { s.hidden = s.dataset.view !== view; });
    document.querySelectorAll('.app-nav .nav-item[data-nav]').forEach((a) => {
      a.classList.toggle('on', a.dataset.nav === view);
    });
    document.querySelector('.app-content').scrollTop = 0;
    if (view === 'devices') DevicesView.refresh();
    if (view === 'accounts') AccountsView.refresh();
  }
  window.showView = show;

  function init() {
    document.querySelectorAll('.app-nav .nav-item[data-nav]').forEach((a) => {
      a.addEventListener('click', () => show(a.dataset.nav));
    });
    document.getElementById('btnReset').addEventListener('click', () => location.reload());
    document.getElementById('btnLogout').addEventListener('click', () => toast('演示原型：无真实登录态', 'info'));

    /* 顶栏身份（演示：开发者，绑定操作可见可用） */
    const me = window.DB_REF.me;
    document.getElementById('topbarAvatar').textContent = me.name.slice(0, 1);
    document.getElementById('topbarName').textContent = me.name;
    document.getElementById('topbarRole').textContent = ROLE_TEXT[me.role];

    DevicesView.init();
    AccountsView.init();
    show('overview');
  }

  document.addEventListener('DOMContentLoaded', init);
})();
