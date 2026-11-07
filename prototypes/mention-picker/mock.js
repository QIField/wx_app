/**
 * 原型 Mock 数据（纯静态，无后端）。
 *
 * 与真实接口的字段对齐：
 * - members 对应 GET /api/conversations/:id/members 的出参（脱敏：不含 wxid）。
 *   pinyin / initials 由后端 pypinyin 预计算，前端不再引 JS 拼音库。
 * - messages 对应 GET /api/conversations/:id/messages 的出参。
 * - payload.at_ids 是群成员行号（group_member.id），服务端再换算成 ats=wxid 串。
 */
window.MOCK = {
  me: { name: '林悦', role: '客服', org: '华东运营' },

  conversations: [
    {
      id: 21, chat_type: 2, name: '华东区报价群', alias: 'R7C1',
      unread: 3, last_msg: '收到，麻烦同步一份 Excel。', last_msg_at: '10:24',
    },
    {
      id: 22, chat_type: 1, name: '张伟', alias: 'K2D9',
      unread: 0, last_msg: '那我等你消息', last_msg_at: '昨天',
    },
    {
      id: 23, chat_type: 1, name: '匿名 B41F', alias: 'B41F',
      unread: 1, last_msg: '[图片]', last_msg_at: '周三',
    },
    {
      id: 24, chat_type: 2, name: '安装交付群', alias: 'R9Q2',
      unread: 0, last_msg: '明天 9 点到场', last_msg_at: '周二',
    },
  ],

  /** 群成员名册：pinyin=全拼（无声调、小写），initials=拼音首字母 */
  members: [
    { id: 101, name: '吴桐',   pinyin: 'wutong',     initials: 'wt',  alias: 'A7F2', tag: '群主' },
    { id: 102, name: '张伟',   pinyin: 'zhangwei',   initials: 'zw',  alias: 'C1E8' },
    { id: 103, name: '李杉',   pinyin: 'lishan',     initials: 'ls',  alias: 'F3B6' },
    { id: 104, name: '王芳',   pinyin: 'wangfang',   initials: 'wf',  alias: 'D9A0' },
    { id: 105, name: '陈建国', pinyin: 'chenjianguo', initials: 'cjg', alias: 'H5C2' },
    { id: 106, name: '赵敏',   pinyin: 'zhaomin',    initials: 'zm',  alias: 'B8D4' },
    { id: 107, name: '刘洋',   pinyin: 'liuyang',    initials: 'ly',  alias: 'E2F7' },
    { id: 108, name: '孙立',   pinyin: 'sunli',      initials: 'sl',  alias: 'G6A1' },
    { id: 109, name: '周婷',   pinyin: 'zhouting',   initials: 'zt',  alias: 'J4E9' },
    { id: 110, name: '郑凯',   pinyin: 'zhengkai',   initials: 'zk',  alias: 'K1B3' },
    { id: 111, name: '何静',   pinyin: 'hejing',     initials: 'hj',  alias: 'L7D8' },
    { id: 112, name: '高远',   pinyin: 'gaoyuan',    initials: 'gy',  alias: 'M2C5' },
    { id: 113, name: '徐磊',   pinyin: 'xulei',      initials: 'xl',  alias: 'N8F1' },
    { id: 114, name: '马晓雨', pinyin: 'maxiaoyu',   initials: 'mxy', alias: 'P3A7' },
  ],

  /** 群成员按会话取：真实接口是 GET /api/conversations/:id/members */
  membersByConv: {},

  /** 会话消息：dir 1=收到 2=发出；text 里的 @昵称 后跟 U+2005（微信 @ 分隔符） */
  messages: {
    21: [
      { type: 'time', label: '今天 10:12' },
      { dir: 1, sender: '陈建国', text: '这批柜子的锁具报价什么时候能给到？' },
      { dir: 1, sender: '赵敏', text: '要含税单价，顺便把上次的差额也带上。' },
      { dir: 2, sender: '林悦', text: '好的，收到。' },
      { type: 'time', label: '今天 10:24' },
      { dir: 2, sender: '林悦', text: '@陈建国\u2005 明天上午 10 点前给到，含税单价已更新。' },
      { dir: 1, sender: '陈建国', text: '收到，麻烦同步一份 Excel。' },
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
  },
};

// 名册按会话挂载（对应真实接口 GET /api/conversations/:id/members）
window.MOCK.membersByConv = {
  21: window.MOCK.members,
  24: window.MOCK.members.slice(0, 5),
};
