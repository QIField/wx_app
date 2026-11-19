/** 头部导航键盘焦点算法（纯函数，供 PanelHead 调用、可单测）。
 *
 * 方向键在按钮间环绕移动并跳过禁用项；Home/End 跳到首/尾可用项；
 * 无可用项或无关按键时原地不动。
 *
 * @param {string} key KeyboardEvent.key
 * @param {number} index 当前焦点下标
 * @param {number} count 按钮总数
 * @param {(i: number) => boolean} isDisabled 下标 i 是否禁用
 * @returns {number} 目标下标；空列表返回 -1
 */
const KEY_STEP = { ArrowRight: 1, ArrowLeft: -1 }

export function moveMenuFocus(key, index, count, isDisabled = () => false) {
  if (count <= 0) return -1

  if (key === 'Home' || key === 'End') {
    const step = key === 'Home' ? 1 : -1
    for (let i = key === 'Home' ? 0 : count - 1; i >= 0 && i < count; i += step) {
      if (!isDisabled(i)) return i
    }
    return index
  }

  const step = KEY_STEP[key]
  if (!step) return index

  for (let n = 1; n <= count; n++) {
    const i = (((index + step * n) % count) + count) % count
    if (!isDisabled(i)) return i
  }
  return index
}
