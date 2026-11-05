/** 未读徽标文案：>99 折叠为 99+（UnreadBadge 与 DeviceCards 顶栏卡片共用）。 */
export function formatBadgeCount(count) {
  return count > 99 ? '99+' : String(count)
}
