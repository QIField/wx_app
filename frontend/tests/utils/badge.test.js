/** formatBadgeCount 徽标文案单测：未读红点 99+ 折叠规则的共用口径（UnreadBadge / DeviceCards）。 */
import { describe, it, expect } from 'vitest'
import { formatBadgeCount } from '../../src/utils/badge'

describe('formatBadgeCount 徽标文案', () => {
  it('正常区间显示原数', () => {
    expect(formatBadgeCount(1)).toBe('1')
    expect(formatBadgeCount(99)).toBe('99')
  })

  it('超过 99 折叠为 99+', () => {
    expect(formatBadgeCount(100)).toBe('99+')
    expect(formatBadgeCount(12345)).toBe('99+')
  })

  it('0 原样返回（是否渲染由调用方 v-if 决定）', () => {
    expect(formatBadgeCount(0)).toBe('0')
  })
})
