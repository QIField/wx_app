/* ===== 快捷报价面板 · 视图：手动报价（查询/AI对话/第三方比价/采购历史） ===== */
'use strict';

function renderManualView() {
  const m = S.manual;
  const subs = [ ['query', '查询报价'], ['ai', 'AI 对话'], ['third', '第三方比价'], ['history', '采购历史'] ];
  $('#qqBody').innerHTML = `
    <div class="view ${m.subTab === 'ai' ? 'ai-full' : ''}">
      <div class="sub-tabs">${subs.map(([k, t]) => `<span class="st ${m.subTab === k ? 'on' : ''}" data-sub="${k}">${t}</span>`).join('')}</div>
      <div id="manualBody"></div>
    </div>`;
  $('#qqBody').querySelectorAll('.st').forEach(el =>
    el.addEventListener('click', () => { m.subTab = el.dataset.sub; renderManualView(); }));
  renderManualSub();
}

function renderManualSub() {
  const m = S.manual;
  const box = $('#manualBody');
  if (m.subTab === 'query') {
    box.innerHTML = `
      <div class="mq-box">
        <div class="mq-row">
          <input class="input" id="mqInput" placeholder="输入 OE / VIN / 配件名称（如：节温器）" value="">
          <button class="btn primary" id="mqGo">查询</button>
        </div>
        <div class="mq-chips">
          <span class="chip" data-q="1665000075">OE 1665000075</span>
          <span class="chip" data-q="WBAWX3100G0L69597">VIN 宝马X3</span>
          <span class="chip" data-q="节温器">名称：节温器</span>
          <span class="chip" data-q="0005400017">无效OE演示</span>
        </div>
      </div>
      <div class="mq-res" id="mqRes">${m.result ? quoteCardHTML(m.result) : '<div class="empty">查询结果将在此输出（识别 → 译码 → CRM → 爆炸图）</div>'}</div>`;
    const go = () => manualQuery($('#mqInput').value.trim());
    $('#mqGo').addEventListener('click', go);
    $('#mqInput').addEventListener('keydown', e => { if (e.key === 'Enter') go(); });
    box.querySelectorAll('.chip').forEach(c => c.addEventListener('click', () => { $('#mqInput').value = c.dataset.q; manualQuery(c.dataset.q); }));
    if (m.result) bindCardActs($('#mqRes'), m.result);
  } else if (m.subTab === 'ai') {
    box.innerHTML = `
      <div class="ai-chat">
        <div class="ai-msgs" id="aiMsgs">${m.chatLog.map(l => `<div class="ai-msg ${l.role} ${l.need ? 'need' : ''}">${esc(l.text)}</div>`).join('') || '<div class="empty">支持 文字 / 图片 / 文件 输入，解析询价需求</div>'}</div>
        <div class="ai-inputs">
          <div class="ai-attach">
            <button class="btn sm" id="aiImg">🖼 图片</button>
            <button class="btn sm" id="aiFile">📎 文件</button>
            <span class="att-chip" id="aiAtt" style="display:none"></span>
          </div>
          <div class="ai-inputbox">
            <textarea class="ai-textarea" id="aiInput" placeholder="输入消息 / 粘贴聊天记录…"></textarea>
            <div class="ai-sendrow">
              <span class="ai-hint">Enter 发送 · Shift+Enter 换行</span>
              <button class="ai-send" id="aiSend" title="发送（Enter）">
                <svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true"><path d="M12 19V5M5.5 11.5 12 5l6.5 6.5" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>
              </button>
            </div>
          </div>
        </div>
      </div>`;
    const ta = $('#aiInput');
    const send = () => {
      const v = ta.value.trim();
      if (!v) { toast('请输入内容', 'err'); return; }
      aiChatStep(v);
      ta.value = '';
      ta.style.height = 'auto';
    };
    $('#aiSend').addEventListener('click', send);
    ta.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
    });
    ta.addEventListener('input', () => { ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight, 160) + 'px'; });
    $('#aiImg').addEventListener('click', () => { aiChatStep('系统备注：上一条是【老王】发的图片', 'img'); });
    $('#aiFile').addEventListener('click', () => aiChatStep('系统备注：上一条是【黄晓明】发的文件（需求.xlsx）', 'file'));
  } else if (m.subTab === 'third') {
    box.innerHTML = `
      <div class="sub-tabs">${[['zpy', '兆配云'], ['jqr', '机汽人']].map(([k, t]) => `<span class="st ${m.thirdTab === k ? 'on' : ''}" data-t="${k}">${t}</span>`).join('')}</div>
      <div id="thirdBody"><div class="skel"><span class="ring"></span>查询 ${m.thirdTab === 'zpy' ? 'platform_api/zpy' : 'platform_api/jqr'}（number=11538635689）…</div></div>`;
    box.querySelectorAll('[data-t]').forEach(el => el.addEventListener('click', () => { m.thirdTab = el.dataset.t; renderManualSub(); }));
    loadThird();
  } else {
    box.innerHTML = `<div class="skel"><span class="ring"></span>查询 crm_api/purchaseHistory_list（OE 1665000075）…</div>`;
    loadHistory();
  }
}

function detectType(q) {
  if (/^[A-HJ-NPR-Z0-9]{17}$/i.test(q)) return 'vin';
  if (/^[A-Z]{0,3}\d{6,12}$/i.test(q)) return 'oe';
  return 'name';
}

async function manualQuery(q) {
  if (!q) { toast('请输入查询内容', 'err'); return; }
  const res = $('#mqRes');
  res.innerHTML = '<div class="skel"><span class="ring"></span>解析中…</div>';
  S.manual.result = null;
  try {
    const type = detectType(q);
    let car = null, partno = null, product = null, piList = null;
    if (type === 'vin') {
      // qqCall 返回响应信封 {code,msg,data}，业务数据一律取 .data（mock 与真实接口同构）
      car = ((await qqCall('vininfo', { vin: q })).data || [])[0] || null;
      if (!car) throw new Error('VIN 未命中车型档案（200+空，按「查无此车」处理）');
      partno = (await qqCall('partno', { vin: q, originalPartsNos: '节温器' })).data;
    } else if (type === 'oe') {
      const pl = await qqCall('productList', { number: q });
      // product_list 分页信封：data = {total, per_page, current_page, data: {list, no_exist_oe}}
      const inner = (pl.data && pl.data.data) || pl.data || {};
      if (!inner.list || !inner.list.length) throw new Error(`OE 未命中产品档案：no_exist_oe=[${inner.no_exist_oe}]`);
      product = inner.list[0];
    } else {
      partno = (await qqCall('partno', { vin: 'WBAWX3100G0L69597', originalPartsNos: q })).data;
      if (!partno.oeCodeTrim) throw new Error('名称译码失败（字段空串=无档案）');
    }
    if (partno && partno.oeCodeTrim) {
      const pl = await qqCall('productList', { number: partno.oeCodeTrim });
      const inner2 = (pl.data && pl.data.data) || pl.data || {};
      product = (inner2.list && inner2.list[0]) || null;
      const pi = (await qqCall('partImages', { vin: car ? car.vin : 'WBAWX3100G0L69597', oeCode: partno.oeCodeTrim })).data;
      if (Array.isArray(pi) && pi[0] && pi[0].imageId) {
        piList = (await qqCall('partImagesList', { vin: car ? car.vin : 'WBAWX3100G0L69597', oeCode: partno.oeCodeTrim, imageIds: pi[0].imageId, carBrandId: car ? car.carBrandCode : 'BMW' })).data;
      }
    }
    if (!product && !car) throw new Error('无匹配结果');
    S.manual.result = { car: car || window.QQMock.VININFO[0], product, partImagesList: piList };
    res.innerHTML = quoteCardHTML(S.manual.result);
    bindCardActs(res, S.manual.result);
  } catch (e) {
    res.innerHTML = `<div class="empty"><span class="badge b-red">查询失败</span> <span style="margin-left:6px;">${esc(e.message)}</span></div>`;
  }
}

async function aiChatStep(text, kind) {
  const m = S.manual;
  if (kind) {
    m.chatLog.push({ role: 'user', text: kind === 'img' ? '[图片] 车架号照片.jpg' : '[文件] 需求.xlsx' });
    m.chatLog.push({ role: 'bot', text: '附件已登记（演示）。真实联调时：图片走 ocr_api/tx_vin（POST form: image_url 需公网可访问），文件暂存后按内容解析。' });
    renderChatLog(); return;
  }
  if (!text) { toast('请输入内容', 'err'); return; }
  m.chatLog.push({ role: 'user', text });
  renderChatLog();
  const script = window.QQMock.AI_CHAT_SCRIPT;
  const hit = script[m.chatIdx % script.length];
  m.chatIdx++;
  await sleep(500);
  m.chatLog.push({ role: 'bot', text: hit.bot.text, need: hit.bot.need });
  renderChatLog();
}

function renderChatLog() {
  const box = $('#aiMsgs');
  const m = S.manual;
  box.innerHTML = m.chatLog.map(l => `<div class="ai-msg ${l.role} ${l.need ? 'need' : ''}">${esc(l.text)}</div>`).join('');
  box.scrollTop = box.scrollHeight;
}

async function loadThird() {
  const body = $('#thirdBody');
  try {
    if (S.manual.thirdTab === 'zpy') {
      const env = await qqCall('zpy', { number: '11538635689' });
      const rows = Array.isArray(env.data) ? env.data : [];
      const min = Math.min(...rows.map(r => r['含税售价']));
      body.innerHTML = `<table class="ztable">
        <thead><tr><th>城市</th><th>库存</th><th>折扣</th><th>含税售价</th><th>4S含税进价</th></tr></thead>
        <tbody>${rows.map(r => `
          <tr class="${r['含税售价'] === min ? 'hl' : ''}">
            <td>${esc(r['城市'])}</td><td class="n">${esc(r['库存'])}</td>
            <td class="n">${esc(r['折扣'])}</td>
            <td class="n"><b>¥${esc(r['含税售价'])}</b>${r['含税售价'] === min ? ' <span class="badge b-green">最低</span>' : ''}</td>
            <td class="n">¥${esc(r['4S含税进价'])}</td></tr>`).join('')}</tbody></table>
        <div style="font-size:10px;color:var(--c-text-sub);margin-top:6px;">${esc(rows[0]['发货说明'])} · 数据来自 platform_api/zpy（响应为中文键名，价格字段混用字符串/数字已统一展示）</div>`;
    } else {
      const env = await qqCall('jqr', { number: '11538635689' });
      const d = env.data || { jy_data: [] };
      body.innerHTML = `<table class="ztable">
        <thead><tr><th>品牌</th><th>城市</th><th>供应商编码</th><th>等级</th><th>信用分</th><th>匹配分</th></tr></thead>
        <tbody>${d.jy_data.map(r => `
          <tr><td>${esc(r.custom_brand_name)}</td><td>${esc(r.city_name)}</td>
            <td class="n">${esc(r.default_code)}</td><td class="n">${esc(r.level_code)}</td>
            <td class="n">${esc(r.credit_score)}</td><td class="n">${esc(r._score)}</td></tr>`).join('')}</tbody></table>
        <div style="font-size:10px;color:var(--c-text-sub);margin-top:6px;">共 ${d.jy_data.length} 条竞价（演示条数，真实接口实测 230 条）· xj_data（询价数据）结构联调期展开</div>`;
    }
  } catch (e) {
    body.innerHTML = `<div class="empty"><span class="badge b-red">查询失败</span> ${esc(e.message)}</div>`;
  }
}

async function loadHistory() {
  const box = $('#manualBody');
  try {
    const d = await qqCall('purchaseHistory', { number: '1665000075', page: 1, limit: 10 });
    const t = d.data.total, list = d.data.list;
    box.innerHTML = `
      <div class="ph-summary">
        <div class="box"><div class="v num">${esc(t.purchase_quantity)}</div><div class="k">累计采购数量（件）</div></div>
        <div class="box"><div class="v num">¥${esc(t.totalprice)}</div><div class="k">累计采购金额</div></div>
      </div>
      <table class="ztable">
        <thead><tr><th>采购单号</th><th>配件</th><th>供应商</th><th>单价</th><th>数量</th><th>日期</th></tr></thead>
        <tbody>${list.data.map(r => `
          <tr><td class="n" title="${esc(r.order_no)}">${esc(r.order_no.slice(-9))}</td>
            <td>${esc(r.l_name_zh_default)}<small style="color:var(--c-text-sub)"> ${esc(r.brand)}</small></td>
            <td style="max-width:90px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${esc(r.company_name.replace('汽车零配件有限公司', '').replace('零配件有限公司', ''))}</td>
            <td class="n">¥${esc(r.price)}</td><td class="n">${esc(r.purchase_quantity)}</td>
            <td class="n">${ts2date(r.create_date)}</td></tr>`).join('')}</tbody></table>
      <div style="font-size:10px;color:var(--c-text-sub);margin-top:6px;">共 ${list.total} 条 · 当前 ${list.current_page}/${list.last_page} 页 · create_date 为 Unix 时间戳已格式化</div>`;
  } catch (e) {
    box.innerHTML = `<div class="empty"><span class="badge b-red">查询失败</span> ${esc(e.message)}</div>`;
  }
}

/* ---------- 视图注册 ---------- */
registerView({ key: 'manual', label: '手动报价', order: 20, render: renderManualView });
