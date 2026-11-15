/**
 * 原型 Mock 数据（纯静态，无后端）。
 *
 * 与真实接口字段对齐：
 * - conversations 对应 GET /api/conversations 出参（转发选择器的目标实体 = 会话，含单聊与群聊）。
 *   单聊会话附带 pinyin / initials（后端 pypinyin 预计算，供三路搜索）。
 * - messages 对应 GET /api/conversations/:id/messages 出参。
 * - favorites 对应 GET /api/favorites 出参。
 * - 转发卡片消息 type='forward_card'，携带 snapshot 快照（合并转发回看不受原消息删除影响）。
 */
window.MOCK = {
  me: { name: '林悦', role: '客服', org: '华东运营' },

  /** 会话列表：也是转发选择器的目标实体 */
  conversations: [
    { id: 21, chat_type: 2, name: '华东区报价群', alias: 'R7C1', member_count: 14, unread: 3, last_msg: '收到，麻烦同步一份 Excel。', last_msg_at: '10:24' },
    { id: 22, chat_type: 1, name: '张伟', alias: 'K2D9', pinyin: 'zhangwei', initials: 'zw', unread: 0, last_msg: '那我等你消息', last_msg_at: '昨天' },
    { id: 23, chat_type: 1, name: '匿名 B41F', alias: 'B41F', unread: 1, last_msg: '[图片]', last_msg_at: '周三' },
    { id: 24, chat_type: 2, name: '安装交付群', alias: 'R9Q2', member_count: 8, unread: 0, last_msg: '明天 9 点到场', last_msg_at: '周二' },
    { id: 25, chat_type: 1, name: '吴桐', alias: 'A7F2', pinyin: 'wutong', initials: 'wt', unread: 0, last_msg: '报价单我更新好了', last_msg_at: '周二' },
    { id: 26, chat_type: 1, name: '王芳', alias: 'D9A0', pinyin: 'wangfang', initials: 'wf', unread: 0, last_msg: '周末收到货了，谢谢', last_msg_at: '周一' },
    { id: 27, chat_type: 1, name: '李杉', alias: 'F3B6', pinyin: 'lishan', initials: 'ls', unread: 0, last_msg: '发票抬头发你', last_msg_at: '周一' },
    { id: 28, chat_type: 1, name: '陈建国', alias: 'H5C2', pinyin: 'chenjianguo', initials: 'cjg', unread: 0, last_msg: '[链接] 报价单模板 V3', last_msg_at: '上周' },
    { id: 29, chat_type: 1, name: '郑凯', alias: 'K1B3', pinyin: 'zhengkai', initials: 'zk', unread: 0, last_msg: '好的', last_msg_at: '上周' },
  ],

  /** 最近转发：转发选择器顶部的常驻头像行（对应 GET /api/forwards/recent） */
  recentForwardIds: [22, 25, 24, 26],

  /**
   * 会话消息：dir 1=收到 2=发出。
   * _deleted: 软删除标记（删除后列表不渲染，数据仍保留，可回收站恢复）。
   */
  messages: {
    21: [
      { type: 'time', label: '今天 10:12' },
      { dir: 1, sender: '陈建国', text: '这批柜子的锁具报价什么时候能给到？' },
      { dir: 1, sender: '赵敏', text: '要含税单价，顺便把上次的差额也带上。' },
      { dir: 2, sender: '林悦', text: '好的，收到。' },
      { type: 'time', label: '今天 10:24' },
      { dir: 2, sender: '林悦', text: '明天上午 10 点前给到，含税单价已更新。' },
      { dir: 1, sender: '陈建国', text: '收到，麻烦同步一份 Excel。' },
      { dir: 1, sender: '吴桐', text: '报价里加上运费和安装费，客户问了好几次了。' },
    ],
    22: [
      { type: 'time', label: '昨天 16:40' },
      { dir: 1, sender: '张伟', text: '方案我看了，第二个柜型先不做。' },
      { dir: 2, sender: '林悦', text: '明白，那我按剩余清单重算报价。' },
      { dir: 1, sender: '张伟', text: '那我等你消息' },
    ],
    23: [
      { type: 'time', label: '周三 09:05' },
      { dir: 1, sender: '匿名 B41F', text: '（图片消息）' },
    ],
    24: [
      { type: 'time', label: '周二 14:30' },
      { dir: 2, sender: '林悦', text: '师傅，明天几点能到场？' },
      { dir: 1, sender: '周婷', text: '明天 9 点到场' },
    ],
    25: [
      { type: 'time', label: '周二 11:08' },
      { dir: 1, sender: '吴桐', text: '报价单我更新好了' },
    ],
    26: [
      { type: 'time', label: '周一 18:22' },
      { dir: 1, sender: '王芳', text: '周末收到货了，谢谢' },
    ],
    27: [
      { type: 'time', label: '周一 09:47' },
      { dir: 1, sender: '李杉', text: '发票抬头发你' },
    ],
    28: [
      { type: 'time', label: '上周五 15:36' },
      { dir: 1, sender: '陈建国', text: '[链接] 报价单模板 V3' },
    ],
    29: [
      { type: 'time', label: '上周四 10:15' },
      { dir: 2, sender: '林悦', text: '样机明早寄出，注意查收。' },
      { dir: 1, sender: '郑凯', text: '好的' },
    ],
  },

  /**
   * 收藏列表：type ∈ text | image | voice | link | note。
   * source = 「来源会话 · 发送者」，deleted = 软删除标记。
   */
  favorites: [
    { id: 'f1', type: 'text', content: '明天上午 10 点前给到，含税单价已更新。', source: '华东区报价群 · 林悦', time: '今天 10:24', tags: ['报价'] },
    { id: 'f2', type: 'image', title: '锁具样品照片', content: '', source: '张伟', time: '昨天 16:42', tags: [] },
    { id: 'f3', type: 'link', title: '《报价单模板 V3》在线文档', desc: 'shimo.im · 协作文档', source: '华东区报价群 · 陈建国', time: '上周五 15:37', tags: ['文档'] },
    { id: 'f4', type: 'note', title: '跟进清单：华东区 11 月', excerpt: '1. 锁具报价复核\n2. 安装排期确认\n3. 尾款催收', source: '收藏笔记', time: '周一 09:12', tags: ['工作'] },
    { id: 'f5', type: 'voice', duration: '0:12', content: '[语音]', source: '张伟', time: '昨天 17:02', tags: [] },
    { id: 'f6', type: 'text', content: '明天 9 点到场', source: '安装交付群 · 周婷', time: '周二 14:31', tags: ['排期'] },
  ],
};
