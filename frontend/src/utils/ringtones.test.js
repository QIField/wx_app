import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  CUSTOM_PREFIX,
  DEFAULT_RING,
  getCustomRingtones,
  getRingtone,
  isCustomId,
  loadRingtone,
  setCustomRingtones,
} from './ringtones'

/** jsdom 不可用（vitest 默认 node 环境）：stub 一个最小 localStorage。 */
const store = new Map()
vi.stubGlobal('localStorage', {
  getItem: (k) => (store.has(k) ? store.get(k) : null),
  setItem: (k, v) => store.set(k, String(v)),
  removeItem: (k) => store.delete(k),
})

const LS_KEY = 'notify.ringtone.v1'
const ROWS = [
  { id: 11, name: '轻快鸟鸣', url: '/media/ringtones/a.mp3', fmt: 'mp3', size: 100 },
  { id: 12, name: '复古电话', url: '/media/ringtones/b.wav', fmt: 'wav', size: 200 },
]

describe('ringtones · 自定义铃声 id 与兜底', () => {
  beforeEach(() => {
    store.clear()
    setCustomRingtones([]) // 每例重置缓存，防止用例间串扰
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('isCustomId：仅 custom: 前缀字符串为真', () => {
    expect(isCustomId('custom:11')).toBe(true)
    expect(isCustomId(`${CUSTOM_PREFIX}1`)).toBe(true)
    expect(isCustomId('ding-dong')).toBe(false)
    expect(isCustomId(11)).toBe(false)
    expect(isCustomId(null)).toBe(false)
    expect(isCustomId('')).toBe(false)
  })

  it('setCustomRingtones：行 id 映射为 custom: 前缀 id 供全局链路使用', () => {
    setCustomRingtones(ROWS)
    expect(getCustomRingtones()).toHaveLength(2)
    expect(getCustomRingtones()[0].cid).toBe('custom:11')
    expect(getCustomRingtones()[0].name).toBe('轻快鸟鸣') // 其余字段原样保留
    setCustomRingtones([])
    expect(getCustomRingtones()).toHaveLength(0) // 空列表直接清空
  })

  it('getRingtone：自定义 id 命中缓存返回行；未命中回退默认系统铃声', () => {
    expect(getRingtone('ding-dong').id).toBe('ding-dong')
    expect(getRingtone('not-exist').id).toBe(DEFAULT_RING) // 非法系统 id 兜底

    setCustomRingtones(ROWS)
    expect(getRingtone('custom:11').name).toBe('轻快鸟鸣')
    expect(getRingtone('custom:99').id).toBe(DEFAULT_RING) // 缓存里没有 → 默认
  })

  it('loadRingtone：无存档回退默认', () => {
    expect(loadRingtone()).toBe(DEFAULT_RING)
  })

  it('loadRingtone：合法系统铃声 id 原样恢复', () => {
    store.set(LS_KEY, 'ding-dong')
    expect(loadRingtone()).toBe('ding-dong')
    store.set(LS_KEY, 'bogus-id')
    expect(loadRingtone()).toBe(DEFAULT_RING) // 非法存档兜底
  })

  it('loadRingtone：自定义铃声存档对照缓存校验', () => {
    store.set(LS_KEY, 'custom:12')
    expect(loadRingtone()).toBe(DEFAULT_RING) // 缓存未加载（开机时序）→ 暂回默认
    setCustomRingtones(ROWS)
    expect(loadRingtone()).toBe('custom:12') // 列表加载后恢复生效
    setCustomRingtones([ROWS[0]])
    expect(loadRingtone()).toBe(DEFAULT_RING) // 铃声被删 → 回退默认
  })

  it('loadRingtone：localStorage 抛异常时安全回退默认', () => {
    vi.stubGlobal('localStorage', {
      getItem: () => { throw new Error('blocked') },
    })
    expect(loadRingtone()).toBe(DEFAULT_RING)
    vi.unstubAllGlobals() // 恢复文件级 stub，避免污染后续用例
  })
})
