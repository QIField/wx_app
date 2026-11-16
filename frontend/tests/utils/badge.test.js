/** 未读工具单测：徽标文案 99+ 折叠规则 + 会话列表未读轮转选取（ConvList.locateUnread 共用口径）。 */
import { describe, it, expect } from 'vitest'
import { formatBadgeCount, pickNextUnread } from '../../src/utils/badge'

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

describe('pickNextUnread 未读轮转选取', () => {
  const list = [
    { id: 1, unread_count: 0 },
    { id: 2, unread_count: 3 },
    { id: 3, unread_count: 0 },
    { id: 4, unread_count: 1 },
    { id: 5, unread_count: 2 },
  ]

  it('首次点击（lastId=null）取第一条未读', () => {
    expect(pickNextUnread(list, null).id).toBe(2)
  })

  it('多条未读依次向后轮转', () => {
    expect(pickNextUnread(list, 2).id).toBe(4)
    expect(pickNextUnread(list, 4).id).toBe(5)
  })

  it('末尾回绕：最后一条未读之后回到第一条未读', () => {
    expect(pickNextUnread(list, 5).id).toBe(2)
  })

  it('lastId 不在列表中（已清零/被搜索过滤）从头开始', () => {
    expect(pickNextUnread(list, 999).id).toBe(2)
  })

  it('lastId 已清零但仍在列表：取其之后的第一条未读', () => {
    expect(pickNextUnread(list, 3).id).toBe(4)
  })

  it('无未读返回 null', () => {
    const allRead = list.map((c) => ({ ...c, unread_count: 0 }))
    expect(pickNextUnread(allRead, 2)).toBeNull()
    expect(pickNextUnread([], null)).toBeNull()
  })

  it('只认传入顺序（已读项不跳过位置），被过滤列表只在其可见范围内轮转', () => {
    const filtered = [{ id: 4, unread_count: 1 }, { id: 5, unread_count: 2 }]
    expect(pickNextUnread(filtered, 4).id).toBe(5)
    expect(pickNextUnread(filtered, 5).id).toBe(4)
  })
})
