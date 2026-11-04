/* ===== mock.js · 种子数据（与后端模型字段对齐）=====
 * User: id/username/name/role + devices[]（改造后：一人多设备）
 * Conversation: openid+wxid 唯一，按设备隔离
 * Message: dir 1收/2发；dir=2 必带 operator（溯源核心字段）
 */
window.MOCK = (() => {
  const devices = [
    { openid: 'dev_a01', wxid: 'wx_kf01', nickname: '产品咨询号', online: true,  color: '#1d5de4' },
    { openid: 'dev_b02', wxid: 'wx_kf02', nickname: '售后支持号', online: true,  color: '#0e9888' },
    { openid: 'dev_c03', wxid: 'wx_kf03', nickname: 'VIP客户号',  online: true,  color: '#c2611f' },
    { openid: 'dev_d04', wxid: 'wx_kf04', nickname: '渠道合作号', online: false, color: '#7a5af5' },
  ];

  const users = [
    { id: 5, username: 'cs01', name: '吴桐', role: 'agent', devices: ['dev_a01', 'dev_b02', 'dev_c03'] },
    { id: 6, username: 'cs02', name: '李杉', role: 'agent', devices: ['dev_d04'] },
    { id: 1, username: 'dev01', name: '沈砚', role: 'developer', devices: ['dev_a01'] },
  ];

  const T = (h, m) => `2026-11-02 ${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;

  /* v6：会话增加 muted（消息免打扰 0/1），与后端 conversation.muted 对齐 */
  const conversations = [
    { id: 101, openid: 'dev_a01', wxid: 'zhang_wei',   chat_type: 1, name: '张伟',            unread_count: 2, pinned: 1, muted: 0, last_msg: '你们这款的交期最快多久？', last_msg_at: T(14, 32) },
    { id: 102, openid: 'dev_a01', wxid: 'dealer_south', chat_type: 2, name: '华南经销商交流群', unread_count: 5, pinned: 0, muted: 1, last_msg: '孙经理: 报价单收到了，我核对下', last_msg_at: T(14, 21) },
    { id: 103, openid: 'dev_a01', wxid: 'li_na',        chat_type: 1, name: '李娜',            unread_count: 0, pinned: 0, muted: 0, last_msg: '好的，那就按这个方案来', last_msg_at: T(11, 47) },
    { id: 104, openid: 'dev_b02', wxid: 'chen_jl',      chat_type: 1, name: '华丰物流-陈经理',  unread_count: 1, pinned: 0, muted: 0, last_msg: '这批货有 3 件外箱破损', last_msg_at: T(14, 05) },
    { id: 105, openid: 'dev_b02', wxid: 'meiju_liu',    chat_type: 1, name: '美居装饰-刘工',    unread_count: 0, pinned: 0, muted: 0, last_msg: '安装视频我看完了，没问题', last_msg_at: T(10, 18) },
    { id: 106, openid: 'dev_b02', wxid: 'proj_group_a', chat_type: 2, name: 'A项目对接群',      unread_count: 3, pinned: 1, muted: 0, last_msg: '赵总: 周三上午10点现场对一下', last_msg_at: T(13, 44) },
    { id: 107, openid: 'dev_c03', wxid: 'zhao_zt',      chat_type: 1, name: '恒泰地产-赵总',    unread_count: 0, pinned: 0, muted: 0, last_msg: '合同盖章件明天寄出', last_msg_at: T(9, 52) },
    { id: 108, openid: 'dev_c03', wxid: 'sun_star',     chat_type: 1, name: '星辰电子-孙经理',  unread_count: 4, pinned: 0, muted: 1, last_msg: '上一批的良率报告发我一份', last_msg_at: T(14, 40) },
  ];

  let mid = 0;
  const m = (conv_id, dir, sender_name, content, time, status, operator) =>
    ({ id: ++mid, conv_id, dir, msg_type: 1, sender_name, content, time, status, operator: operator || null });

  const messages = [
    m(101, 1, '张伟', '你好，看到你们官网的新款型号', T(14, 25)),
    m(101, 1, '张伟', '你们这款的交期最快多久？', T(14, 32)),
    m(102, 1, '孙经理', '报价单收到了，我核对下', T(14, 21)),
    m(102, 2, '吴桐', '报价有效期 30 天，有问题随时找我', T(13, 55), 1, { username: 'cs01', name: '吴桐', device: 'dev_a01' }),
    m(103, 1, '李娜', '方案我看没问题', T(11, 40)),
    m(103, 2, '吴桐', '那我就按这份清单给您排产了', T(11, 46), 1, { username: 'cs01', name: '吴桐', device: 'dev_a01' }),
    m(103, 1, '李娜', '好的，那就按这个方案来', T(11, 47)),
    m(104, 1, '华丰物流-陈经理', '这批货有 3 件外箱破损', T(14, 5)),
    m(105, 2, '吴桐', '安装视频已发您邮箱，注意第 4 步的固定件方向', T(10, 12), 1, { username: 'cs01', name: '吴桐', device: 'dev_b02' }),
    m(105, 1, '美居装饰-刘工', '安装视频我看完了，没问题', T(10, 18)),
    m(106, 1, '赵总', '周三上午10点现场对一下', T(13, 44)),
    m(107, 2, '吴桐', '合同盖章件明天给您寄出，运单号同步您', T(9, 50), 1, { username: 'cs01', name: '吴桐', device: 'dev_c03' }),
    m(107, 1, '恒泰地产-赵总', '合同盖章件明天寄出', T(9, 52)),
    m(108, 1, '星辰电子-孙经理', '上一批的良率报告发我一份', T(14, 40)),
    m(108, 1, '星辰电子-孙经理', '另外新订单的数量想再确认下', T(14, 41)),
  ];

  /* 通讯录（按聊天账号隔离；与 conversations 的 wxid 对齐，无会话联系人用于演示搜索分组） */
  const contacts = [
    { id: 1,  openid: 'dev_a01', name: '张伟',             wxid: 'zhang_wei',   remark: '采购经理' },
    { id: 2,  openid: 'dev_a01', name: '张强',             wxid: 'wx_zq_2201',  remark: '意向客户-展会加的' },
    { id: 3,  openid: 'dev_a01', name: '李娜',             wxid: 'li_na',       remark: '' },
    { id: 4,  openid: 'dev_a01', name: '周雪',             wxid: 'xue_zhou',    remark: '样机测评' },
    { id: 5,  openid: 'dev_b02', name: '华丰物流-陈经理',  wxid: 'chen_jl',     remark: '' },
    { id: 6,  openid: 'dev_b02', name: '美居装饰-刘工',    wxid: 'meiju_liu',   remark: '' },
    { id: 7,  openid: 'dev_b02', name: '张成',             wxid: 'zc_service',  remark: 'A项目-施工方' },
    { id: 8,  openid: 'dev_b02', name: '王芳',             wxid: 'fang_wang',   remark: '售后回访' },
    { id: 9,  openid: 'dev_c03', name: '恒泰地产-赵总',    wxid: 'zhao_zt',     remark: '' },
    { id: 10, openid: 'dev_c03', name: '星辰电子-孙经理',  wxid: 'sun_star',    remark: '' },
    { id: 11, openid: 'dev_c03', name: '张总-铭泰',        wxid: 'zt_mingtai',  remark: '潜在大客户' },
  ];

  const send_logs = [
    { id: 1, time: T(13, 55), operator_username: 'cs01', operator_name: '吴桐', device: '产品咨询号', conv_name: '华南经销商交流群', action: '发送文本', content: '报价有效期 30 天，有问题随时找我', result: '已发送' },
    { id: 2, time: T(11, 46), operator_username: 'cs01', operator_name: '吴桐', device: '产品咨询号', conv_name: '李娜', action: '发送文本', content: '那我就按这份清单给您排产了', result: '已发送' },
    { id: 3, time: T(10, 12), operator_username: 'cs01', operator_name: '吴桐', device: '售后支持号', conv_name: '美居装饰-刘工', action: '发送文本', content: '安装视频已发您邮箱，注意第 4 步的固定件方向', result: '已发送' },
    { id: 4, time: T(9, 50),  operator_username: 'cs01', operator_name: '吴桐', device: 'VIP客户号',  conv_name: '恒泰地产-赵总', action: '发送文本', content: '合同盖章件明天给您寄出，运单号同步您', result: '已发送' },
  ];

  /* ws-sim：定时注入的来消息（覆盖 scope 外设备，验证跨账号提醒） */
  const incoming_pool = [
    { conv_id: 104, sender_name: '华丰物流-陈经理', content: '破损的 3 件麻烦今天给我个处理方案' },
    { conv_id: 108, sender_name: '星辰电子-孙经理', content: '数量按 5000 套报，急' },
    { conv_id: 106, sender_name: '赵总', content: '周三的会提前到 9 点半可以吗' },
    { conv_id: 102, sender_name: '周雪', content: '样机我这边测试完了，回头发测评' },
    { conv_id: 101, sender_name: '张伟', content: '对了，能开 13% 的专票吗' },
  ];

  return { devices, users, conversations, contacts, messages, send_logs, incoming_pool };
})();
