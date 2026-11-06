/** 演示会话 mock 数据：覆盖三层表情形态的真实客服场景。
 * message: { id, direction(1入/2出), msg_type(1文本/7表情图), content, sender }
 */
const STICKER_URL = `${import.meta.env.BASE_URL}wx-faces/92.png` // 跳跳企鹅当 msg_type=7 样例

export const DEMO_CONV = { name: '张女士（客户）', agent: '客服小王' }

export const DEMO_MESSAGES = [
  { id: 1, direction: 1, msg_type: 1, content: '你好呀，请问上次买的茶叶礼盒还有货吗？[微笑]', sender: '张女士' },
  { id: 2, direction: 2, msg_type: 1, content: '您好～礼盒有货的 [愉快] 现在下单今天就能发出。', sender: '客服小王' },
  { id: 3, direction: 1, msg_type: 7, content: STICKER_URL, sender: '张女士' },
  { id: 4, direction: 1, msg_type: 1, content: '那再来两盒！物流单号记得发我一下哈 [捂脸] 上次找半天没找到 😂', sender: '张女士' },
  { id: 5, direction: 2, msg_type: 1, content: '好嘞 [抱拳] 发货后第一时间同步给您，注意查收～', sender: '客服小王' },
  { id: 6, direction: 1, msg_type: 1, content: '[强][强][强] 你们服务真棒，给你们点赞 👍', sender: '张女士' },
]

/** 发送后的自动回包池（演示交互效果，接入真实后端后删除）。 */
export const AUTO_REPLIES = [
  '收到啦 [愉快]',
  '好哒好哒 [跳跳]',
  '明白了，谢谢你呀 [微笑]',
  '[捂脸] 我再看看订单',
  '哈哈哈哈 [偷笑]',
  '棒！[爱心]',
]
