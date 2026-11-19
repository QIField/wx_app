/* ===== 快捷报价面板 · 视图：自动报价（新消息触发流 + 流水线） ===== */
'use strict';

/* ---------- 视图：自动报价 ---------- */
function renderAutoView() {
  const a = S.auto;
  const modeCls = !a.aiOn ? 'off' : (a.mode === 'auto' ? 'auto' : 'preview');
  const modeTxt = !a.aiOn ? '未开启' : (a.mode === 'auto' ? '识别成功自动发送' : '仅侧边预览');
  $('#qqBody').innerHTML = `
    <div class="view">
      <div class="auto-strip">
        <div class="strip-row">
          <span class="lbl">AI智能识别</span>
          <label class="switch"><input type="checkbox" id="aiSwitch" ${a.aiOn ? 'checked' : ''}><span class="track"></span></label>
          <span class="mode-chip ${modeCls}" style="margin-left:auto">${modeTxt}</span>
        </div>
        <div class="strip-row">
          <span class="sw-label">自动报价模式</span>
          <select class="select mode-sel" id="modeSel">
            <option value="preview" ${a.mode === 'preview' ? 'selected' : ''}>仅侧边预览</option>
            <option value="auto" ${a.mode === 'auto' ? 'selected' : ''}>识别成功自动发送</option>
          </select>
        </div>
      </div>
      <div class="feed-head">
        <span class="t">新消息触发流</span>
        <span class="live"><i></i>LIVE</span>
        <button class="btn sm pause" id="feedPause">${a.paused ? '▶ 继续' : '⏸ 暂停'}</button>
      </div>
      <div class="feed" id="autoFeed">
        ${a.cards.length ? '' : '<div class="empty">监听已开启的好友/群新消息，识别需求后在此输出报价…</div>'}
      </div>
    </div>`;

  const feed = $('#autoFeed');
  a.cards.forEach(c => feed.appendChild(c.el));
  $('#aiSwitch').addEventListener('change', e => {
    S.auto.aiOn = S.settings.aiOn = e.target.checked;
    syncModeChip();
    toast(e.target.checked ? 'AI 智能识别已开启' : 'AI 智能识别已关闭（仅规则识别）');
  });
  $('#modeSel').addEventListener('change', e => {
    S.auto.mode = S.settings.autoMode = e.target.value;
    syncModeChip();
    toast(e.target.value === 'auto' ? '已切换：识别成功自动发送' : '已切换：仅侧边预览');
  });
  $('#feedPause').addEventListener('click', () => {
    a.paused = !a.paused;
    $('#feedPause').textContent = a.paused ? '▶ 继续' : '⏸ 暂停';
  });
  syncModeChip();
}

function syncModeChip() {
  const chip = $('#modeChip');
  const a = S.auto;
  chip.className = 'mode-chip ' + (!a.aiOn ? 'off' : a.mode === 'auto' ? 'auto' : 'preview');
  chip.textContent = !a.aiOn ? '未开启' : a.mode === 'auto' ? '自动发送' : '仅预览';
}

/* 一条场景 → 卡片流水线 */
function runScenario(sc) {
  const a = S.auto;
  const card = document.createElement('div');
  card.className = 'fcard' + (sc.blocked ? ' blocked' : '');
  card.innerHTML = `
    <div class="fhead">
      <span class="grp">${esc(sc.chat.who)}</span>
      <span class="badge ${sc.ai ? 'b-violet' : 'b-blue'}">${esc(sc.label)}${sc.ai ? ' · AI' : ''}</span>
      <span class="tm num">${now()}</span>
    </div>
    <div class="pipe">${sc.steps.map((s, i) => `${i ? '<span class="arr">▸</span>' : ''}<span class="step" data-i="${i}">${esc(s)}</span>`).join('')}</div>
    <div class="qcard"></div>`;
  const feed = $('#autoFeed');
  feed.querySelector('.empty')?.remove();
  feed.prepend(card);
  const steps = [...card.querySelectorAll('.step')];
  const body = card.querySelector('.qcard');
  const qc = { el: card };
  if (sc.sendFail) card.dataset.sendFail = '1';
  a.cards.unshift(qc);
  if (a.cards.length > 6) { a.cards.pop(); a.cards.at(-1).el.remove(); }

  pushChat({ who: sc.chat.who, text: sc.chat.text, img: sc.chat.img, sys: false, imgClass: sc.chat.img ? 'vin-img' : '' });
  if (sc.sysNote) pushChat({ who: '系统', text: sc.sysNote, sys: true });

  const run = async () => {
    if (sc.blocked) {
      steps.forEach(s => s.classList.add('fail'));
      body.innerHTML = `<div style="padding:10px 6px;">
        <span class="badge b-red">已拦截</span>
        <span style="font-size:11px;color:var(--c-text-sub);margin-left:6px;">命中${esc(sc.blocked.reason)}：${esc(sc.blocked.who)}（设置 → 黑名单）</span></div>`;
      return;
    }
    for (const s of steps) { s.classList.add('run'); await sleep(320 + Math.random() * 380); s.classList.remove('run'); s.classList.add('done'); }
    if (sc.aiNote) body.innerHTML += `<div style="font-size:10px;color:#3a6ce0;background:#eef4ff;border-radius:var(--r-sm);padding:5px 8px;margin-bottom:8px;">AI：${esc(sc.aiNote)}</div>`;
    const r = { car: sc.vininfo || sc.car, product: sc.product || window.QQMock.SCENARIOS.find(x => x.product)?.product, partImagesList: sc.partImagesList };
    body.innerHTML = quoteCardHTML(r);
    bindCardActs(card, r);
    if (S.auto.aiOn && S.auto.mode === 'auto' && r.product) {
      body.querySelector('.act-send')?.click();
    }
  };
  run();
}

function startFeed() {
  clearInterval(S.auto.timer);
  S.auto.timer = setInterval(() => {
    if (S.view !== 'auto' || S.auto.paused || !S.settings) return;
    const list = window.QQMock.SCENARIOS;
    runScenario(list[S.auto.idx % list.length]);
    S.auto.idx++;
  }, 9000);
}

/* ---------- 视图注册 ---------- */
registerView({ key: 'auto', label: '自动报价', order: 10, render: renderAutoView });
