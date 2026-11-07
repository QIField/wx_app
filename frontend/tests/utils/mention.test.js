/** @提及纯函数单测：触发检测、命中打分/排序、气泡高亮。
 *
 * 纯 node 环境（不下 DOM）：插入片段/退格删除依赖 Selection，放到组件里联调，
 * 这里只守住"检索与渲染"这类可离线验证的规则。
 */
import { describe, expect, it } from 'vitest'
import {
  extractMentionQuery, matchMembers, memberNameHtml, renderMessageHtml, scoreMember,
} from '../../src/utils/mention'

const SEP = '\u2005' // 微信 @ 的定界符（四分空格），trim 掉对方就收不到提醒

describe('extractMentionQuery 触发检测', () => {
  it('光标前是 @ 或全角 ＠ 时取出检索词（空检索词表示刚输入 @）', () => {
    expect(extractMentionQuery('你好@张')).toBe('张')
    expect(extractMentionQuery('@')).toBe('')
    expect(extractMentionQuery('＠lx')).toBe('lx')
  })

  it('已插入分隔符 / 出现空白 / 不在 @ 上下文时不触发', () => {
    expect(extractMentionQuery(`@张三${SEP}`)).toBeNull()
    expect(extractMentionQuery('a@b c')).toBeNull()
    expect(extractMentionQuery('你好 ')).toBeNull()
    expect(extractMentionQuery('')).toBeNull()
  })
})

describe('scoreMember 命中打分（越小越靠前）', () => {
  const m = { name: '张三', pinyin: 'zhangsan', initials: 'zs' }

  it('昵称前缀 > 全拼前缀 > 首字母前缀', () => {
    expect(scoreMember(m, '张')).toBe(0)
    expect(scoreMember(m, 'zh')).toBe(1)
    expect(scoreMember(m, 'zs')).toBe(2)
  })

  it('包含命中排在前缀之后，不命中返回 -1', () => {
    expect(scoreMember(m, '三')).toBe(3)
    expect(scoreMember(m, 'gsan')).toBe(4)
    expect(scoreMember(m, 'ls')).toBe(-1)
    // 构造数据覆盖"首字母包含"分支：真实拼音里首字母基本都能在全拼中找到，极少走到这里
    expect(scoreMember({ name: '甲', pinyin: 'jia', initials: 'jq' }, 'q')).toBe(5)
  })
})

describe('matchMembers 过滤与排序', () => {
  const members = [
    { name: '张三', pinyin: 'zhangsan', initials: 'zs', alias: 'A1' },
    { name: '李四', pinyin: 'lisi', initials: 'ls', alias: 'B2' },
    { name: '张伟', pinyin: 'zhangwei', initials: 'zw', alias: 'C3' },
  ]

  it('空检索词返回全部成员（刚输入 @ 时的完整名册，按中文拼音字典序）', () => {
    expect(matchMembers(members, '').map((m) => m.name)).toEqual(['李四', '张三', '张伟'])
  })

  it('拼音前缀命中多人时按昵称字典序稳定排列', () => {
    expect(matchMembers(members, 'zh').map((m) => m.name)).toEqual(['张三', '张伟'])
  })

  it('没命中的成员被过滤掉', () => {
    expect(matchMembers(members, 'ls').map((m) => m.name)).toEqual(['李四'])
    expect(matchMembers(members, '不存在')).toEqual([])
  })
})

describe('memberNameHtml 昵称展示', () => {
  it('昵称未解析（name=null）时用「匿名 {alias}」兜底，而不是空白行', () => {
    expect(memberNameHtml({ name: null, alias: 'AB12' }, '')).toBe('匿名 AB12')
  })

  it('命中片段包 mark，且输出已转义', () => {
    expect(memberNameHtml({ name: '张三' }, '三')).toBe('张<mark>三</mark>')
    expect(memberNameHtml({ name: '<b>张三' }, '')).toBe('&lt;b&gt;张三')
  })
})

describe('renderMessageHtml 气泡高亮', () => {
  it('@昵称 + 分隔符高亮为 msg-mention，分隔符本身不显示', () => {
    expect(renderMessageHtml(`@张三${SEP}你好`)).toBe('<span class="msg-mention">@张三</span>你好')
  })

  it('没有分隔符的普通 @（邮箱/文本）不误标', () => {
    expect(renderMessageHtml('a@b.com')).toBe('a@b.com')
  })

  it('先转义再高亮，标签不会被当成 HTML 执行', () => {
    expect(renderMessageHtml(`<img src=x onerror=alert(1)>@张三${SEP}`))
      .toBe('&lt;img src=x onerror=alert(1)&gt;<span class="msg-mention">@张三</span>')
  })
})
