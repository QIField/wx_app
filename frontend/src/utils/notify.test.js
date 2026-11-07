import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { EDGE_BUFFER, MERGE_WINDOW, notifyIncoming, resetNotify, ringDecision, setNotifyBlockedHandler } from './notify'

/** 基准时刻：远离 0，避免与「lastPlayed=0 表示未响过」的哨兵值撞车。 */
const T = 1_000_000

describe('notify · 微信合并提示策略', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(T)
    resetNotify()
  })
  afterEach(() => {
    setNotifyBlockedHandler(null)
    vi.useRealTimers()
  })

  it('ringDecision：满窗口立即响，窗口内排队（边界各取一端）', () => {
    expect(ringDecision(0, MERGE_WINDOW)).toBe('ring') // 恰好到期
    expect(ringDecision(0, MERGE_WINDOW - 1)).toBe('queue') // 差 1ms
    expect(ringDecision(T, T + MERGE_WINDOW)).toBe('ring')
  })

  it('免打扰 / 正在查看 / 系统灰条不响', () => {
    const blocked = vi.fn()
    setNotifyBlockedHandler(blocked)
    expect(notifyIncoming({ muted: true })).toBe(false)
    expect(notifyIncoming({ viewing: true })).toBe(false)
    expect(notifyIncoming({ system: true })).toBe(false)
    expect(notifyIncoming({ muted: true, viewing: true, system: true })).toBe(false)
    expect(blocked).not.toHaveBeenCalled()
  })

  it('首条消息尝试响铃（测试环境无 AudioContext → 拦截上报，且只报一次）', () => {
    const blocked = vi.fn()
    setNotifyBlockedHandler(blocked)
    expect(notifyIncoming({})).toBe(true)
    expect(notifyIncoming({})).toBe(false) // 同时刻再来的消息：窗口内转排队
    expect(blocked).toHaveBeenCalledTimes(1) // dedupe：不刷屏
  })

  it('合并窗口内多条消息一批一响：后续仅排队，到期补响一次', () => {
    const blocked = vi.fn()
    setNotifyBlockedHandler(blocked)
    expect(notifyIncoming({})).toBe(true) // t=T：第一条，响
    vi.setSystemTime(T + 1000)
    expect(notifyIncoming({})).toBe(false) // 窗口内：排队
    vi.setSystemTime(T + 2000)
    expect(notifyIncoming({})).toBe(false) // 窗口内：不重复排队
    expect(blocked).toHaveBeenCalledTimes(1)
    vi.advanceTimersByTime(MERGE_WINDOW + EDGE_BUFFER) // 推进到补响定时器之后
    expect(blocked).toHaveBeenCalledTimes(1) // 补响尝试出声，拦截上报已 dedupe
  })

  it('resetNotify 清掉排队中的补响：到期不再尝试', () => {
    const blocked = vi.fn()
    setNotifyBlockedHandler(blocked)
    notifyIncoming({}) // 响
    vi.setSystemTime(T + 1000)
    notifyIncoming({}) // 排队
    resetNotify()
    vi.advanceTimersByTime(MERGE_WINDOW + EDGE_BUFFER)
    expect(blocked).toHaveBeenCalledTimes(1) // 补响被清，无新尝试
  })

  it('窗口期满后新消息恢复响铃', () => {
    const blocked = vi.fn()
    setNotifyBlockedHandler(blocked)
    notifyIncoming({}) // t=T 响，lastPlayed=T
    vi.setSystemTime(T + MERGE_WINDOW + 1)
    expect(notifyIncoming({})).toBe(true) // 满窗口 → 立即响
    expect(blocked).toHaveBeenCalledTimes(1)
  })
})
