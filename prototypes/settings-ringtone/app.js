/* =========================================================
 * app.js — 视图与交互编排（精简版）
 * 依赖: mock.js 提供的 DB / RINGTONES / DEFAULT_RING，api.js 提供的 api
 * 职责: 图标注入 / Web Audio 试听引擎 / 铃声渲染 / 弹窗与事件
 * ========================================================= */

/* ---------- Lucide 内嵌 SVG 图标（零外链，离线可用） ---------- */
var ICON_PATHS = {
  'settings': '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
  'bell': '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
  'play': '<polygon points="6 3 20 12 6 21 6 3"/>',
  'pause': '<rect x="14" y="4" width="4" height="16" rx="1"/><rect x="6" y="4" width="4" height="16" rx="1"/>',
  'check': '<path d="M20 6 9 17l-5-5"/>',
  'x': '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
  'rotate-ccw': '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>'
};

function svgIcon(name, size) {
  size = size || 16;
  return '<svg width="' + size + '" height="' + size + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' + (ICON_PATHS[name] || '') + '</svg>';
}

function $(sel) { return document.querySelector(sel); }
function $$(sel) { return Array.prototype.slice.call(document.querySelectorAll(sel)); }

/* ---------- Web Audio 试听引擎 ----------
 * 本地合成经典铃声，无需任何音频文件；同时只允许播放一个，
 * 再次点击或切换铃声时立即停掉当前所有振荡器。
 * 注意：AudioContext 必须在用户手势中创建/恢复（浏览器自动播放策略）。 */
var Engine = {
  ctx: null,
  nodes: [],
  playingId: null,
  timer: null,

  ensure: function () {
    if (!this.ctx) {
      var AC = window.AudioContext || window.webkitAudioContext;
      this.ctx = new AC();
    }
    if (this.ctx.state === 'suspended') this.ctx.resume();
    return this.ctx;
  },

  // 停止当前试听：清定时器 + 立即停掉全部振荡器
  stop: function () {
    if (this.timer) { clearTimeout(this.timer); this.timer = null; }
    this.nodes.forEach(function (o) { try { o.stop(); } catch (e) { /* 已结束的节点忽略 */ } });
    this.nodes = [];
    var ended = this.playingId;
    this.playingId = null;
    if (ended) setRowPlaying(ended, false);
  },

  play: function (id) {
    var rt = null;
    for (var i = 0; i < RINGTONES.length; i++) if (RINGTONES[i].id === id) rt = RINGTONES[i];
    if (!rt) return;

    var ctx = this.ensure();
    this.stop();

    var self = this;
    var t0 = ctx.currentTime + 0.02;
    // 主增益节点统一控音量，避免多音叠爆
    var master = ctx.createGain();
    master.gain.value = 0.9;
    master.connect(ctx.destination);

    rt.notes.forEach(function (n) {
      self.nodes.push(self.note(ctx, t0 + n.t, n, master));
      // h 标记：叠一个八度泛音，模拟八音盒/风铃的金属质感
      if (rt.h) self.nodes.push(self.note(ctx, t0 + n.t, { f: n.f * 2, dur: n.dur, g: (n.g || 0.18) * 0.25, type: n.type }, master));
    });

    this.playingId = id;
    setRowPlaying(id, true);

    // 全部音符结束后自动复位按钮
    var total = 0;
    rt.notes.forEach(function (n) { total = Math.max(total, n.t + (n.dur || 0.3)); });
    this.timer = setTimeout(function () { self.stop(); }, (total + 0.15) * 1000);
  },

  // 单个音符：振荡器 + 音量包络（快起缓落，模拟打击/铃声衰减）
  note: function (ctx, at, n, sink) {
    var dur = n.dur || 0.3, g = n.g || 0.18, type = n.type || 'sine';
    var o = ctx.createOscillator();
    var gn = ctx.createGain();
    o.type = type;
    o.frequency.setValueAtTime(n.f, at);
    if (n.to) o.frequency.exponentialRampToValueAtTime(n.to, at + dur);
    gn.gain.setValueAtTime(0.0001, at);
    gn.gain.exponentialRampToValueAtTime(g, at + 0.015);
    gn.gain.exponentialRampToValueAtTime(0.0001, at + dur);
    o.connect(gn); gn.connect(sink);
    o.start(at); o.stop(at + dur + 0.05);
    return o;
  }
};

/* ---------- 状态 ---------- */
var state = { ringtoneId: null, savingRing: false };
var LS_KEY = 'proto-settings-ringtone-v2';

function saveLocal() {
  try { localStorage.setItem(LS_KEY, JSON.stringify({ ringtoneId: state.ringtoneId })); }
  catch (e) { /* 无痕模式等场景忽略 */ }
}

function loadLocal() {
  try {
    var raw = localStorage.getItem(LS_KEY);
    if (raw) { var s = JSON.parse(raw); if (s && s.ringtoneId) state.ringtoneId = s.ringtoneId; }
  } catch (e) { /* 数据损坏时直接用服务端数据 */ }
}

/* ---------- 渲染 ---------- */

function initIcons() {
  $('#openSettingsBtn').innerHTML = svgIcon('settings');
  $('#openSettingsBtn2').innerHTML = svgIcon('settings', 14);
  $('#demoIc').innerHTML = svgIcon('bell', 20);
  $('#modalTitleIc').innerHTML = svgIcon('bell', 15);
  $('#closeModalBtn').innerHTML = svgIcon('x', 14);
  $('#resetRingBtn .mini-btn-ic').innerHTML = svgIcon('rotate-ccw', 11);
}

function currentRingName() {
  for (var i = 0; i < RINGTONES.length; i++) if (RINGTONES[i].id === state.ringtoneId) return RINGTONES[i].name;
  return '';
}

// 铃声列表：radio 单选 + 试听按钮 + 默认/当前标签
function renderRingList() {
  var html = RINGTONES.map(function (r) {
    var isCur = r.id === state.ringtoneId;
    var tags = '';
    if (r.isDefault) tags += '<span class="tag tag-default">默认</span>';
    if (isCur) tags += '<span class="tag tag-current">当前</span>';
    return '<li class="ring-row" data-id="' + r.id + '">' +
      '<label class="ring-pick" title="设为消息提示音">' +
        '<input type="radio" name="ringtone" value="' + r.id + '"' + (isCur ? ' checked' : '') + '>' +
        '<span class="radio-ui"></span>' +
      '</label>' +
      '<div class="ring-meta">' +
        '<div class="ring-name">' + r.name + tags + '</div>' +
        '<div class="ring-desc">' + r.desc + '</div>' +
      '</div>' +
      '<button class="ring-play" data-id="' + r.id + '">' +
        '<span class="wave"><i></i><i></i><i></i><i></i></span>' +
        '<span class="play-ic">' + svgIcon('play', 12) + '</span>' +
        '<span class="play-text">试听</span>' +
      '</button>' +
    '</li>';
  }).join('');
  $('#ringList').innerHTML = html;
}

// 播放中行：波形动画 + 图标切换 play/pause
function setRowPlaying(id, on) {
  var row = document.querySelector('.ring-row[data-id="' + id + '"]');
  if (!row) return;
  row.classList.toggle('playing', on);
  var ic = row.querySelector('.play-ic');
  if (ic) ic.innerHTML = svgIcon(on ? 'pause' : 'play', 12);
  var text = row.querySelector('.play-text');
  if (text) text.textContent = on ? '停止' : '试听';
}

/* ---------- Toast ---------- */
var toastTimer = null;
function showToast(msg, type) {
  var t = $('#toast');
  t.className = 'toast ' + (type || 'ok');
  t.innerHTML = svgIcon(type === 'err' ? 'x' : 'check', 14) + '<span>' + msg + '</span>';
  clearTimeout(toastTimer);
  toastTimer = setTimeout(function () { t.classList.add('hidden'); }, 2600);
}

/* ---------- 事件绑定 ---------- */

function openModal() {
  $('#settingsModal').classList.remove('hidden');
  renderRingList(); // 每次打开都按最新状态渲染
}

function closeModal() {
  Engine.stop(); // 关弹窗时停止试听
  $('#settingsModal').classList.add('hidden');
}

function bindEvents() {
  // 两个设置入口：顶栏齿轮 + 演示按钮
  $('#openSettingsBtn').addEventListener('click', openModal);
  $('#openSettingsBtn2').addEventListener('click', openModal);
  $('#closeModalBtn').addEventListener('click', closeModal);
  $('#settingsModal').addEventListener('click', function (e) { if (e.target === this) closeModal(); });

  // ESC 关闭
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && !$('#settingsModal').classList.contains('hidden')) closeModal();
  });

  // 试听按钮（事件委托，列表是动态渲染的）
  $('#ringList').addEventListener('click', function (e) {
    var btn = e.target.closest('.ring-play');
    if (!btn) return;
    var id = btn.getAttribute('data-id');
    if (Engine.playingId === id) { Engine.stop(); return; }
    Engine.play(id);
  });

  // 选择提示音：选中即保存（loading 态 + toast 反馈）
  $('#ringList').addEventListener('change', async function (e) {
    if (e.target.name !== 'ringtone') return;
    var id = e.target.value;
    // 保存进行中时，把视觉选中态回滚到真实值，避免 UI 与状态不一致
    if (state.savingRing) {
      e.target.checked = false;
      var real = document.querySelector('.ring-row[data-id="' + state.ringtoneId + '"] input');
      if (real) real.checked = true;
      return;
    }
    if (id === state.ringtoneId) return;
    state.savingRing = true;
    Engine.stop();
    e.target.closest('.ring-row').classList.add('saving');
    try {
      var res = await api.updateRingtone(id);
      state.ringtoneId = res.ringtoneId;
      saveLocal();
      renderRingList(); // 重渲染刷新「当前」标签
      showToast('已将「' + currentRingName() + '」设为消息提示音');
    } catch (err) {
      showToast('保存失败，请重试', 'err');
      renderRingList(); // 回滚选中态
    } finally {
      state.savingRing = false;
    }
  });

  // 恢复默认提示音
  $('#resetRingBtn').addEventListener('click', async function () {
    if (state.savingRing) return;
    if (state.ringtoneId === DEFAULT_RING) { showToast('当前已是默认提示音「' + currentRingName() + '」'); return; }
    state.savingRing = true;
    try {
      var res = await api.updateRingtone(DEFAULT_RING);
      state.ringtoneId = res.ringtoneId;
      saveLocal();
      renderRingList();
      showToast('已恢复默认提示音「' + currentRingName() + '」');
    } finally {
      state.savingRing = false;
    }
  });
}

/* ---------- 启动 ---------- */
(async function boot() {
  initIcons();
  bindEvents();

  // 先拉取 mock 数据（期间展示骨架屏），再叠加本地持久化的演示数据
  var data = await api.fetchRingtone();
  state.ringtoneId = data.ringtoneId;
  loadLocal();
  renderRingList();
})();
