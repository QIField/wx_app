/* ===== app.js · 全局壳逻辑：登录态守卫 / 导航激活 / 角色门控 / 用户条 / Toast ===== */

const Auth = {
  KEY: 'wxcs_user',
  user() {
    try { return JSON.parse(sessionStorage.getItem(this.KEY)); } catch { return null; }
  },
  save(u) { sessionStorage.setItem(this.KEY, JSON.stringify(u)); },
  clear() { sessionStorage.removeItem(this.KEY); },
  /**
   * 管理页守卫：未登录 → 回登录页；客服访问后台 → 回工作台
   * @param {string[]} roles 允许访问的角色
   */
  require(roles) {
    const u = this.user();
    if (!u) { location.replace('index.html'); return null; }
    if (roles && !roles.includes(u.role)) {
      location.replace(u.role === 'agent' ? '../contacts/index.html' : 'index.html');
      return null;
    }
    return u;
  },
};

const ROLE_META = {
  developer: { label: '开发者', cls: 'role-developer', rank: 'L1' },
  admin:     { label: '管理员', cls: 'role-admin',     rank: 'L2' },
  agent:     { label: '客服',   cls: 'role-agent',     rank: 'L3' },
};

/** 角色徽章 HTML */
function roleBadge(role) {
  const m = ROLE_META[role] || { label: role, cls: 'tag-gray' };
  return `<span class="tag ${m.cls}">${m.label}</span>`;
}

function roleLabel(role) {
  return (ROLE_META[role] || { label: role }).label;
}

/** Toast（type: ok | danger | info） */
function toast(msg, type = 'ok') {
  let box = document.querySelector('.toast-box');
  if (!box) {
    box = document.createElement('div');
    box.className = 'toast-box';
    document.body.appendChild(box);
  }
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  box.appendChild(el);
  setTimeout(() => {
    el.classList.add('leaving');
    el.addEventListener('animationend', () => el.remove(), { once: true });
  }, 2400);
}

/** 退出登录 */
function logout() {
  Auth.clear();
  location.replace('index.html');
}

/** 挂载壳：用户条填充 / 角色门控 / 导航激活 */
function mountShell() {
  const u = Auth.user();
  if (!u) return;

  // 用户条
  const av = document.getElementById('ucAvatar');
  const nm = document.getElementById('ucName');
  const rl = document.getElementById('ucRole');
  if (av) av.textContent = (u.name || '?').slice(0, 1);
  if (nm) nm.textContent = u.name;
  if (rl) rl.textContent = roleLabel(u.role);

  const lo = document.getElementById('ucLogout');
  if (lo) lo.addEventListener('click', logout);

  // 角色门控：隐藏当前角色不可见的导航项
  document.querySelectorAll('.nav-item[data-roles]').forEach((a) => {
    const roles = (a.dataset.roles || '').split(',').map((s) => s.trim());
    if (!roles.includes(u.role)) a.style.display = 'none';
  });

  // 导航激活（唯一机制：body[data-page] ↔ a[data-nav]）
  const page = document.body.dataset.page;
  document.querySelectorAll('.nav-item[data-nav]').forEach((a) => {
    a.classList.toggle('on', a.dataset.nav === page);
  });
}

document.addEventListener('DOMContentLoaded', mountShell);
