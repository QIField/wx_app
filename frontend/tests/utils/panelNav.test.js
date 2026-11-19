import { describe, expect, it } from 'vitest'
import { moveMenuFocus } from '../../src/components/right/panelNav'

const none = () => false

describe('moveMenuFocus 头部导航键盘焦点算法', () => {
  it('方向键环绕移动', () => {
    expect(moveMenuFocus('ArrowRight', 0, 4, none)).toBe(1)
    expect(moveMenuFocus('ArrowRight', 3, 4, none)).toBe(0)
    expect(moveMenuFocus('ArrowLeft', 0, 4, none)).toBe(3)
    expect(moveMenuFocus('ArrowLeft', 1, 4, none)).toBe(0)
  })

  it('方向键跳过禁用项（含跨环绕边界）', () => {
    const dis = (i) => i === 1
    expect(moveMenuFocus('ArrowRight', 0, 4, dis)).toBe(2)
    expect(moveMenuFocus('ArrowRight', 2, 4, dis)).toBe(3)
    expect(moveMenuFocus('ArrowLeft', 2, 4, dis)).toBe(0)
    expect(moveMenuFocus('ArrowLeft', 0, 4, dis)).toBe(3)
    const disTail = (i) => i === 3
    expect(moveMenuFocus('ArrowLeft', 0, 4, disTail)).toBe(2)
    expect(moveMenuFocus('ArrowRight', 2, 4, disTail)).toBe(0)
  })

  it('Home/End 落在首个/末个可用项', () => {
    expect(moveMenuFocus('Home', 2, 4, none)).toBe(0)
    expect(moveMenuFocus('End', 0, 4, none)).toBe(3)
    const dis = (i) => i === 0 || i === 3
    expect(moveMenuFocus('Home', 2, 4, dis)).toBe(1)
    expect(moveMenuFocus('End', 1, 4, dis)).toBe(2)
  })

  it('全部禁用原地不动', () => {
    const all = () => true
    expect(moveMenuFocus('ArrowRight', 2, 4, all)).toBe(2)
    expect(moveMenuFocus('Home', 2, 4, all)).toBe(2)
    expect(moveMenuFocus('End', 2, 4, all)).toBe(2)
  })

  it('无关按键原地不动，空列表返回 -1', () => {
    expect(moveMenuFocus('Enter', 1, 4, none)).toBe(1)
    expect(moveMenuFocus('Tab', 1, 4, none)).toBe(1)
    expect(moveMenuFocus('ArrowRight', 0, 0, none)).toBe(-1)
    expect(moveMenuFocus('Home', 0, 0, none)).toBe(-1)
  })
})
