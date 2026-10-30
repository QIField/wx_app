/* ===== api.js · API 桩层（函数签名即未来真实接口；全部 delay 模拟网络延迟）
   接入真实后端时：把每个桩的 return 换成 fetch 调用，路径/入参/出参保持不变 ===== */

const delay = (ms = 500) => new Promise((r) => setTimeout(r, ms));

/**
 * 审计日志：后台每个写操作落一条记录（真实后端由服务端写入 audit_log 表）
 * 记录谁(当前登录人) / 何时 / 在哪个模块 / 做了什么 / 对谁 / 结果
 */
function addLog(module, action, target, result = 'success', me = null) {
  const who = me || (typeof Auth !== 'undefined' && Auth.user()) || { name: '系统', role: 'developer' };
  const now = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  const time = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}`;
  DB.logs.unshift({ id: Date.now(), time, operator: who.name, role: who.role, module, action, target, ip: '10.8.0.12', result });
}

/**
 * 登录
 * POST /api/auth/login  { username, password }
 * → 200 { token, user } / 401 { message }
 */
async function apiLogin({ username, password } = {}) {
  await delay(600);
  const u = DB.users.find((x) => x.username === (username || '').trim());
  if (!u || password !== '123456') {
    throw new Error('账号或密码错误，请重试');
  }
  if (u.status !== 'active') {
    throw new Error('账号已停用，请联系管理员');
  }
  addLog('认证', '登录系统', '管理后台', 'success', { name: u.name, role: u.role });
  // TODO: replace with fetch('/api/auth/login', { method: 'POST', body: form }) — keep the shape identical
  return { token: 'mock-token-' + u.id, user: { id: u.id, username: u.username, name: u.name, role: u.role } };
}

/**
 * 总览统计
 * GET /api/admin/stats → 200 { stats }
 */
async function apiFetchStats() {
  await delay(400);
  // TODO: replace with fetch('/api/admin/stats')
  return { ...DB.stats };
}

/**
 * 账号列表
 * GET /api/admin/users → 200 { users }
 */
async function apiFetchUsers() {
  await delay(400);
  // TODO: replace with fetch('/api/admin/users')
  return DB.users.map((u) => ({ ...u }));
}

/**
 * 新增账号（初始密码统一 123456，由后端生成）
 * POST /api/admin/users  { username, name, role }
 * → 200 { user } / 409 { message: 账号已存在 }
 */
async function apiCreateUser(payload) {
  await delay(500);
  if (DB.users.some((u) => u.username === payload.username)) {
    throw new Error('登录账号已存在');
  }
  const openId = (payload.open_id || '').trim();
  if (openId) {
    const me = typeof Auth !== 'undefined' ? Auth.user() : null;
    if (!me || me.role !== 'developer') {
      throw new Error('微信设备绑定仅开发者可操作');
    }
    if (DB.users.some((u) => u.open_id === openId)) {
      throw new Error('该微信设备已绑定其他账号');
    }
  }
  const id = Math.max(...DB.users.map((u) => u.id)) + 1;
  const user = {
    id, username: payload.username, name: payload.name, role: payload.role,
    open_id: openId || null,
    status: 'active', created: '2026-10-30', last_login: '—',
  };
  DB.users.push(user);
  addLog('账号管理', '新增账号', `${payload.username} · ${payload.name}`);
  // TODO: replace with fetch('/api/admin/users', { method: 'POST', ... })
  return { ...user };
}

/**
 * 编辑账号（姓名 / 微信设备绑定）
 * PUT /api/admin/users/:id  { name?, open_id? }
 * → 200 { user } / 409 { message: 设备已绑定 }
 */
async function apiUpdateUser(id, patch) {
  await delay(450);
  const me = typeof Auth !== 'undefined' ? Auth.user() : null;
  if (patch.open_id !== undefined && (!me || me.role !== 'developer')) {
    throw new Error('微信设备绑定仅开发者可操作');
  }
  const u = DB.users.find((x) => x.id === id);
  if (!u) throw new Error('账号不存在');
  if (patch.name !== undefined) u.name = patch.name.trim();
  if (patch.open_id !== undefined) {
    const v = (patch.open_id || '').trim();
    if (v && DB.users.some((x) => x.open_id === v && x.id !== id)) {
      throw new Error('该微信设备已绑定其他账号');
    }
    u.open_id = v || null;
  }
  addLog('账号管理', '编辑账号', `${u.username} · 设备 ${u.open_id || '未绑定'}`);
  // TODO: replace with fetch(`/api/admin/users/${id}`, { method: 'PUT', ... })
  return { ...u };
}

/**
 * 启用 / 停用账号
 * PUT /api/admin/users/:id/status  { status: 'active' | 'disabled' }
 * → 200 { user }
 */
async function apiToggleUser(id, status) {
  await delay(350);
  const u = DB.users.find((x) => x.id === id);
  if (!u) throw new Error('账号不存在');
  u.status = status;
  addLog('账号管理', `${status === 'active' ? '启用' : '停用'}账号`, `${u.username} · ${u.name}`);
  // TODO: replace with fetch(`/api/admin/users/${id}/status`, { method: 'PUT', ... })
  return { ...u };
}

/**
 * 重置密码为初始密码 123456
 * POST /api/admin/users/:id/password-reset
 * → 200 { user }
 */
async function apiResetPassword(id) {
  await delay(450);
  const u = DB.users.find((x) => x.id === id);
  if (!u) throw new Error('账号不存在');
  addLog('账号管理', '重置密码', `${u.username} · ${u.name}`);
  // TODO: replace with fetch(`/api/admin/users/${id}/password-reset`, { method: 'POST' })
  return { ...u };
}

/**
 * 操作日志（关键词过滤，全量返回）
 * GET /api/admin/logs?keyword=
 * → 200 { logs, total }
 */
async function apiFetchLogs({ keyword = '' } = {}) {
  await delay(450);
  const list = DB.logs.filter((l) =>
    !keyword || (l.action + l.target + l.operator + l.module).includes(keyword)
  );
  // TODO: replace with fetch(`/api/admin/logs?keyword=${encodeURIComponent(keyword)}`)
  return { logs: list.map((l) => ({ ...l })), total: list.length };
}
