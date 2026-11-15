/* mock.js — 演示数据唯一来源。
 * 字段与真实后端 /api/conversations 出参对齐（name/chat_type/last_msg/unread/muted/pinned），
 * 便于后续把交互逻辑搬到 ConvList.vue 时逐字段对照。 */
const INITIAL_CONVS = [
  { id: 1,  name: '王海涛',             chat_type: 'single', time: '10:24', last_msg: '好的，报价单收到了，我内部先过一遍', unread: 0, muted: 0, pinned: 1, av: 0 },
  { id: 2,  name: 'SI售后支持群',       chat_type: 'group',  time: '10:02', last_msg: '王工：新版本手册已上传群文件，自取', unread: 0, muted: 1, pinned: 1, av: 1 },
  { id: 3,  name: '陈曼',               chat_type: 'single', time: '昨天',  last_msg: '好的，那就按这个方案执行',           unread: 0, muted: 0, pinned: 0, av: 2 },
  { id: 4,  name: '深圳蓝鲸科技-何经理', chat_type: 'single', time: '昨天',  last_msg: '何经理：合同盖章版明天寄出',         unread: 0, muted: 0, pinned: 0, av: 3 },
  { id: 5,  name: '刘子豪',             chat_type: 'single', time: '周三',  last_msg: '收到，我这边同步给车间',             unread: 0, muted: 0, pinned: 0, av: 4 },
  { id: 6,  name: 'SI产品交流群',       chat_type: 'group',  time: '周三',  last_msg: '林工：3D 图 STEP 格式已上传',        unread: 0, muted: 1, pinned: 0, av: 5 },
  { id: 7,  name: '周正阳',             chat_type: 'single', time: '周二',  last_msg: '嗯，数量按 800 件报',                unread: 0, muted: 0, pinned: 0, av: 0 },
  { id: 8,  name: '林芳',               chat_type: 'single', time: '周二',  last_msg: '图纸批注我标好了，重点看第 3 页装配间隙', unread: 8, muted: 0, pinned: 0, av: 1 },
  { id: 9,  name: '东莞恒达五金-张生',   chat_type: 'single', time: '周一',  last_msg: '这批货周五之前能安排发出吗？',        unread: 2, muted: 1, pinned: 0, av: 2 },
  { id: 10, name: '采购一部对接群',     chat_type: 'group',  time: '11-08', last_msg: '曹工：明天上午十点腾讯会议对参数',    unread: 5, muted: 0, pinned: 0, av: 3 },
  { id: 11, name: '李晓雯',             chat_type: 'single', time: '11-08', last_msg: '麻烦把这两票的对账单发我一下',        unread: 1, muted: 0, pinned: 0, av: 4 },
  { id: 12, name: '孙悦',               chat_type: 'single', time: '11-07', last_msg: '样品收到了，外观有两处小瑕疵，看下图', unread: 2, muted: 0, pinned: 0, av: 5 },
  { id: 13, name: '系统通知助手',       chat_type: 'single', time: '11-06', last_msg: '您的工单 #20481 已处理完成，请评价',  unread: 1, muted: 1, pinned: 0, av: 0 },
  { id: 14, name: '郑州广汇机械-曹工',   chat_type: 'single', time: '11-05', last_msg: '焊缝探伤报告出来了，两件不合格',      unread: 3, muted: 0, pinned: 0, av: 1 },
  { id: 15, name: '赵倩',               chat_type: 'single', time: '11-04', last_msg: '周一看完产线再给你答复',             unread: 0, muted: 0, pinned: 0, av: 2 },
  { id: 16, name: '郭涛',               chat_type: 'single', time: '11-01', last_msg: '发票信息我私发你了，查收',           unread: 0, muted: 0, pinned: 0, av: 3 },
  { id: 17, name: '吴一凡',             chat_type: 'single', time: '10-30', last_msg: '这款还能做阳极氧化金色吗？',         unread: 0, muted: 0, pinned: 0, av: 4 },
  { id: 18, name: '冯雪',               chat_type: 'single', time: '10-28', last_msg: '明天店铺盘点，晚点回复你',           unread: 0, muted: 0, pinned: 0, av: 5 },
];

/* 模拟新消息可用的候选文案（随机取一条，保持业务语境真实） */
const INCOMING_TEXTS = [
  '您好，在吗？刚发的那份文件麻烦看下～',
  '这个价格含运费吗？',
  '上次说的样品大概什么时候能到？',
  '合同那边法务还要再改两个字',
  '麻烦帮我查一下这单的物流',
];
