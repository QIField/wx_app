/** 新消息提示音（微信策略：合并提示，短窗口只响一次）。
 *  ① 响铃后有 5s 合并窗口：窗口内再来消息只累积角标，不逐条响铃；
 *  ② 窗口到期时若期间仍有新消息，补响一次（代表这一批）；
 *  ③ 免打扰 / 正在查看 / 系统灰条不响；跨账号来消息由调用方按需放开。
 *  声音用 Web Audio 合成「叮-咚」双音，零外部资源；
 *  任意 pointerdown 兜底解锁 AudioContext（浏览器自动播放策略）；
 *  响铃遇挂起先 resume 再响，仍被拦截回调 setNotifyBlockedHandler（只一次）。 */

export const MERGE_WINDOW = 5000 // 合并窗口 ms：响铃后 5s 内的新消息合并
export const EDGE_BUFFER = 30 // 边界提前量 ms：抵消定时器调度抖动，保证窗口到期即补响

let ctx = null // AudioContext
let lastPlayed = 0 // 上次响铃时间戳（0 = 未响过，真实时钟下首次必响）
let pendingTimer = null // 合并窗口结束后的补响定时器
let blockedNotified = false // 被拦截只上报一次，不刷屏
let blockedHandler = null

/** 创建/恢复 AudioContext：任意用户点击都会尝试解锁（浏览器自动播放策略）。 */
function unlock() {
  if (!ctx && typeof window !== 'undefined') {
    const AC = window.AudioContext || window.webkitAudioContext
    if (AC) ctx = new AC()
  }
  if (ctx && ctx.state === 'suspended') ctx.resume()
}
if (typeof document !== 'undefined') document.addEventListener('pointerdown', unlock)

/** 单音：三角波 + 极快起音 + 指数衰减，短促清晰。 */
function tone(freq, at, dur) {
  const t0 = ctx.currentTime + at
  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.type = 'triangle'
  osc.frequency.value = freq
  gain.gain.setValueAtTime(0.0001, t0)
  gain.gain.exponentialRampToValueAtTime(0.3, t0 + 0.015)
  gain.gain.exponentialRampToValueAtTime(0.0001, t0 + dur)
  osc.connect(gain).connect(ctx.destination)
  osc.start(t0)
  osc.stop(t0 + dur + 0.05)
}

function play() {
  tone(1318.5, 0, 0.16) // 叮 E6
  tone(987.8, 0.13, 0.26) // 咚 B5
}

function reportBlocked() {
  if (blockedNotified) return
  blockedNotified = true
  if (blockedHandler) blockedHandler()
}

/** 响铃（含挂起自愈）：被挂起先 resume 再响；彻底出不了声上报，不静默吞掉。 */
function ringOrReport() {
  if (!ctx) unlock()
  if (ctx && ctx.state === 'suspended') {
    ctx.resume().then(play).catch(reportBlocked)
  } else if (!ctx || ctx.state !== 'running') {
    reportBlocked()
  } else {
    play()
  }
  lastPlayed = Date.now()
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

/** 控制台自检：window.Notify.test() 应立即听到一声「叮-咚」。 */
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
