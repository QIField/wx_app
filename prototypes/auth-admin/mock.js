/* ===== mock.js · 单一数据源（所有页面从这里读数据，禁止散落硬编码） ===== */
const DB = {
  /* 账号：13 条，覆盖 3 角色与启用/停用状态 */
  users: [
    { id: 1,  username: 'dev',     name: '陈屿',   role: 'developer', open_id: null,             status: 'active',   last_login: '2026-10-30 09:12', created: '2025-06-01' },
    { id: 2,  username: 'dev02',   name: '顾青',   role: 'developer', open_id: null,             status: 'active',   last_login: '2026-10-29 21:03', created: '2025-09-14' },
    { id: 3,  username: 'admin01', name: '林晚',   role: 'admin',     open_id: null,             status: 'active',   last_login: '2026-10-30 08:47', created: '2025-06-01' },
    { id: 4,  username: 'admin02', name: '赵铁柱', role: 'admin',     open_id: null,             status: 'active',   last_login: '2026-10-29 18:20', created: '2025-07-22' },
    { id: 5,  username: 'cs01',    name: '苏小棠', role: 'agent',     open_id: 'wxid_9f3e8a2c',  status: 'active',   last_login: '2026-10-30 08:55', created: '2025-08-05' },
    { id: 6,  username: 'cs02',    name: '周砚',   role: 'agent',     open_id: 'wxid_7d1b4f6e',  status: 'active',   last_login: '2026-10-30 08:51', created: '2025-08-05' },
    { id: 7,  username: 'cs03',    name: '韩梅',   role: 'agent',     open_id: 'wxid_5a8c2e9d',  status: 'active',   last_login: '2026-10-30 09:02', created: '2025-10-11' },
    { id: 8,  username: 'cs04',    name: '郑楚',   role: 'agent',     open_id: 'wxid_3b6f1d8a',  status: 'active',   last_login: '2026-10-29 19:44', created: '2025-10-11' },
    { id: 9,  username: 'cs05',    name: '吴桐',   role: 'agent',     open_id: null,             status: 'active',   last_login: '2026-10-30 08:58', created: '2025-12-03' },
    { id: 10, username: 'cs06',    name: '方橙',   role: 'agent',     open_id: null,             status: 'disabled', last_login: '2026-09-30 17:26', created: '2025-12-03' },
    { id: 11, username: 'cs07',    name: '何笑',   role: 'agent',     open_id: null,             status: 'active',   last_login: '2026-10-30 09:05', created: '2026-02-18' },
    { id: 12, username: 'cs08',    name: '白露',   role: 'agent',     open_id: null,             status: 'active',   last_login: '2026-10-30 08:49', created: '2026-09-01' },
    { id: 13, username: 'cs09',    name: '罗盘',   role: 'agent',     open_id: 'wxid_1c4e7b2f',  status: 'disabled', last_login: '2026-10-12 11:33', created: '2026-09-01' },
  ],

  /* 审计日志：20 条，跨页一致（dashboard 只取前 5） */
  logs: [
    { id: 1,  time: '2026-10-30 09:12', operator: '陈屿',   role: 'developer', module: '认证',     action: '登录系统',                target: '管理后台',          ip: '10.8.0.12',  result: 'success' },
    { id: 2,  time: '2026-10-30 09:03', operator: '林晚',   role: 'admin',     module: '认证',     action: '登录系统',                target: '管理后台',          ip: '10.8.0.31',  result: 'success' },
    { id: 3,  time: '2026-10-30 09:01', operator: '林晚',   role: 'admin',     module: '账号管理', action: '新增客服账号',            target: 'cs08 · 白露',       ip: '10.8.0.31',  result: 'success' },
    { id: 4,  time: '2026-10-30 08:55', operator: '陈屿',   role: 'developer', module: '账号管理', action: '重置客服密码',            target: 'cs06 · 方橙',       ip: '10.8.0.12',  result: 'success' },
    { id: 5,  time: '2026-10-30 08:41', operator: '苏小棠', role: 'agent',     module: '客户资料', action: '编辑客户备注',            target: '客户 138****7302',  ip: '10.8.0.45',  result: 'success' },
    { id: 6,  time: '2026-10-30 08:30', operator: '赵铁柱', role: 'admin',     module: '账号管理', action: '重置客服密码',            target: 'cs04 · 郑楚',       ip: '10.8.0.32',  result: 'success' },
    { id: 7,  time: '2026-10-30 08:00', operator: '郑楚',   role: 'agent',     module: '客户资料', action: '编辑客户电话',            target: '客户 153****2088',  ip: '10.8.0.48',  result: 'success' },
    { id: 8,  time: '2026-10-29 23:40', operator: '苏小棠', role: 'agent',     module: '客户资料', action: '编辑客户标签',            target: '客户 136****8845',  ip: '10.8.0.45',  result: 'success' },
    { id: 9,  time: '2026-10-29 22:15', operator: '顾青',   role: 'developer', module: '认证',     action: '登录系统',                target: '管理后台',          ip: '10.8.0.13',  result: 'success' },
    { id: 10, time: '2026-10-29 18:22', operator: '赵铁柱', role: 'admin',     module: '账号管理', action: '停用客服账号',            target: 'cs09 · 罗盘',       ip: '10.8.0.32',  result: 'success' },
    { id: 11, time: '2026-10-29 16:48', operator: '林晚',   role: 'admin',     module: '客户资料', action: '编辑客户备注',            target: '客户 137****6600',  ip: '10.8.0.31',  result: 'success' },
    { id: 12, time: '2026-10-29 15:10', operator: '周砚',   role: 'agent',     module: '客户资料', action: '编辑客户城市/标签',       target: '客户 151****4417',  ip: '10.8.0.46',  result: 'success' },
    { id: 13, time: '2026-10-29 14:02', operator: '赵铁柱', role: 'admin',     module: '账号管理', action: '重置客服密码',            target: 'cs04 · 郑楚',       ip: '10.8.0.32',  result: 'success' },
    { id: 14, time: '2026-10-29 11:37', operator: '顾青',   role: 'developer', module: '账号管理', action: '启用客服账号',            target: 'cs06 · 方橙',       ip: '10.8.0.13',  result: 'success' },
    { id: 15, time: '2026-10-29 10:20', operator: '系统',   role: 'developer', module: '同步任务', action: '发送结果确认轮询',        target: '任务 uuid 9f3e…c2', ip: '127.0.0.1',  result: 'fail' },
    { id: 16, time: '2026-10-29 09:54', operator: '林晚',   role: 'admin',     module: '账号管理', action: '新增客服账号',            target: 'cs07 · 何笑',       ip: '10.8.0.31',  result: 'success' },
    { id: 17, time: '2026-10-29 09:12', operator: '韩梅',   role: 'agent',     module: '客户资料', action: '编辑客户电话',            target: '客户 152****9953',  ip: '10.8.0.47',  result: 'success' },
    { id: 18, time: '2026-10-28 23:30', operator: '陈屿',   role: 'developer', module: '认证',     action: '登录失败',                target: '密码连续错误 3 次', ip: '10.8.0.12',  result: 'fail' },
    { id: 19, time: '2026-10-28 21:07', operator: '赵铁柱', role: 'admin',     module: '认证',     action: '登录系统',                target: '管理后台',          ip: '10.8.0.32',  result: 'success' },
    { id: 20, time: '2026-10-28 19:44', operator: '苏小棠', role: 'agent',     module: '客户资料', action: '编辑客户备注',            target: '客户 150****7302',  ip: '10.8.0.45',  result: 'success' },
  ],

  /* 统计：dashboard 读 */
  stats: {
    msgToday: 12847, msgDelta: 6.2,
    agentsOnline: 8, agentsTotal: 11,
    newCustomers: 5,
    successRate: 99.6,
  },
};
