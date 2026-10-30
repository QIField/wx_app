/* ===== mock.js · 单一数据源（所有页面从这里读数据，禁止散落硬编码） ===== */
const DB = {
  /* 账号：13 条，覆盖 3 角色与启用/停用状态 */
  users: [
    { id: 1,  username: 'dev',     name: '陈屿',   role: 'developer', dept: '技术部',          phone: '138****2210', status: 'active',   last_login: '2026-10-30 09:12', created: '2025-06-01' },
    { id: 2,  username: 'dev02',   name: '顾青',   role: 'developer', dept: '技术部',          phone: '139****8845', status: 'active',   last_login: '2026-10-29 21:03', created: '2025-09-14' },
    { id: 3,  username: 'admin01', name: '林晚',   role: 'admin',     dept: '客服中心 · 运营组', phone: '137****6621', status: 'active',   last_login: '2026-10-30 08:47', created: '2025-06-01' },
    { id: 4,  username: 'admin02', name: '赵铁柱', role: 'admin',     dept: '客服中心 · 质检组', phone: '136****3390', status: 'active',   last_login: '2026-10-29 18:20', created: '2025-07-22' },
    { id: 5,  username: 'cs01',    name: '苏小棠', role: 'agent',     dept: '客服一组',         phone: '150****7302', status: 'active',   last_login: '2026-10-30 08:55', created: '2025-08-05' },
    { id: 6,  username: 'cs02',    name: '周砚',   role: 'agent',     dept: '客服一组',         phone: '151****4417', status: 'active',   last_login: '2026-10-30 08:51', created: '2025-08-05' },
    { id: 7,  username: 'cs03',    name: '韩梅',   role: 'agent',     dept: '客服二组',         phone: '152****9953', status: 'active',   last_login: '2026-10-30 09:02', created: '2025-10-11' },
    { id: 8,  username: 'cs04',    name: '郑楚',   role: 'agent',     dept: '客服二组',         phone: '153****2088', status: 'active',   last_login: '2026-10-29 19:44', created: '2025-10-11' },
    { id: 9,  username: 'cs05',    name: '吴桐',   role: 'agent',     dept: '客服三组',         phone: '155****6104', status: 'active',   last_login: '2026-10-30 08:58', created: '2025-12-03' },
    { id: 10, username: 'cs06',    name: '方橙',   role: 'agent',     dept: '客服三组',         phone: '156****8721', status: 'disabled', last_login: '2026-09-30 17:26', created: '2025-12-03' },
    { id: 11, username: 'cs07',    name: '何笑',   role: 'agent',     dept: '客服一组',         phone: '157****5540', status: 'active',   last_login: '2026-10-30 09:05', created: '2026-02-18' },
    { id: 12, username: 'cs08',    name: '白露',   role: 'agent',     dept: '客服二组',         phone: '158****3067', status: 'active',   last_login: '2026-10-30 08:49', created: '2026-09-01' },
    { id: 13, username: 'cs09',    name: '罗盘',   role: 'agent',     dept: '客服三组',         phone: '159****1178', status: 'disabled', last_login: '2026-10-12 11:33', created: '2026-09-01' },
  ],

  /* 权限矩阵：12 项功能 × 3 角色（booleans，roles.html 直接读写） */
  permissions: [
    { key: 'workbench',       name: '聊天工作台',       desc: '收发消息、查看分配给自己的会话', group: '消息',   roles: { developer: true, admin: true,  agent: true } },
    { key: 'assign',          name: '会话分配',         desc: '将新会话指派给在线客服',       group: '消息',   roles: { developer: true, admin: true,  agent: false } },
    { key: 'customer.edit',   name: '客户资料编辑',     desc: '电话 / 城市 / 标签 / 备注',     group: '消息',   roles: { developer: true, admin: true,  agent: true } },
    { key: 'customer.export', name: '数据导出',         desc: '导出消息统计与客户清单',       group: '消息',   roles: { developer: true, admin: true,  agent: false } },
    { key: 'accounts.agent',  name: '客服账号管理',     desc: '增删改客服账号、启停用',       group: '账号',   roles: { developer: true, admin: true,  agent: false } },
    { key: 'accounts.admin',  name: '管理员账号管理',   desc: '管理员账号的维护与角色调整',   group: '账号',   roles: { developer: true, admin: false, agent: false } },
    { key: 'accounts.dev',    name: '开发者账号管理',   desc: '仅最高权限可维护',             group: '账号',   roles: { developer: true, admin: false, agent: false } },
    { key: 'roles.view',      name: '权限矩阵查看',     desc: '查看各角色功能边界',           group: '系统',   roles: { developer: true, admin: true,  agent: false } },
    { key: 'roles.edit',      name: '权限矩阵编辑',     desc: '调整角色功能授权',             group: '系统',   roles: { developer: true, admin: false, agent: false } },
    { key: 'system.config',   name: '系统配置',         desc: '中间方接口密钥 / WebSocket / 轮询间隔', group: '系统', roles: { developer: true, admin: false, agent: false } },
    { key: 'system.sync',     name: '手动触发同步',     desc: '重置同步游标、补拉消息',       group: '系统',   roles: { developer: true, admin: false, agent: false } },
    { key: 'logs.view',       name: '操作日志查看',     desc: '审计全部后台操作',             group: '系统',   roles: { developer: true, admin: true,  agent: false } },
  ],

  /* 审计日志：20 条，跨页一致（dashboard 只取前 5） */
  logs: [
    { id: 1,  time: '2026-10-30 09:12', operator: '陈屿',   role: 'developer', module: '系统配置', action: '更新中间方接口密钥',      target: '中间方适配器',      ip: '10.8.0.12',  result: 'success' },
    { id: 2,  time: '2026-10-30 09:03', operator: '林晚',   role: 'admin',     module: '会话分配', action: '将会话 #4821 分配给客服', target: '苏小棠',            ip: '10.8.0.31',  result: 'success' },
    { id: 3,  time: '2026-10-30 09:01', operator: '林晚',   role: 'admin',     module: '账号管理', action: '新增客服账号',            target: 'cs08 · 白露',       ip: '10.8.0.31',  result: 'success' },
    { id: 4,  time: '2026-10-30 08:55', operator: '陈屿',   role: 'developer', module: '权限管理', action: '调整权限矩阵：会话分配',  target: '管理员 +会话分配',  ip: '10.8.0.12',  result: 'success' },
    { id: 5,  time: '2026-10-30 08:41', operator: '苏小棠', role: 'agent',     module: '客户资料', action: '编辑客户备注',            target: '客户 138****7302',  ip: '10.8.0.45',  result: 'success' },
    { id: 6,  time: '2026-10-30 08:30', operator: '赵铁柱', role: 'admin',     module: '数据导出', action: '导出昨日消息统计',        target: '2026-10-29.xlsx',   ip: '10.8.0.32',  result: 'success' },
    { id: 7,  time: '2026-10-30 08:00', operator: '系统',   role: 'developer', module: '同步任务', action: '消息增量同步',            target: '游标 2026-10-30 07:59', ip: '127.0.0.1', result: 'success' },
    { id: 8,  time: '2026-10-29 23:40', operator: '陈屿',   role: 'developer', module: '系统配置', action: '重启 WebSocket 推送服务', target: 'ws 服务',           ip: '10.8.0.12',  result: 'success' },
    { id: 9,  time: '2026-10-29 22:15', operator: '顾青',   role: 'developer', module: '同步任务', action: '手动补拉历史消息',        target: '游标回拨 24h',      ip: '10.8.0.13',  result: 'success' },
    { id: 10, time: '2026-10-29 18:22', operator: '赵铁柱', role: 'admin',     module: '账号管理', action: '停用客服账号',            target: 'cs09 · 罗盘',       ip: '10.8.0.32',  result: 'success' },
    { id: 11, time: '2026-10-29 16:48', operator: '林晚',   role: 'admin',     module: '会话分配', action: '批量转移会话（8 条）',    target: '客服二组',          ip: '10.8.0.31',  result: 'success' },
    { id: 12, time: '2026-10-29 15:10', operator: '周砚',   role: 'agent',     module: '客户资料', action: '编辑客户城市/标签',       target: '客户 151****4417',  ip: '10.8.0.46',  result: 'success' },
    { id: 13, time: '2026-10-29 14:02', operator: '赵铁柱', role: 'admin',     module: '账号管理', action: '重置客服密码',            target: 'cs04 · 郑楚',       ip: '10.8.0.32',  result: 'success' },
    { id: 14, time: '2026-10-29 11:37', operator: '顾青',   role: 'developer', module: '系统配置', action: '修改轮询间隔 5s → 3s',    target: '同步定时器',        ip: '10.8.0.13',  result: 'success' },
    { id: 15, time: '2026-10-29 10:20', operator: '系统',   role: 'developer', module: '同步任务', action: '发送结果确认轮询',        target: '任务 uuid 9f3e…c2', ip: '127.0.0.1',  result: 'fail' },
    { id: 16, time: '2026-10-29 09:54', operator: '林晚',   role: 'admin',     module: '数据导出', action: '导出客服绩效月报',        target: '2026-09 绩效.xlsx', ip: '10.8.0.31',  result: 'success' },
    { id: 17, time: '2026-10-29 09:12', operator: '韩梅',   role: 'agent',     module: '客户资料', action: '编辑客户电话',            target: '客户 152****9953',  ip: '10.8.0.47',  result: 'success' },
    { id: 18, time: '2026-10-28 23:30', operator: '陈屿',   role: 'developer', module: '系统配置', action: '切换数据库 dev → prod',   target: '.env · APP_ENV',    ip: '10.8.0.12',  result: 'fail' },
    { id: 19, time: '2026-10-28 21:07', operator: '赵铁柱', role: 'admin',     module: '会话分配', action: '将会话 #4790 分配给客服', target: '吴桐',              ip: '10.8.0.32',  result: 'success' },
    { id: 20, time: '2026-10-28 19:44', operator: '苏小棠', role: 'agent',     module: '客户资料', action: '编辑客户备注',            target: '客户 150****7302',  ip: '10.8.0.45',  result: 'success' },
  ],

  /* 统计：dashboard 读 */
  stats: {
    msgToday: 12847, msgDelta: 6.2,
    agentsOnline: 8, agentsTotal: 11,
    pendingConv: 3,
    successRate: 99.6,
    syncLag: '2.4s', wsOnline: 12, apiOk: true,
    trend: [
      { day: '10-24', val: 9210 },
      { day: '10-25', val: 8640 },
      { day: '10-26', val: 10480 },
      { day: '10-27', val: 11890 },
      { day: '10-28', val: 11020 },
      { day: '10-29', val: 12095 },
      { day: '10-30', val: 12847 },
    ],
  },

  /* 在线客服（dashboard 侧栏） */
  onlineAgents: [
    { name: '苏小棠', dept: '客服一组', serving: 6,  state: 'online' },
    { name: '周砚',   dept: '客服一组', serving: 4,  state: 'online' },
    { name: '何笑',   dept: '客服一组', serving: 5,  state: 'online' },
    { name: '韩梅',   dept: '客服二组', serving: 7,  state: 'online' },
    { name: '白露',   dept: '客服二组', serving: 3,  state: 'online' },
    { name: '郑楚',   dept: '客服二组', serving: 2,  state: 'busy'   },
    { name: '吴桐',   dept: '客服三组', serving: 4,  state: 'online' },
    { name: '陈屿',   dept: '技术部',   serving: 1,  state: 'online' },
  ],
};
