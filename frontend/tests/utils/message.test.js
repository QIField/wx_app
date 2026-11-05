/** msgTextOf 取值规则单测：右键复制的核心取值口，重构的行为基线。
 *
 * 纯 node 环境（无 DOMParser），所有用例走 payload 结构化数据，
 * 避免 message.js 兜底解析 XML 的路径（DOMParser 依赖浏览器）。
 */
import { describe, it, expect } from 'vitest'
import { msgTextOf } from '../../src/utils/message'

describe('msgTextOf 整条消息全文提取', () => {
  it('空入参返回空串', () => {
    expect(msgTextOf(null)).toBe('')
    expect(msgTextOf(undefined)).toBe('')
  })

  it('纯文本消息返回原文', () => {
    expect(msgTextOf({ msg_type: 1, content: '你好，在吗' })).toBe('你好，在吗')
  })

  it('引用消息 = 回复 + 引用行', () => {
    const m = {
      msg_type: 5,
      payload: { quote: { reply: '好的收到', name: '张三', text: '明天上午开会' } },
    }
    expect(msgTextOf(m)).toBe('好的收到\n引用 张三：明天上午开会')
  })

  it('引用消息缺名字时只带原文', () => {
    const m = {
      msg_type: 5,
      payload: { quote: { reply: 'ok', name: '', text: '原始内容' } },
    }
    expect(msgTextOf(m)).toBe('ok\n引用 原始内容')
  })

  it('引用消息回复为空时不产生空行', () => {
    const m = {
      msg_type: 5,
      payload: { quote: { reply: '', name: '张三', text: '原文' } },
    }
    expect(msgTextOf(m)).toBe('引用 张三：原文')
  })

  it('链接卡片取标题/摘要/链接三行', () => {
    const m = {
      msg_type: 5,
      payload: { app: { title: '需求文档', desc: 'V2 版评审稿', url: 'https://example.com/doc' } },
    }
    expect(msgTextOf(m)).toBe('需求文档\nV2 版评审稿\nhttps://example.com/doc')
  })

  it('链接卡片缺摘要时跳过空段', () => {
    const m = {
      msg_type: 5,
      payload: { app: { title: '需求文档', desc: '', url: 'https://example.com/doc' } },
    }
    expect(msgTextOf(m)).toBe('需求文档\nhttps://example.com/doc')
  })

  it('文件消息取文件名', () => {
    expect(msgTextOf({ msg_type: 3, content: '季度报表.xlsx' })).toBe('季度报表.xlsx')
  })

  it('appmsg 文件取卡片标题', () => {
    const m = { msg_type: 3, content: '<xml/>', payload: { app: { title: '设计稿.pdf' } } }
    expect(msgTextOf(m)).toBe('设计稿.pdf')
  })

  it('纯媒体消息无文本可取返回空串', () => {
    expect(msgTextOf({ msg_type: 2 })).toBe('') // 图片
    expect(msgTextOf({ msg_type: 4 })).toBe('') // 视频
    expect(msgTextOf({ msg_type: 6 })).toBe('') // 语音
    expect(msgTextOf({ msg_type: 7 })).toBe('') // 表情
  })
})
