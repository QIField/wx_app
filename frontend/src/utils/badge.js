/** 未读相关共用工具：徽标文案折叠 + 会话列表未读轮转选取。 */

/** 未读徽标文案：>99 折叠为 99+（UnreadBadge 与 DeviceCards 顶栏卡片共用）。 */
export function formatBadgeCount(count) {
  return count > 99 ? '99+' : String(count)
}

/** 未读轮转选取：从 lastId 之后找第一条未读，末尾回绕到第一条；无未读返回 null。
 *  纯函数（list 即当前展示顺序，含搜索过滤结果），便于单测覆盖多会话/回绕等边界。 */
export function pickNextUnread(list, lastId) {
  const unread = list.filter((c) => c.unread_count > 0)
  if (!unread.length) return null
  const startIdx = list.findIndex((c) => c.id === lastId)
  return unread.find((c) => list.indexOf(c) > startIdx) || unread[0]
}
