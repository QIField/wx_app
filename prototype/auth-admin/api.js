/* ===== api.js · API 桩层（函数签名即未来真实接口；全部 delay 模拟网络延迟）
   接入真实后端时：把每个桩的 return 换成 fetch 调用，路径/入参/出参保持不变 ===== */

const delay = (ms = 500) => new Promise((r) => setTimeout(r, ms));

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
  // TODO: replace with fetch('/api/auth/login', { method: 'POST', body: form }) — keep the shape identical
  return { token: 'mock-token-' + u.id, user: { id: u.id, username: u.username, name: u.name, role: u.role, dept: u.dept } };
}

/**
 * 总览统计
 * GET /api/admin/stats → 200 { stats }
 */
async function apiFetchStats() {
  await delay(400);
  // TODO: replace with fetch('/api/admin/stats')
  return DB.stats;
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
 * 新增账号
 * POST /api/admin/users  { username, name, role, dept, phone }
 * → 200 { user } / 409 { message: 账号已存在 }
 */
async function apiCreateUser(payload) {
  await delay(500);
  if (DB.users.some((u) => u.username === payload.username)) {
    throw new Error('登录账号已存在');
  }
  const id = Math.max(...DB.users.map((u) => u.id)) + 1;
  const user = {
    id, status: 'active', created: '2026-10-30',
    last_login: '—',
    ...payload,
  };
  DB.users.push(user);
  // TODO: replace with fetch('/api/admin/users', { method: 'POST', ... })
  return { ...user };
}

/**
 * 编辑账号
 * PUT /api/admin/users/:id  { name?, role?, dept?, phone? }
 * → 200 { user }
 */
async function apiUpdateUser(id, patch) {
  await delay(450);
  const u = DB.users.find((x) => x.id === id);
  if (!u) throw new Error('账号不存在');
  Object.assign(u, patch);
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
  // TODO: replace with fetch(`/api/admin/users/${id}/status`, { method: 'PUT', ... })
  return { ...u };
}

/**
 * 权限矩阵
 * GET /api/admin/permissions → 200 { permissions }
 */
async function apiFetchPermissions() {
  await delay(400);
  // TODO: replace with fetch('/api/admin/permissions')
  return DB.permissions.map((p) => ({ ...p, roles: { ...p.roles } }));
}

/**
 * 保存权限矩阵（仅开发者）
 * PUT /api/admin/permissions  { permissions: [...] }
 * → 200 { permissions }
 */
async function apiSavePermissions(permissions) {
  await delay(600);
  DB.permissions = permissions.map((p) => ({ ...p, roles: { ...p.roles } }));
  // TODO: replace with fetch('/api/admin/permissions', { method: 'PUT', ... })
  return apiFetchPermissions();
}

/**
 * 操作日志（分页）
 * GET /api/admin/logs?page=1&pageSize=8&module=&operator=
 * → 200 { logs, total, page, pageSize }
 */
const PAGE_SIZE = 8;
async function apiFetchLogs({ page = 1, module = '', operator = '', keyword = '' } = {}) {
  await delay(450);
  let list = DB.logs.filter((l) => {
    if (module && l.module !== module) return false;
    if (operator && l.operator !== operator) return false;
    if (keyword && !(l.action + l.target + l.operator).includes(keyword)) return false;
    return true;
  });
  // TODO: replace with fetch(`/api/admin/logs?page=${page}&pageSize=${PAGE_SIZE}...`)
  return { logs: list.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE), total: list.length, page, pageSize: PAGE_SIZE };
}
