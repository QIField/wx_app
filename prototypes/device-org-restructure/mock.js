/* 演示数据 + API 桩：函数签名即未来真实接口，TODO 处换成 fetch 即可接入后端。 */
(function () {
  const delay = (ms = 320) => new Promise((r) => setTimeout(r, ms));

  const DB = {
    /* 当前演示身份：开发者（绑定操作仅开发者可执行，沿用现有权限） */
    me: { id: 1, username: 'dev01', name: '陈工', role: 'developer' },

    orgs: [
      { id: 1, name: '佛山', status: 1 },
      { id: 2, name: '珠海', status: 1 },
      { id: 3, name: '中山', status: 1 },
      { id: 4, name: '东莞百业', status: 1 },
      { id: 5, name: '东莞合峰', status: 1 },
    ],

    /* 设备字典（新）：openid 全局唯一，必须归属组织；online 由轮询回写 */
    devices: [
      { id: 101, openid: 'wxid_fs01a7k3', name: '佛山一部-01', org_id: 1, online: 1, created_at: '2026-09-02 10:21' },
      { id: 102, openid: 'wxid_fs02b9m4', name: '佛山一部-02', org_id: 1, online: 0, created_at: '2026-09-02 10:24' },
      { id: 103, openid: 'wxid_fs03c2n8', name: '佛山二部-01', org_id: 1, online: 1, created_at: '2026-09-18 14:03' },
      { id: 104, openid: 'wxid_zh01d5p2', name: '珠海一部-01', org_id: 2, online: 1, created_at: '2026-09-20 09:12' },
      { id: 105, openid: 'wxid_zh02e8q6', name: '珠海一部-02', org_id: 2, online: -1, created_at: '2026-09-20 09:15' },
      { id: 106, openid: 'wxid_zs01f3r9', name: '中山一部-01', org_id: 3, online: 0, created_at: '2026-10-08 16:40' },
      { id: 107, openid: 'wxid_zs02g7t4', name: '中山售后组', org_id: 3, online: 1, created_at: '2026-10-08 16:44' },
      { id: 108, openid: 'wxid_dby01h2w', name: '百业客服-01', org_id: 4, online: 1, created_at: '2026-10-15 11:02' },
      { id: 109, openid: 'wxid_dby02j5y', name: '百业客服-02', org_id: 4, online: 0, created_at: '2026-10-15 11:05' },
      { id: 110, openid: 'wxid_dhf01k8a', name: '合峰客服-01', org_id: 5, online: 1, created_at: '2026-10-22 15:37' },
      { id: 111, openid: 'wxid_dhf02l1c', name: '合峰客服-02', org_id: 5, online: -1, created_at: '2026-10-22 15:39' },
      { id: 112, openid: 'wxid_fs04m6d0', name: '佛山机动-01', org_id: 1, online: 0, created_at: '2026-11-01 08:55' },
    ],

    /* 账号：绑定改为 device_ids（引用设备字典），多账号可关联同一台设备，跨组织可选 */
    users: [
      { id: 1, username: 'dev01', name: '陈工', role: 'developer', org_id: null, status: 1, device_ids: [], last_login_at: '2026-11-04 08:30', created_at: '2026-06-01 09:00' },
      { id: 2, username: 'admin1', name: '刘敏', role: 'admin', org_id: 1, status: 1, device_ids: [], last_login_at: '2026-11-03 17:42', created_at: '2026-06-01 09:05' },
      { id: 3, username: 'fs_cs01', name: '黄晓岚', role: 'agent', org_id: 1, status: 1, device_ids: [101, 103], last_login_at: '2026-11-04 08:51', created_at: '2026-06-12 10:18' },
      { id: 4, username: 'fs_cs02', name: '梁俊轩', role: 'agent', org_id: 1, status: 1, device_ids: [101, 102], last_login_at: '2026-11-02 19:07', created_at: '2026-06-12 10:21' },
      { id: 5, username: 'zh_cs01', name: '苏婉清', role: 'agent', org_id: 2, status: 1, device_ids: [104, 105], last_login_at: '2026-11-04 09:02', created_at: '2026-07-03 14:30' },
      { id: 6, username: 'zs_cs01', name: '何俊贤', role: 'agent', org_id: 3, status: 0, device_ids: [106, 107], last_login_at: '2026-10-28 18:20', created_at: '2026-07-15 11:11' },
      { id: 7, username: 'dby_cs01', name: '许安琪', role: 'agent', org_id: 4, status: 1, device_ids: [108], last_login_at: null, created_at: '2026-09-26 09:47' },
    ],
  };

  const orgName = (id) => (DB.orgs.find((o) => o.id === id) || {}).name || '';
  const deviceById = (id) => DB.devices.find((d) => d.id === id) || null;

  const fail = (msg) => { throw new Error(msg); };

  window.API = {
    /* GET /api/admin/orgs */
    async listOrgs() {
      await delay(180);
      return DB.orgs.filter((o) => o.status === 1).map((o) => ({ ...o }));
    },

    /* GET /api/admin/devices —— 列表附关联账号（可多个） */
    async listDevices() {
      await delay();
      return DB.devices.map((d) => ({
        ...d,
        org_name: orgName(d.org_id),
        bound_users: DB.users
          .filter((u) => u.device_ids.includes(d.id))
          .map((u) => ({ id: u.id, name: u.name, username: u.username, org_id: u.org_id, org_name: orgName(u.org_id) })),
      }));
    },

    /* POST /api/admin/devices {openid, name, org_id} */
    async createDevice(p) {
      await delay();
      const openid = (p.openid || '').trim();
      if (!openid) fail('请填写设备 ID');
      if (!(p.name || '').trim()) fail('请填写设备名称');
      if (!p.org_id) fail('请选择所属组织');
      if (DB.devices.some((d) => d.openid === openid)) fail(`设备 ID ${openid} 已存在`);
      const row = {
        id: Math.max(100, ...DB.devices.map((d) => d.id)) + 1,
        openid,
        name: p.name.trim(),
        org_id: p.org_id,
        online: -1,
        created_at: '2026-11-04 10:00',
      };
      DB.devices.push(row);
      return { ...row };
    },

    /* PUT /api/admin/devices/<id> {name, org_id}（openid 录入后不可改） */
    async updateDevice(id, p) {
      await delay();
      const d = deviceById(id) || fail('设备不存在');
      if (!(p.name || '').trim()) fail('请填写设备名称');
      if (!p.org_id) fail('请选择所属组织');
      d.name = p.name.trim();
      d.org_id = p.org_id;
      return { ...d };
    },

    /* DELETE /api/admin/devices/<id> —— 仍被账号关联时 409 */
    async deleteDevice(id) {
      await delay();
      const d = deviceById(id) || fail('设备不存在');
      const n = DB.users.filter((u) => u.device_ids.includes(id)).length;
      if (n) fail(`该设备仍被 ${n} 个账号关联，请先在账号管理中解除关联`);
      DB.devices = DB.devices.filter((x) => x.id !== id);
      return true;
    },

    /* GET /api/admin/accounts —— devices 按绑定顺序展开 */
    async listAccounts() {
      await delay();
      return DB.users.map((u) => ({
        ...u,
        org_name: u.org_id ? orgName(u.org_id) : '',
        devices: u.device_ids
          .map((id) => deviceById(id))
          .filter(Boolean)
          .map((d) => ({ id: d.id, name: d.name, org_id: d.org_id, org_name: orgName(d.org_id) })),
      }));
    },

    /* POST /api/admin/accounts {username, name, role, org_id, device_ids} */
    async createAccount(p) {
      await delay();
      if (!(p.username || '').trim()) fail('请填写登录账号');
      if (!(p.name || '').trim()) fail('请填写姓名');
      if (p.role !== 'developer' && !p.org_id) fail('请选择所属组织');
      if (DB.users.some((u) => u.username === p.username.trim())) fail(`登录账号 ${p.username.trim()} 已存在`);
      validateDevices(p.device_ids || []);
      DB.users.push({
        id: Math.max(...DB.users.map((u) => u.id)) + 1,
        username: p.username.trim(),
        name: p.name.trim(),
        role: p.role,
        org_id: p.role === 'developer' ? null : p.org_id,
        status: 1,
        device_ids: [...(p.device_ids || [])],
        last_login_at: null,
        created_at: '2026-11-04 10:00',
      });
      return true;
    },

    /* PUT /api/admin/accounts/<id> {name, org_id, device_ids} */
    async updateAccount(id, p) {
      await delay();
      const u = DB.users.find((x) => x.id === id) || fail('账号不存在');
      if (!(p.name || '').trim()) fail('请填写姓名');
      if (u.role !== 'developer' && !p.org_id) fail('请选择所属组织');
      validateDevices(p.device_ids || []);
      u.name = p.name.trim();
      u.org_id = u.role === 'developer' ? null : p.org_id;
      u.device_ids = [...(p.device_ids || [])];
      return true;
    },

    /* PUT /api/admin/accounts/<id>/status */
    async toggleAccount(id, status) {
      await delay();
      const u = DB.users.find((x) => x.id === id) || fail('账号不存在');
      u.status = status;
      return true;
    },
  };

  /** 关联校验：设备必须存在（多账号可关联同一台设备）。 */
  function validateDevices(deviceIds) {
    for (const did of deviceIds) {
      if (!deviceById(did)) fail('关联的设备不存在，请刷新后重试');
    }
  }

  window.DB_REF = DB;
})();
