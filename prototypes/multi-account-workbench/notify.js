/* ===== notify.js · 新消息提示音（微信策略：合并提示，短窗口只响一次） =====
   微信的做法——提示音不是每条消息都响：
   ① 响铃后有静默合并窗口，窗口内再来的消息只累积角标，不逐条响铃；
   ② 窗口结束时若期间仍有新消息，补响一次（代表这一批）；
   ③ 免打扰会话不响（只红点）；正在查看的会话不响（人已在看）。
   声音用 Web Audio 合成「叮-咚」双音，无外部音频文件，保持离线可开。 */
(() => {
  const MERGE_WINDOW = 5000; // 合并窗口 ms：响铃后 5s 内的新消息合并
  const EDGE_BUFFER = 30;    // 边界提前量 ms：抵消定时器调度抖动，保证窗口到期即补响

  let ctx = null;          // AudioContext（登录点击的手势里解锁）
  let lastPlayed = 0;      // 上次响铃时间戳
  let pendingTimer = null; // 合并窗口结束后的补响定时器

  /* 浏览器自动播放策略：AudioContext 需在用户手势后创建/恢复（登录时调用） */
  function unlock() {
    if (!ctx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (AC) ctx = new AC();
    }
    if (ctx && ctx.state === 'suspended') ctx.resume();
  }

  /* 单音：三角波 + 极快起音 + 指数衰减，短促轻量不吵 */
  function tone(freq, at, dur) {
    const t0 = ctx.currentTime + at;
    const osc = ctx.createOscillator(), gain = ctx.createGain();
    osc.type = 'triangle';
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(0.0001, t0);
    gain.gain.exponentialRampToValueAtTime(0.18, t0 + 0.015);
    gain.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    osc.connect(gain).connect(ctx.destination);
    osc.start(t0); osc.stop(t0 + dur + 0.05);
  }

  function play() {
    if (!ctx || ctx.state !== 'running') return;
    tone(1318.5, 0, 0.16);    // 叮 E6
    tone(987.8, 0.13, 0.22);  // 咚 B5
  }

  /* 响铃并推进合并窗口起点（play 与时间戳原子更新） */
  function ring() {
    play();
    lastPlayed = Date.now();
  }

  /* 合并窗口到期：期间若排过队，补响一次 */
  function flushPending() {
    pendingTimer = null;
    if (Date.now() - lastPlayed >= MERGE_WINDOW - EDGE_BUFFER) ring();
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
    ring();
    return true;
  }

  /* 退出工作台：清掉排队中的补响（避免登录页响铃） */
  function reset() {
    if (pendingTimer) { clearTimeout(pendingTimer); pendingTimer = null; }
  }

  window.Notify = { unlock, incoming, reset };
})();
