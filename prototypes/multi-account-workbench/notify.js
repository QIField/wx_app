/* ===== notify.js · 新消息提示音（微信策略：合并提示，短窗口只响一次） =====
   微信的做法——提示音不是每条消息都响：
   ① 响铃后有静默合并窗口，窗口内再来的消息只累积角标，不逐条响铃；
   ② 窗口结束时若期间仍有新消息，补响一次（代表这一批）；
   ③ 免打扰会话不响（只红点）；正在查看的会话不响（人已在看）。
   声音用 Web Audio 合成「叮-咚」双音，无外部音频文件，保持离线可开。
   健壮性：任意用户点击都尝试解锁 AudioContext（浏览器自动播放策略）；
   响铃遇挂起先 resume 再响；仍被拦截时回调 onBlocked（一次）而非静默失败；
   控制台 Notify.test() 可自检出声链路。 */
(() => {
  const MERGE_WINDOW = 5000; // 合并窗口 ms：响铃后 5s 内的新消息合并
  const EDGE_BUFFER = 30;    // 边界提前量 ms：抵消定时器调度抖动，保证窗口到期即补响

  let ctx = null;              // AudioContext
  let lastPlayed = 0;          // 上次响铃时间戳
  let pendingTimer = null;     // 合并窗口结束后的补响定时器
  let blockedNotified = false; // 被浏览器拦截只提示一次，不刷屏

  /* 创建/恢复 AudioContext：登录点击与任意 pointerdown 都会走到这里 */
  function unlock() {
    if (!ctx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (AC) ctx = new AC();
    }
    if (ctx && ctx.state === 'suspended') ctx.resume();
  }
  document.addEventListener('pointerdown', unlock);

  /* 单音：三角波 + 极快起音 + 指数衰减，短促清晰 */
  function tone(freq, at, dur) {
    const t0 = ctx.currentTime + at;
    const osc = ctx.createOscillator(), gain = ctx.createGain();
    osc.type = 'triangle';
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(0.0001, t0);
    gain.gain.exponentialRampToValueAtTime(0.3, t0 + 0.015);
    gain.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    osc.connect(gain).connect(ctx.destination);
    osc.start(t0); osc.stop(t0 + dur + 0.05);
  }

  function play() {
    tone(1318.5, 0, 0.16);    // 叮 E6
    tone(987.8, 0.13, 0.26);  // 咚 B5
  }

  function ring() {
    play();
    lastPlayed = Date.now();
  }

  /* 响铃（含挂起自愈）：AudioContext 被浏览器挂起时先 resume 再响；
     彻底出不了声走 reportBlocked，不再静默吞掉——无声难排查即源于此 */
  function ringOrReport() {
    if (!ctx) unlock();
    if (ctx && ctx.state === 'suspended') {
      ctx.resume().then(ring).catch(reportBlocked);
      lastPlayed = Date.now();
      return;
    }
    if (!ctx || ctx.state !== 'running') { reportBlocked(); lastPlayed = Date.now(); return; }
    ring();
  }

  function reportBlocked() {
    if (blockedNotified) return;
    blockedNotified = true;
    if (typeof Notify.onBlocked === 'function') Notify.onBlocked();
  }

  /* 合并窗口到期：期间若排过队，补响一次 */
  function flushPending() {
    pendingTimer = null;
    if (Date.now() - lastPlayed >= MERGE_WINDOW - EDGE_BUFFER) ringOrReport();
  }

  /* 来消息时调用（调用方已排除「正在查看的会话」）。免打扰只红点不响 */
  function incoming(conv) {
    if (conv.muted) return false;
    const remaining = MERGE_WINDOW - (Date.now() - lastPlayed);
    if (remaining > 0) {
      /* 合并窗口内：整批只排一次补响，不逐条响 */
      if (!pendingTimer) pendingTimer = setTimeout(flushPending, remaining + EDGE_BUFFER);
      return false;
    }
    ringOrReport();
    return true;
  }

  /* 退出工作台：清掉排队中的补响（避免登录页响铃） */
  function reset() {
    if (pendingTimer) { clearTimeout(pendingTimer); pendingTimer = null; }
  }

  /* 控制台自检：Notify.test() 应立即听到一声「叮-咚」 */
  function test() {
    unlock();
    if (ctx && ctx.state === 'running') { play(); return true; }
    reportBlocked();
    return false;
  }

  window.Notify = { unlock, incoming, reset, test, onBlocked: null };
})();
