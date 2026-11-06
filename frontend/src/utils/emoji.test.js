/** 表情工具层单测：渲染安全（防 XSS）、码映射完整性、编辑器序列化还原。 */
import { describe, it, expect } from 'vitest'
import { WX_FACES, FACE_INDEX, faceUrlOf } from '../data/wxEmojis'
import { escapeHtml, renderEmojiHtml, serializeComposer } from './emoji'

describe('wxEmojis 数据完整性', () => {
  it('113 个表情码且名称唯一', () => {
    expect(WX_FACES.length).toBe(113)
    expect(new Set(WX_FACES).size).toBe(113)
  })
  it('边界序号映射正确（微笑=0，蜡烛=112）', () => {
    expect(FACE_INDEX['微笑']).toBe(0)
    expect(FACE_INDEX['蜡烛']).toBe(112)
    expect(faceUrlOf('微笑')).toContain('/wx-faces/0.png')
    expect(faceUrlOf('蜡烛')).toContain('/wx-faces/112.png')
  })
})

describe('escapeHtml', () => {
  it('转义脚本与引号注入字符', () => {
    expect(escapeHtml('<img src=x onerror=alert(1)>')).not.toContain('<img')
    expect(escapeHtml(`<a href="x">'&`)).toBe('&lt;a href=&quot;x&quot;&gt;&#39;&amp;')
    expect(escapeHtml(null)).toBe('')
  })
})

describe('renderEmojiHtml', () => {
  it('[微笑] 替换为表情图', () => {
    const html = renderEmojiHtml('你好[微笑]')
    expect(html).toContain('<img class="wx-emoji"')
    expect(html).toContain('/wx-faces/0.png')
    expect(html).toContain('alt="[微笑]"')
  })
  it('连续多个表情码各自成图', () => {
    const html = renderEmojiHtml('[微笑][呲牙]')
    expect((html.match(/<img class="wx-emoji"/g) || []).length).toBe(2)
    expect(html).toContain('/wx-faces/13.png') // 呲牙=13
  })
  it('未识别码原样显示（与微信兜底一致）', () => {
    expect(renderEmojiHtml('[裂开]')).toBe('[裂开]')
  })
  it('先转义再替换：恶意内容不产生标签', () => {
    const html = renderEmojiHtml('<script>[微笑]</script>')
    expect(html).not.toContain('<script>')
    expect(html).toContain('&lt;script&gt;')
    expect(html).toContain('<img class="wx-emoji"')
  })
})

/* serializeComposer 用最小 DOM 桩：walk 只访问 nodeType/tagName/dataset/textContent/childNodes */
const text = (s) => ({ nodeType: 3, textContent: s })
const el = (tag, children = [], dataset = {}) => ({ nodeType: 1, tagName: tag, dataset, childNodes: children })
const img = (name) => el('IMG', [], { name })
const br = () => el('BR')

describe('serializeComposer', () => {
  it('表情图还原为 [名称] 码，<br> 还原为换行', () => {
    const node = el('DIV', [text('你好'), img('微笑'), br(), text('好的')])
    expect(serializeComposer(node)).toBe('你好[微笑]\n好的')
  })
  it('末尾残留换行被裁掉（清空输入常见 <br> 残留）', () => {
    const node = el('DIV', [text('hi'), br(), br()])
    expect(serializeComposer(node)).toBe('hi')
  })
  it('未知 img（无 data-name）与嵌套节点安全跳过/递归', () => {
    const node = el('DIV', [text('a'), el('SPAN', [img('呲牙')])])
    expect(serializeComposer(node)).toBe('a[呲牙]')
  })
})
