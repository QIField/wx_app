import { describe, it, expect } from 'vitest'
import { wordRangeAt, textFromSegments, fragmentOf } from '../../src/utils/textSelection'

/* textSelection.js 纯函数层单测（引擎的 DOM 交互部分依赖浏览器 API，由浏览器端自验） */
describe('wordRangeAt（双击选词的词边界扩展）', () => {
  it('英文/数字/下划线连续段整词选中（件号场景）', () => {
    const text = '编号 WDCDA5HB3DA250327 已发'
    const w = wordRangeAt(text, 5) // 落在件号中间
    expect(w).toEqual({ start: 3, end: 20 }) // 件号 WDCDA5HB3DA250327 共 17 字符，[3,20)
  })

  it('行首 offset=0 选中第一个词', () => {
    const w = wordRangeAt('hello world', 0)
    expect(w).toEqual({ start: 0, end: 5 })
  })

  it('行尾 offset 选中最后一个词', () => {
    const text = 'hello world'
    const w = wordRangeAt(text, text.length - 1)
    expect(w).toEqual({ start: 6, end: 11 })
  })

  it('CJK 连续串按串扩展（双击中文字符选连续汉字）', () => {
    const w = wordRangeAt('请把货发到仓库', 4)
    expect(w).toEqual({ start: 0, end: 7 })
  })

  it('中英混合各自独立扩展，互不跨界', () => {
    const text = 'AB12发货CD'
    expect(wordRangeAt(text, 1)).toEqual({ start: 0, end: 4 })
    expect(wordRangeAt(text, 4)).toEqual({ start: 4, end: 6 })
    expect(wordRangeAt(text, 7)).toEqual({ start: 6, end: 8 })
  })

  it('offset 落在空白/标点返回 null', () => {
    expect(wordRangeAt('a b', 1)).toBeNull()
    expect(wordRangeAt('a，b', 1)).toBeNull()
  })

  it('offset 越界与空文本返回 null', () => {
    expect(wordRangeAt('ab', 5)).toBeNull()
    expect(wordRangeAt('ab', -1)).toBeNull()
    expect(wordRangeAt('', 0)).toBeNull()
    expect(wordRangeAt(null, 0)).toBeNull()
  })
})

describe('textFromSegments（Range 文本提取：表情图 alt 还原码）', () => {
  it('纯文本段直接拼接', () => {
    expect(textFromSegments([{ type: 'text', value: '你好' }, { type: 'text', value: '世界' }])).toBe('你好世界')
  })

  it('emoji 段 value 已含方括号，原样保留（不再包裹）', () => {
    expect(textFromSegments([{ type: 'emoji', value: '[微笑]' }])).toBe('[微笑]')
  })

  it('混合拼接：文本+表情+换行+文本（跨行与表情混排）', () => {
    const segs = [
      { type: 'text', value: '第一行' },
      { type: 'emoji', value: '[呲牙]' },
      { type: 'text', value: '\n第二行' },
    ]
    expect(textFromSegments(segs)).toBe('第一行[呲牙]\n第二行')
  })

  it('空段序列返回空串', () => {
    expect(textFromSegments([])).toBe('')
  })
})

describe('fragmentOf（右键复制归属判断）', () => {
  const state = { msgId: 101, text: '选中片段' }

  it('选中归属右键气泡 → 返回片段', () => {
    expect(fragmentOf(state, 101)).toBe('选中片段')
  })

  it('选中属于其他气泡 → 空串（走全文兜底）', () => {
    expect(fragmentOf(state, 202)).toBe('')
  })

  it('无任何选中 → 空串', () => {
    expect(fragmentOf(null, 101)).toBe('')
  })
})
