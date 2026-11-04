/* mock.js — 演示数据唯一来源（业务语境：汽配报价客服）
   字段与未来后端接口对齐：
   friend: { id, name, remark, wxid, letter, region, source, added, tags[], note }
   group:  { id, name, member_count, owner, notice, members[{name}], last_active } */

const AVATAR_COLORS = ['#1d5de4', '#18a058', '#f0821e', '#0f3da8', '#1b3468'];

const DB = {
  friends: [
    { id: 1,  name: '何俊杰', remark: '佛山鑫铃 139****9515(测试)', wxid: 'fj_hello88',  letter: 'H', region: '广东 佛山', source: '通过群聊添加', added: '2025-11-03', tags: ['客户', '月结'],   note: '鑫铃佛山仓负责人，报价后需电话确认。' },
    { id: 2,  name: '陈国斌', remark: '泉州鑫铃 138****6652',       wxid: 'chen_gb_88',   letter: 'C', region: '福建 泉州', source: '通过群聊添加', added: '2025-11-12', tags: ['客户', '奔驰超豪'], note: '只收原厂拆车件，副厂勿报。' },
    { id: 3,  name: '吴志明', remark: '广州鑫铃 136****0027',       wxid: 'wzm_gz01',     letter: 'W', region: '广东 广州', source: '对方通过手机号添加', added: '2025-12-01', tags: ['客户'],        note: '常报 09-15 奔驰件，注意核对 VIN。' },
    { id: 4,  name: '黄淑芬', remark: '厦门鑫铃 135****8890',       wxid: 'hsf_66',       letter: 'H', region: '福建 厦门', source: '通过群聊添加', added: '2026-01-08', tags: ['客户'],        note: '' },
    { id: 5,  name: '程雪',   remark: '',                           wxid: 'cx_1024',      letter: 'C', region: '浙江 杭州', source: '同事（市场部）', added: '2025-09-20', tags: ['同事'],        note: '负责义乌客户对接。' },
    { id: 6,  name: '龚丽娜', remark: '',                           wxid: 'gln2022',      letter: 'G', region: '上海',      source: '同事（售后组）', added: '2025-09-20', tags: ['同事'],        note: '' },
    { id: 7,  name: '徐文静', remark: '',                           wxid: 'xwj_kefu',     letter: 'X', region: '广东 深圳', source: '同事（客服组）', added: '2025-10-15', tags: ['同事'],        note: '排班：周一至周五白班。' },
    { id: 8,  name: '邓志强', remark: '强记变速器拆车件',           wxid: 'dzq_parts',    letter: 'D', region: '广东 广州', source: '通过名片添加', added: '2025-08-22', tags: ['供应商', '变速箱'], note: 'CVT/双离合变速箱总成货源稳定。' },
    { id: 9,  name: '李伟',   remark: '德邦物流-郑州站',            wxid: 'liwei_dbl',    letter: 'L', region: '河南 郑州', source: '通过群聊添加', added: '2025-10-02', tags: ['供应商', '物流'],  note: '大件走德邦，运费月结。' },
    { id: 10, name: '冯敏',   remark: '',                           wxid: 'fengmin77',    letter: 'F', region: '湖南 长沙', source: '通过搜索手机号添加', added: '2026-02-14', tags: ['客户'],      note: '' },
    { id: 11, name: '高翔',   remark: '',                           wxid: 'gx_0513',      letter: 'G', region: '江苏 苏州', source: '通过群聊添加', added: '2026-02-20', tags: ['客户', '大众专修'], note: '' },
    { id: 12, name: '林晓梅', remark: '',                           wxid: 'lxmei09',      letter: 'L', region: '福建 泉州', source: '通过群聊添加', added: '2026-03-05', tags: ['客户'],        note: '下午 2 点后在线。' },
    { id: 13, name: '马小军', remark: '',                           wxid: 'mxj_1988',     letter: 'M', region: '陕西 西安', source: '对方通过搜索手机号添加', added: '2026-04-11', tags: ['客户'],    note: '' },
    { id: 14, name: '苏婷',   remark: '',                           wxid: 'suting_vip',   letter: 'S', region: '浙江 义乌', source: '通过群聊添加', added: '2026-05-18', tags: ['客户', '月结'],   note: '义乌件对件对接人。' },
    { id: 15, name: '王大鹏', remark: '',                           wxid: 'wdp_forever',  letter: 'W', region: '山东 青岛', source: '通过群聊添加', added: '2026-06-09', tags: ['客户'],        note: '' },
    { id: 16, name: '张伟豪', remark: '',                           wxid: 'zwh_0303',     letter: 'Z', region: '浙江 义乌', source: '通过群聊添加', added: '2026-07-21', tags: ['客户'],        note: '新客户，首次合作走现结。' },
    { id: 17, name: '周涛',   remark: '',                           wxid: 'zhoutao_9',    letter: 'Z', region: '江西 南昌', source: '通过群聊添加', added: '2026-08-02', tags: ['客户'],        note: '' },
  ],

  groups: [
    {
      id: 101, name: '鑫铃自动报价群', member_count: 46, owner: '何俊杰', last_active: '15:30',
      notice: '报价格式：车型+年份+排量+变速箱型号+车架号；客服 15 分钟内回复，急单请电话联系 139****9515。',
      members: ['何俊杰', '陈国斌', '吴志明', '黄淑芬', '徐文静', '龚丽娜', '邓志强', '冯敏', '高翔', '林晓梅', '苏婷', '张伟豪', '马小军', '王大鹏', '周涛', '程雪'],
    },
    {
      id: 102, name: '泉州鑫铃-奔驰超豪', member_count: 8, owner: '陈国斌', last_active: '15:26',
      notice: '本群只对接奔驰 Super Hao / Raul 平台件，走超豪渠道报价。',
      members: ['陈国斌', '何俊杰', '徐文静', '邓志强', '林晓梅', '程雪'],
    },
    {
      id: 103, name: '广州鑫铃-奔驰超豪', member_count: 12, owner: '吴志明', last_active: '11:32',
      notice: '广州仓发货，下午 5 点前下单当天出库。',
      members: ['吴志明', '何俊杰', '徐文静', '高翔', '冯敏', '龚丽娜'],
    },
    {
      id: 104, name: '厦门鑫铃客服群', member_count: 5, owner: '黄淑芬', last_active: '10:14',
      notice: '',
      members: ['黄淑芬', '何俊杰', '徐文静', '程雪', '龚丽娜'],
    },
    {
      id: 105, name: '变速箱拆车件交流群', member_count: 128, owner: '邓志强', last_active: '昨天',
      notice: '行业交流群：询价请带车型年份+变速箱型号；禁止刷屏广告，违者移出。',
      members: ['邓志强', '何俊杰', '陈国斌', '吴志明', '李伟', '高翔', '马小军', '王大鹏', '周涛', '张伟豪', '苏婷', '冯敏'],
    },
    {
      id: 106, name: '义乌件对件对接群', member_count: 23, owner: '苏婷', last_active: '周三',
      notice: '件对件报价统一走本群，私聊报价不作数。',
      members: ['苏婷', '程雪', '徐文静', '张伟豪', '何俊杰'],
    },
  ],
};

/* 头像颜色按 id 稳定分配（蓝/绿/橙三族，避免花） */
function avatarColor(id) {
  return AVATAR_COLORS[id % AVATAR_COLORS.length];
}
