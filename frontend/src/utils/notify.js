/** 新消息提示音（微信策略：合并提示，短窗口只响一次）。
 *  ① 响铃后有 5s 合并窗口：窗口内再来消息只累积角标，不逐条响铃；
 *  ② 窗口到期时若期间仍有新消息，补响一次（代表这一批）；
 *  ③ 免打扰 / 正在查看 / 系统灰条不响；跨账号来消息由调用方按需放开；
 *  ④ 铃声可在设置里选择（utils/ringtones 铃声库 + localStorage 持久化），
 *     旧版固定「叮-咚」已由可选铃声替代。
 *  声音用 Web Audio 按铃声序列合成，零外部资源；
 *  任意 pointerdown 兜底解锁 AudioContext（浏览器自动播放策略）；
 *  响铃遇挂起先 resume 再响，仍被拦截回调 setNotifyBlockedHandler（只一次）。 */

import { getRingtone, isCustomId, loadRingtone, saveRingtone } from './ringtones'

export const MERGE_WINDOW = 5000 // 合并窗口 ms：响铃后 5s 内的新消息合并
export const EDGE_BUFFER = 30 // 边界提前量 ms：抵消定时器调度抖动，保证窗口到期即补响

let ctx = null // AudioContext
let lastPlayed = 0 // 上次响铃时间戳（0 = 未响过，真实时钟下首次必响）
let pendingTimer = null // 合并窗口结束后的补响定时器
let blockedNotified = false // 被拦截只上报一次，不刷屏
let blockedHandler = null
let ringtoneId = loadRingtone() // 当前铃声 id（模块加载即读本地偏好）

/** 创建/恢复 AudioContext：任意用户点击都会尝试解锁（浏览器自动播放策略）。 */
function unlock() {
  if (!ctx && typeof window !== 'undefined') {
    const AC = window.AudioContext || window.webkitAudioContext
    if (AC) ctx = new AC()
  }
  if (ctx && ctx.state === 'suspended') ctx.resume()
}
if (typeof document !== 'undefined') document.addEventListener('pointerdown', unlock)

/** 单音（通用）：type 波形 / to 滑音 / gain 音量可配；sink 缺省直连输出。
 *  三角波 + 极快起音 + 指数衰减，短促清晰；滑音用于水滴/鸟鸣类音色。 */
function tone(freq, at, dur, { to, type = 'sine', gain = 0.18 } = {}, sink) {
  const t0 = ctx.currentTime + at
  const osc = ctx.createOscillator()
  const gn = ctx.createGain()
  osc.type = type
  osc.frequency.setValueAtTime(freq, t0)
  if (to) osc.frequency.exponentialRampToValueAtTime(to, t0 + dur)
  gn.gain.setValueAtTime(0.0001, t0)
  gn.gain.exponentialRampToValueAtTime(gain, t0 + 0.015)
  gn.gain.exponentialRampToValueAtTime(0.0001, t0 + dur)
  osc.connect(gn).connect(sink || ctx.destination)
  osc.start(t0)
  osc.stop(t0 + dur + 0.05)
  return osc
}

/** 按铃声定义合成一整段：h 标记叠八度泛音（八音盒/风铃金属质感），
 *  master 统一控音量，防止多音叠加爆音。返回全部节点（试听时可中途停止）。 */
function playSequence(rt) {
  const master = ctx.createGain()
  master.gain.value = 0.9
  master.connect(ctx.destination)
  const nodes = []
  rt.notes.forEach((n) => {
    const dur = n.dur ?? 0.3
    nodes.push(tone(n.f, n.t, dur, { to: n.to, type: n.type, gain: n.g ?? 0.18 }, master))
    if (rt.h) nodes.push(tone(n.f * 2, n.t, dur, { type: n.type, gain: (n.g ?? 0.18) * 0.25 }, master))
  })
  return nodes
}

function play() {
  const rt = getRingtone(ringtoneId)
  if (rt.url) playCustomAudio(rt)
  else playSequence(rt)
}

/* ---------- 自定义铃声：HTML Audio 播音频文件（与合成路径互斥） ---------- */

let customAudio = null // 正在播放的自定义铃声 Audio 元素

/** 播放自定义铃声文件；换播前先停旧的，播放被拦截走统一上报。 */
function playCustomAudio(rt) {
  stopCustomAudio()
  customAudio = new Audio(rt.url)
  customAudio.play().catch(reportBlocked)
}

function stopCustomAudio() {
  if (!customAudio) return
  try {
    customAudio.pause()
    customAudio.currentTime = 0
  } catch (e) { /* 已释放的元素忽略 */ }
  customAudio = null
}

function reportBlocked() {
  if (blockedNotified) return
  blockedNotified = true
  if (blockedHandler) blockedHandler()
}

/** 响铃（含挂起自愈）：被挂起先 resume 再响；彻底出不了声上报，不静默吞掉。 */
function ringOrReport() {
  lastPlayed = Date.now()
  if (!ctx) unlock()
  if (ctx && ctx.state === 'suspended') {
    ctx.resume().then(play).catch(reportBlocked)
  } else if (!ctx || ctx.state !== 'running') {
    reportBlocked()
  } else {
    play()
  }
}

/** 合并窗口到期：期间若排过队，补响一次。 */
function flushPending() {
  pendingTimer = null
  if (Date.now() - lastPlayed >= MERGE_WINDOW - EDGE_BUFFER) ringOrReport()
}

/** 合并窗口决策（纯函数，单测锚点）：距上次响铃满窗口 → 立即响，否则排队补响。 */
export function ringDecision(lastPlayedTs, nowTs, windowMs = MERGE_WINDOW) {
  return nowTs - lastPlayedTs >= windowMs ? 'ring' : 'queue'
}

/** 来消息时调用（store 已备好事实字段）。返回是否尝试响铃。 */
export function notifyIncoming({ muted = false, viewing = false, system = false } = {}) {
  if (muted || viewing || system) return false
  if (ringDecision(lastPlayed, Date.now()) === 'queue') {
    // 合并窗口内：整批只排一次补响，不逐条响
    if (!pendingTimer) {
      const remaining = MERGE_WINDOW - (Date.now() - lastPlayed)
      pendingTimer = setTimeout(flushPending, remaining + EDGE_BUFFER)
    }
    return false
  }
  ringOrReport()
  return true
}

/** 浏览器音频策略拦截提示的接管点（store 里接 ElMessage）。 */
export function setNotifyBlockedHandler(fn) {
  blockedHandler = typeof fn === 'function' ? fn : null
}

/** 清空合并状态（测试钩子；退出工作台如需静音也可调用）。 */
export function resetNotify() {
  if (pendingTimer) {
    clearTimeout(pendingTimer)
    pendingTimer = null
  }
  lastPlayed = 0
  blockedNotified = false
}

/* ---------- 铃声选择与试听（设置弹窗用） ---------- */

/** 读当前铃声 id。 */
export function currentRingtone() {
  return ringtoneId
}

/** 换铃声：更新内存并持久化到 localStorage。
 *  系统铃声经 getRingtone 校验兜底；自定义铃声原样存 custom:<id> 前缀 id
 *  （合法性由 loadRingtone 对照内存缓存校验，铃声被删时自动回退默认）。 */
export function setRingtone(id) {
  ringtoneId = isCustomId(id) ? id : getRingtone(id).id
  saveRingtone(ringtoneId)
}

/** 重新按最新持久化偏好校正当前铃声（自定义铃声列表拉取后调用）：
 *  存的自定义铃声被删 → 回退默认；存的 custom:<id> 现在合法 → 恢复生效。 */
export function refreshRingtone() {
  const id = loadRingtone()
  if (id !== ringtoneId) ringtoneId = id
}

let previewNodes = [] // 试听中的振荡器（可中途停止）
let previewTimer = null // 试听自动复位定时器

/** 停止试听：清定时器 + 停掉全部振荡器 + 停自定义铃声 Audio。 */
export function stopPreview() {
  if (previewTimer) {
    clearTimeout(previewTimer)
    previewTimer = null
  }
  stopCustomAudio()
  previewNodes.forEach((o) => { try { o.stop() } catch (e) { /* 已结束的节点忽略 */ } })
  previewNodes = []
}

/** 试听指定铃声（设置弹窗）：
 *  - 系统铃声：Web Audio 合成，返回时长秒供 UI 定时复位动画；
 *  - 自定义铃声：HTML Audio 播文件，播完/出错回调 onEnd 复位，返回 -1（时长未知）；
 *  - 返回 0 表示无法播放（静音环境无 AudioContext）。
 * @param onEnd 自定义铃声播完回调（合成铃声走定时复位，不需要） */
export function previewRingtone(id, onEnd) {
  const rt = getRingtone(id)
  stopPreview()
  if (isCustomId(id)) {
    if (!rt.url) return 0
    // 播完/出错/被拦截都走同一个收尾：停试听 + 通知 UI 复位
    const finish = () => {
      stopPreview()
      if (typeof onEnd === 'function') onEnd()
    }
    customAudio = new Audio(rt.url)
    customAudio.addEventListener('ended', finish)
    customAudio.addEventListener('error', finish)
    customAudio.play().catch(finish)
    return -1
  }
  if (!ctx) unlock()
  if (!ctx) return 0
  const dur = Math.max(...rt.notes.map((n) => n.t + (n.dur ?? 0.3)))
  const start = () => {
    previewNodes = playSequence(rt)
    previewTimer = setTimeout(stopPreview, (dur + 0.15) * 1000)
  }
  if (ctx.state === 'suspended') ctx.resume().then(start).catch(() => {})
  else start()
  return dur
}

/** 控制台自检：window.Notify.test() 应立即听到一声当前铃声。 */
export function notifyTest() {
  unlock()
  if (ctx && ctx.state === 'running') {
    play()
    return true
  }
  reportBlocked()
  return false
}
if (typeof window !== 'undefined') window.Notify = { test: notifyTest }
