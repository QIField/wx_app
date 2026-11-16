/** 消息提示音铃声库（数据单一来源）。
 *  系统铃声全部用 Web Audio 序列合成，零音频文件、离线可用；
 *  序列字段：t 起始秒 | f 起始频率Hz | to 滑向频率 | dur 时长秒
 *            type 波形(sine/triangle/square) | g 音量 | h 叠八度泛音
 *  自定义铃声由后端 /api/ringtones 上传持久化，内存缓存后并入同一套选择/播放链路。
 *  当前选择持久化到 localStorage（本地偏好，不进后端）：
 *  系统铃声存 id，自定义铃声存 `custom:<行id>` 前缀 id。 */

const LS_KEY = 'notify.ringtone.v1'

export const DEFAULT_RING = 'ding-dong' // 恢复默认的目标

/** 自定义铃声 id 前缀：localStorage 里区分系统/自定义铃声。 */
export const CUSTOM_PREFIX = 'custom:'

/** 判断是否自定义铃声 id。 */
export function isCustomId(id) {
  return typeof id === 'string' && id.startsWith(CUSTOM_PREFIX)
}

/** 自定义铃声内存缓存（行结构 + cid 前缀 id）；列表来自 /api/ringtones。 */
let customList = []

/** 写入自定义铃声缓存：rows 为后端返回行数组（原样行 id）。 */
export function setCustomRingtones(rows) {
  customList = (rows || []).map((r) => ({ ...r, cid: CUSTOM_PREFIX + r.id }))
}

/** 读当前自定义铃声缓存（设置弹窗渲染用）。 */
export function getCustomRingtones() {
  return customList
}

/** 经典铃声库（与 prototypes/settings-ringtone 原型同源）。
 *  isDefault 仅作 UI 展示标签。 */
export const RINGTONES = [
  {
    id: 'ding-dong', name: '轻快叮咚', desc: '温和清脆，久听不腻', isDefault: true,
    notes: [
      { t: 0, f: 880, dur: 0.16, g: 0.2 },
      { t: 0.18, f: 659.25, dur: 0.42, g: 0.18 },
    ],
  },
  {
    id: 'tri-tone', name: '经典三全音', desc: '熟悉的下降三连音',
    notes: [
      { t: 0, f: 1046.5, dur: 0.11, type: 'triangle', g: 0.18 },
      { t: 0.115, f: 830.61, dur: 0.11, type: 'triangle', g: 0.18 },
      { t: 0.23, f: 698.46, dur: 0.11, type: 'triangle', g: 0.18 },
      { t: 0.345, f: 466.16, dur: 0.38, type: 'triangle', g: 0.18 },
    ],
  },
  {
    id: 'marimba', name: '马林巴晨曲', desc: '木琴琶音，明快不刺耳',
    notes: [
      { t: 0, f: 261.63, dur: 0.4, type: 'triangle', g: 0.1 },
      { t: 0, f: 523.25, dur: 0.2, type: 'triangle', g: 0.16 },
      { t: 0.09, f: 659.25, dur: 0.2, type: 'triangle', g: 0.16 },
      { t: 0.18, f: 783.99, dur: 0.2, type: 'triangle', g: 0.16 },
      { t: 0.27, f: 1046.5, dur: 0.2, type: 'triangle', g: 0.16 },
      { t: 0.42, f: 783.99, dur: 0.2, type: 'triangle', g: 0.14 },
      { t: 0.51, f: 659.25, dur: 0.26, type: 'triangle', g: 0.14 },
    ],
  },
  {
    id: 'drop', name: '水滴落盘', desc: '一滴水声，轻巧低调',
    notes: [
      { t: 0, f: 1250, to: 520, dur: 0.24, g: 0.24 },
      { t: 0.26, f: 1000, to: 420, dur: 0.3, g: 0.18 },
    ],
  },
  {
    id: 'music-box', name: '八音盒', desc: '细碎铃音，安静氛围', h: true,
    notes: [
      { t: 0, f: 1318.5, dur: 0.3, g: 0.13 },
      { t: 0.15, f: 1046.5, dur: 0.3, g: 0.13 },
      { t: 0.3, f: 880, dur: 0.3, g: 0.13 },
      { t: 0.5, f: 1318.5, dur: 0.3, g: 0.12 },
      { t: 0.65, f: 1568, dur: 0.55, g: 0.11 },
    ],
  },
  {
    id: 'beep', name: '电子嘀嘀', desc: '复古双音，业务感强',
    notes: [
      { t: 0, f: 1318.5, dur: 0.09, type: 'square', g: 0.09 },
      { t: 0.18, f: 1318.5, dur: 0.09, type: 'square', g: 0.09 },
    ],
  },
  {
    id: 'bird', name: '鸟鸣晨曦', desc: '两声短促鸟叫，自然轻快',
    notes: [
      { t: 0, f: 2100, to: 2900, dur: 0.12, g: 0.16 },
      { t: 0.15, f: 2400, to: 1650, dur: 0.16, g: 0.14 },
    ],
  },
  {
    id: 'chime', name: '空灵风铃', desc: '一串渐弱高音，余韵绵长',
    notes: [
      { t: 0, f: 2093, dur: 0.5, g: 0.1 },
      { t: 0.12, f: 1760, dur: 0.5, g: 0.09 },
      { t: 0.24, f: 1568, dur: 0.55, g: 0.09 },
      { t: 0.36, f: 1318.5, dur: 0.6, g: 0.08 },
      { t: 0.5, f: 1046.5, dur: 0.7, g: 0.07 },
    ],
  },
]

/** 按铃声 id 找定义；自定义铃声查内存缓存（url 字段为音频文件地址）；
 *  找不到回退默认（localStorage 被手改/铃声被删/版本演进时兜底）。 */
export function getRingtone(id) {
  if (isCustomId(id)) {
    return customList.find((r) => r.cid === id)
      || RINGTONES.find((r) => r.id === DEFAULT_RING)
  }
  return RINGTONES.find((r) => r.id === id) || RINGTONES.find((r) => r.id === DEFAULT_RING)
}

/** 读当前铃声：无存档/存档非法（含自定义铃声已被删除）时回退默认。 */
export function loadRingtone() {
  try {
    const id = localStorage.getItem(LS_KEY)
    if (!id) return DEFAULT_RING
    if (isCustomId(id)) {
      return customList.some((r) => r.cid === id) ? id : DEFAULT_RING
    }
    if (RINGTONES.some((r) => r.id === id)) return id
  } catch (e) { /* 无痕模式等存取失败场景忽略 */ }
  return DEFAULT_RING
}

/** 写当前铃声。 */
export function saveRingtone(id) {
  try { localStorage.setItem(LS_KEY, id) } catch (e) { /* 忽略 */ }
}
