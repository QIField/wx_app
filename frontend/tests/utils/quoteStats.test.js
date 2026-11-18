import { describe, expect, it } from 'vitest'
import { barPercent, maxOf, trendBadge, trendPercent } from '../../src/utils/quoteStats'

describe('trendPercent 当期 vs 上期', () => {
  it('正常百分比取整', () => {
    expect(trendPercent(12, 10)).toBe(20)
    expect(trendPercent(5, 10)).toBe(-50)
    expect(trendPercent(10, 10)).toBe(0)
  })

  it('上期为 0：有量显示「新增」(null)，双 0 持平', () => {
    expect(trendPercent(3, 0)).toBeNull()
    expect(trendPercent(0, 0)).toBe(0)
  })
})

describe('trendBadge 徽标', () => {
  it('上涨/下跌/持平/新增', () => {
    expect(trendBadge(20)).toEqual({ text: '▲ 20%', cls: 'up' })
    expect(trendBadge(-50)).toEqual({ text: '▼ 50%', cls: 'down' })
    expect(trendBadge(0)).toEqual({ text: '持平', cls: '' })
    expect(trendBadge(null)).toEqual({ text: '新增', cls: 'up' })
  })
})

describe('barPercent 柱高', () => {
  it('按最大值归一化，>0 保底 6%，封顶 100%', () => {
    expect(barPercent(5, 10)).toBe(50)
    expect(barPercent(0.1, 10)).toBe(6)
    expect(barPercent(20, 10)).toBe(100)
    expect(barPercent(0, 10)).toBe(0)
    expect(barPercent(5, 0)).toBe(0)
  })
})

describe('maxOf 系列最大值', () => {
  it('取最大，全 0/空返回 0', () => {
    expect(maxOf([1, 5, 3])).toBe(5)
    expect(maxOf([0, 0])).toBe(0)
    expect(maxOf([])).toBe(0)
    expect(maxOf(undefined)).toBe(0)
  })
})
