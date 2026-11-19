/* ===== 快捷报价面板 · 应用层（分析视图/设置视图/外壳事件/启动） ===== */
'use strict';

/* ---------- 视图：报价分析 ---------- */
function renderAnalysis() {
  const d = window.QQMock.ANALYSIS[S.analysis.period];
  const max = Math.max(...d.series.quote);
  const cols = d.days.map((day, i) => `
    <div class="col">
      <div style="display:flex;gap:1px;width:100%;height:${Math.round(d.series.quote[i] / max * 82)}%;align-items:flex-end;">
        <div class="bar" style="height:100%;flex:1;" title="报价 ${d.series.quote[i]}"></div>
        <div class="bar oe" style="height:${Math.round(d.series.oe[i] / d.series.quote[i] * 100)}%;flex:1;" title="OE ${d.series.oe[i]}"></div>
      </div>
      <span class="lb">${esc(day)}</span>
    </div>`).join('');
  const arrow = n => `<span class="d ${n >= 0 ? 'up' : 'down'} num">${n >= 0 ? '▲' : '▼'} ${Math.abs(n)}%</span>`;
  $('#qqBody').innerHTML = `
    <div class="view">
      <div class="ana-toggle">
        <button class="btn ${S.analysis.period === 'day' ? 'on' : ''}" data-p="day">日报</button>
        <button class="btn ${S.analysis.period === 'month' ? 'on' : ''}" data-p="month">月报</button>
      </div>
      <div class="kpis">
        <div class="kpi"><div class="v num">${d.quote}</div><div class="k">报价次数</div>${arrow(d.trend.quote)}</div>
        <div class="kpi"><div class="v num">${d.oe}</div><div class="k">OE 报价次数</div>${arrow(d.trend.oe)}</div>
        <div class="kpi"><div class="v num">${d.vin}</div><div class="k">VIN 解析次数</div>${arrow(d.trend.vin)}</div>
      </div>
      <div class="sec-title">趋势<div class="line"></div></div>
      <div class="barchart">${cols}</div>
      <div class="legend"><span><i style="background:#e82016"></i>报价次数</span><span><i style="background:#5588f1"></i>OE 次数</span></div>
      <div class="sec-title">TOP 询价配件<div class="line"></div></div>
      <div class="rank-list">${d.top.map((t, i) => `
        <div class="rank"><span class="no">${i + 1}</span><span class="nm">${esc(t.name)} <span class="num" style="color:var(--c-text-sub)">${esc(t.oe)}</span></span><span class="ct">${t.ct} 次</span></div>`).join('')}</div>
    </div>`;
  $('#qqBody').querySelectorAll('[data-p]').forEach(b => b.addEventListener('click', () => { S.analysis.period = b.dataset.p; renderAnalysis(); }));
}

/* ---------- 视图：设置 ---------- */
function renderSettings() {
  const st = S.settings;
  const tplMap = {
    tplA: { n: '标准版', p: '【{车型}】\n{配件}（OE {oe}）\n{品牌价格}\n4S对照价 ¥{s4}\n现货速发，量大优惠' },
    tplB: { n: '热情推销版', p: '老板您好！{车型} {配件} 现货\n{品牌价格}\n比 4S 店（¥{s4}）便宜一大截\n质保齐全，下单即发 🚚' },
    tplC: { n: '极简版', p: '{配件}：{品牌价格}\nOE {oe}' },
  };
  $('#qqBody').innerHTML = `
    <div class="view">
      <div class="set-sec"><div class="sh">基础识别配置</div><div class="sb">
        <div class="set-row"><div class="rl"><div class="rt">AI 智能识别</div><div class="rs">关闭后进入普通模式：不自动分析新消息，手动查询报价不受影响</div></div><label class="switch sw"><input type="checkbox" id="setAi" ${st.aiOn ? 'checked' : ''}><span class="track"></span></label></div>
        <div class="set-row"><div class="rl"><div class="rt">自动报价模式</div><div class="rs">仅侧边预览只在面板展示；自动发送直接回复会话。开关取自通讯录备注模块，群开启优先于用户开启</div></div>
          <div class="radio-group"><span class="radio-pill ${st.autoMode === 'preview' ? 'on' : ''}" data-m="preview">仅侧边预览</span><span class="radio-pill ${st.autoMode === 'auto' ? 'on' : ''}" data-m="auto">自动发送</span></div></div>
        <div class="set-row" style="flex-direction:column;align-items:stretch;">
          <div class="rl"><div class="rt">配件黑名单</div><div class="rs">命中配件不报价、不自动发送（点击标签移除）</div></div>
          <div class="blk-tags" id="blkP">${st.blkParts.map((p, i) => `<span class="blk-tag" data-i="${i}">${esc(p)} <i>×</i></span>`).join('')}</div>
        </div>
      </div></div>
      <div class="set-sec"><div class="sh">价格</div><div class="sb">
        <div class="rs" style="margin-bottom:6px;">客户等级价格映射（报价 = 我方价 × 系数）</div>
        <table class="map-table"><thead><tr><th>客户等级</th><th>价格系数</th></tr></thead>
          <tbody>${st.priceMap.map((r, i) => `<tr><td>${esc(r.level)}</td><td><input class="input" data-mi="${i}" value="${esc(r.rate)}"></td></tr>`).join('')}</tbody></table>
      </div></div>
      <div class="set-sec"><div class="sh">报价话术模板</div><div class="sb">
        <div class="tpl-grid">${Object.entries(tplMap).map(([k, t]) => `<div class="tpl-card ${st.tpl === k ? 'on' : ''}" data-tpl="${k}"><div class="tn">${esc(t.n)}</div><div class="tp">${esc(t.p)}</div></div>`).join('')}</div>
        <div class="tpl-preview">${esc(tplMap[st.tpl].p)}</div>
        <div style="font-size:10px;color:var(--c-text-sub);margin-top:4px;">默认一版，后续动态新增模板</div>
      </div></div>
      <div class="set-sec"><div class="sh">通知配置</div><div class="sb">
        ${[['highInq', '高价值询价提醒', '单笔询价金额超过阈值时提醒'], ['highPart', '高价配件询价提醒', '4S 价超过阈值的配件被询价时提醒'], ['unFollow', '长时间未跟进询价提醒', '询价超过设定小时数未回复时提醒']].map(([k, t, s]) => `
          <div class="set-row notif-row"><div class="rl"><div class="rt">${t}</div><div class="rs">${s}</div></div>
            <input class="input th-input num" data-th="${k}" value="${esc(st.thresholds[k])}">
            <label class="switch sw"><input type="checkbox" data-nt="${k}" ${st.notify[k] ? 'checked' : ''}><span class="track"></span></label></div>`).join('')}
      </div></div>
    </div>`;
  $('#setAi').addEventListener('change', e => { st.aiOn = e.target.checked; S.auto.aiOn = e.target.checked; });
  $('#qqBody').querySelectorAll('.radio-pill').forEach(el => el.addEventListener('click', () => {
    st.autoMode = el.dataset.m; S.auto.mode = el.dataset.m; renderSettings(); syncModeChip();
  }));
  $('#qqBody').querySelectorAll('.blk-tag').forEach(el => el.addEventListener('click', () => {
    toast(`已移除黑名单：${st.blkParts[el.dataset.i]}`); st.blkParts.splice(el.dataset.i, 1); renderSettings();
  }));
  $('#qqBody').querySelectorAll('[data-mi]').forEach(inp => inp.addEventListener('change', () => { st.priceMap[inp.dataset.mi].rate = inp.value; }));
  $('#qqBody').querySelectorAll('[data-tpl]').forEach(el => el.addEventListener('click', () => { st.tpl = el.dataset.tpl; renderSettings(); }));
  $('#qqBody').querySelectorAll('[data-nt]').forEach(sw => sw.addEventListener('change', () => { st.notify[sw.dataset.nt] = sw.checked; toast(sw.checked ? '通知已开启' : '通知已关闭'); }));
  $('#qqBody').querySelectorAll('[data-th]').forEach(inp => inp.addEventListener('change', () => { st.thresholds[inp.dataset.th] = inp.value; }));
}

/* ---------- 视图注册 & 顶部菜单（注册表驱动，可拓展） ---------- */
registerView({ key: 'analysis', label: '报价分析', order: 30, render: renderAnalysis });
registerView({ key: 'settings', label: '设置', order: 90, render: renderSettings });

function renderMenu() {
  const menu = $('#qqMenu');
  menu.innerHTML = VIEW_REGISTRY.map(v => `
    <button class="m ${v.key === S.view ? 'on' : ''}" data-view="${v.key}">
      ${esc(v.label)}${v.badge ? '<span class="dot"></span>' : ''}
    </button>`).join('');
  menu.querySelectorAll('.m').forEach(el =>
    el.addEventListener('click', () => switchView(el.dataset.view)));
  syncMenuScroll();
}

/* 溢出时两侧渐隐提示还有更多入口 */
function syncMenuScroll() {
  const wrap = $('.qq-menu-wrap'), menu = $('#qqMenu');
  if (!wrap || !menu) return;
  const over = menu.scrollWidth > menu.clientWidth + 1;
  wrap.classList.toggle('can-l', over && menu.scrollLeft > 1);
  wrap.classList.toggle('can-r', over && menu.scrollLeft < menu.scrollWidth - menu.clientWidth - 1);
}

function switchView(v) {
  const def = getView(v);
  if (!def) { console.warn(`视图「${v}」未注册`); return; }
  S.view = v;
  document.querySelectorAll('.qq-menu .m').forEach(el => el.classList.toggle('on', el.dataset.view === v));
  def.render();
}

function bindShell() {
  $('#qqMenu').addEventListener('scroll', syncMenuScroll);
  window.addEventListener('resize', syncMenuScroll);
  $('#envChip').addEventListener('click', () => {
    const next = !window.QQIsMock();
    window.QQSetMock(next);
    const chip = $('#envChip');
    chip.classList.toggle('real', !next);
    chip.textContent = next ? 'MOCK 演示数据' : '真实接口 wx_api.fsbbr.net';
    toast(next ? '已切换 Mock 模式（离线可看）' : '已切换真实接口模式（需服务可达）', next ? '' : 'ok');
    switchView(S.view);
  });
  $('#chatBtnVin').addEventListener('click', () => { simulateIncoming(2); toast('已模拟 VIN 图片消息'); });
  $('#chatBtnOe').addEventListener('click', () => { simulateIncoming(0); toast('已模拟 OE 消息'); });
  $('#chatBtnName').addEventListener('click', () => { simulateIncoming(3); toast('已模拟 VIN+名称消息'); });
  $('#chatBtnNl').addEventListener('click', () => { simulateIncoming(4); toast('已模拟自然语言消息'); });
}

function simulateIncoming(idx) {
  if (S.view !== 'auto') switchView('auto');
  S.auto.paused = false;
  runScenario(window.QQMock.SCENARIOS[idx]);
}

/* ---------- 启动 ---------- */
function init() {
  pushChat({ who: '老王', img: window.QQMock.IMG_VIN, imgClass: 'vin-img', text: '' });
  pushChat({ who: '系统', text: '上一条是【老王】发的图片', sys: true });
  pushChat({ who: '马斯克', text: '885625662 火花塞 有货吗' });
  pushChat({ who: '我', text: '885625662 马勒铱金 ¥120，现货', self: true });
  pushChat({ who: '黄晓明', text: '油底壳 节温器' });
  renderMenu();
  switchView(VIEW_REGISTRY[0]?.key || 'auto');
  bindShell();
  startFeed();
  setTimeout(() => runScenario(window.QQMock.SCENARIOS[2]), 1200);
}

document.addEventListener('DOMContentLoaded', init);
