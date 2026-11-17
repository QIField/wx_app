/* ===== 快捷报价面板 · 共享基础（工具/状态/提示/聊天区/报价卡） ===== */
'use strict';

const $ = sel => document.querySelector(sel);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
const now = () => new Date().toTimeString().slice(0, 8);
const ts2date = ts => { const d = new Date(Number(ts) * 1000); return isNaN(d) ? '-' : `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`; };

/* ---------- 全局状态 ---------- */
const S = {
  view: 'auto',
  auto: { aiOn: true, mode: 'preview', paused: false, cards: [], timer: null, idx: 0 },
  manual: { subTab: 'query', thirdTab: 'zpy', loading: false, result: null, chatLog: [], chatIdx: 0 },
  analysis: { period: 'day' },
  settings: {
    aiOn: true, autoMode: 'preview',
    blkParts: ['保险杠总成', '发动机总成'],
    priceMap: [
      { level: 'VIP-A（月结大客户）', rate: '0.75' },
      { level: 'VIP-B（月结）', rate: '0.82' },
      { level: '普通客户', rate: '0.90' },
      { level: '新客试用', rate: '0.95' },
    ],
    tpl: 'tplA', notify: { highInq: true, highPart: true, unFollow: false },
    thresholds: { highInq: '5000', highPart: '3000', unFollow: '24' },
  },
};

/* ---------- 视图注册表（可拓展入口） ----------
   顶部菜单不写死：任意模块加载后调用
   registerView({ key, label, order, render, badge })
   即自动进入顶栏菜单；order 越小越靠前；badge=true 显示红点（新功能提醒）。
*/
const VIEW_REGISTRY = [];

function registerView(def) {
  if (!def.key || typeof def.render !== 'function') {
    throw new Error(`registerView「${def.key || '(无名)'}」缺少 key 或 render`);
  }
  VIEW_REGISTRY.push(def);
  VIEW_REGISTRY.sort((a, b) => (a.order ?? 999) - (b.order ?? 999));
}

function getView(key) {
  return VIEW_REGISTRY.find(v => v.key === key);
}

/* ---------- 提示 ---------- */
function toast(text, type = '') {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = text;
  $('.toast-wrap').appendChild(el);
  setTimeout(() => el.remove(), 2400);
}

/* ---------- 左侧聊天区 ---------- */
function pushChat({ who, text = '', img = '', sys = false, self = false, imgClass = '' }) {
  const wrap = document.createElement('div');
  wrap.className = 'msg' + (sys ? ' sys' : '') + (self ? ' self' : '');
  const avatar = `<span class="who">${esc((who || '系')[0])}</span>`;
  const content = sys
    ? esc(text)
    : (img ? `<img class="${imgClass || 'vin-img'}" src="${img}" alt="">` : esc(text));
  wrap.innerHTML = `${avatar}<div class="bubble">${sys ? '' : `<div class="meta">${esc(who)} ${now()}</div>`}${content}</div>`;
  const body = $('#chatBody');
  body.appendChild(wrap);
  body.scrollTop = body.scrollHeight;
}

/* ---------- 报价卡渲染（自动/手动共用） ---------- */
/* 改价契约：r._price 为发送价覆盖值，未改价回退 product.cost_price */
const qPrice = r => (r && r._price != null ? r._price : r && r.product ? r.product.cost_price : '0');

function quoteCardHTML(r) {
  const { car, product: p, partImagesList } = r;
  const carLine = car
    ? `<div class="car"><b>${esc(car.brandName)} ${esc(car.model)}</b> ${esc(car.yearPattern)}款 ${esc(car.displacement)} ${esc(car.fuel)} · VIN ${esc(car.vin)}</div>`
    : '';
  const thumb = p && p.image ? `<img class="thumb" src="${p.image}" alt="">` : `<div class="thumb" style="display:grid;place-items:center;color:#9aa7bc;font-size:10px;">无图</div>`;
  const price = p ? `
    <div class="price-line">
      <span class="mine num">¥${esc(qPrice(r))}<small> 起我方价</small></span>
      <button class="price-edit act-price" title="发送前改价">✎</button>
      ${r._edited ? '<span class="badge b-orange">已改价</span>' : ''}
      <span class="s4 num">4S ¥${esc(p.store_price)}</span>
      <span class="save">省 ${Math.max(0, Math.round((1 - Number(qPrice(r)) / Number(p.store_price)) * 100))}%</span>
    </div>` : '';
  const rows = p && p.child ? `
    <table class="qtable">
      <thead><tr><th>品牌</th><th>我方价</th><th>4S价</th><th>库存</th></tr></thead>
      <tbody>${p.child.map((c, i) => `
        <tr class="${i === 0 ? 'me' : ''}">
          <td>${esc(c.brand_name)}${i === 0 ? ' <span class="badge b-green">推荐</span>' : ''}</td>
          <td class="n">¥${esc(c.cost_price)}</td>
          <td class="n">¥${esc(c.store_price)}</td>
          <td class="n">${c.stock > 0 ? esc(c.stock) : '<span class="badge b-red">缺货</span>'}</td>
        </tr>`).join('')}</tbody>
    </table>` : '';
  const exp = partImagesList ? `
    <table class="qtable">
      <thead><tr><th>标号</th><th>周边配件（爆炸图）</th><th>OE</th><th>4S价</th><th>用量</th></tr></thead>
      <tbody>${partImagesList.data.map(it => `
        <tr><td class="n">${esc(it.imageLabel)}</td>
          <td>${esc(it.oeName)}<small style="color:var(--c-text-sub)"> / ${esc(it.stdName)}</small></td>
          <td class="n">${esc(it.oeCode)}</td>
          <td class="n">¥${esc(it.price4s)}</td>
          <td class="n">×${esc(it.count)}</td></tr>`).join('')}</tbody>
    </table>` : '';
  const acts = p ? `
    <div class="qacts">
      <button class="btn sm primary act-send">发送报价</button>
      <button class="btn sm act-copy">复制话术</button>
      <button class="btn sm act-link">选购链接 ↗</button>
      <span class="sent-tag"></span>
    </div>` : '';
  return `${carLine}
    <div class="qrow">${thumb}
      <div class="qinfo">
        <div class="pname">${esc(p ? p.product_name : '')}</div>
        <div class="poe">OE ${esc(p ? p.display_number.value : '')} · store ${esc(p ? p.store_number : '')} · PARTENT ${esc(p ? p.partent_number : '')}</div>
        ${price}
        <div style="font-size:10px;color:var(--c-text-sub);margin-top:4px;">卖点：${esc(p ? p.sell_point : '')}</div>
      </div>
    </div>${rows}${exp}${acts}`;
}

function bindCardActs(card, r) {
  const send = card.querySelector('.act-send');
  const sentTag = card.querySelector('.sent-tag');
  if (send) send.addEventListener('click', () => {
    // 失败态契约：sendFail=1 的卡首次发送失败，转可重试（重试成功）
    if (card.dataset.sendFail === '1') {
      card.classList.add('failed');
      send.textContent = '重试发送';
      sentTag.innerHTML = '<span class="badge b-red">✕ 发送失败</span>';
      card.dataset.sendFail = '0';
      toast('发送失败，可重试', 'err');
      return;
    }
    send.disabled = true;
    card.dataset.sent = '1';
    card.classList.remove('failed');
    sentTag.innerHTML = '<span class="badge b-green">✓ 已发送至会话</span>';
    // 产品决议：图片在前只发产品图，随后文本话术（分开发，默认发）
    if (r.product && r.product.image) pushChat({ who: '我', img: r.product.image, self: true });
    pushChat({ who: '我', text: quoteText(r), self: true });
    toast('报价已发送（产品图 + 话术）', 'ok');
  });
  // 改价：发送前手动调整价格（话术/省比联动；业务端 price_json 记改后价）
  const pe = card.querySelector('.act-price');
  if (pe) pe.addEventListener('click', () => {
    if (card.dataset.sent) return;
    const line = pe.closest('.price-line');
    line.innerHTML = `<input class="input num price-input" inputmode="decimal" value="${esc(qPrice(r))}">
      <button class="btn sm primary price-ok">确定</button><button class="btn sm price-no">取消</button>`;
    const inp = line.querySelector('.price-input');
    inp.focus(); inp.select();
    const close = ok => {
      if (ok) {
        const v = parseFloat(inp.value);
        if (!v || v <= 0) { toast('请输入有效价格', 'err'); inp.focus(); return; }
        r._price = v.toFixed(2); r._edited = true;
      }
      card.querySelector('.qcard').innerHTML = quoteCardHTML(r);
      bindCardActs(card, r);
      if (ok) toast(`已改价：¥${r._price}`, 'ok');
    };
    line.querySelector('.price-ok').addEventListener('click', () => close(true));
    line.querySelector('.price-no').addEventListener('click', () => close(false));
    inp.addEventListener('keydown', e => { if (e.key === 'Enter') close(true); if (e.key === 'Escape') close(false); });
  });
  const copy = card.querySelector('.act-copy');
  if (copy) copy.addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(quoteText(r)); toast('话术已复制', 'ok'); }
    catch { toast('复制失败（浏览器限制）', 'err'); }
  });
  const link = card.querySelector('.act-link');
  if (link) link.addEventListener('click', () => toast('演示原型：跳转选购链接（对接 CRM 商城）'));
}

function quoteText(r) {
  const p = r.product, car = r.car;
  let t = '';
  if (car) t += `【${car.brandName} ${car.model} ${car.yearPattern}款 ${car.displacement}】\n`;
  if (p) {
    t += `${p.product_name}（OE ${p.display_number.value}）\n`;
    t += p.child.map(c => `${c.brand_name} ¥${c.cost_price}${c.stock > 0 ? '' : '(缺货)'}`).join(' / ') + '\n';
    if (r._edited) t += `报价 ¥${qPrice(r)}\n`;
    t += `4S对照价 ¥${p.store_price}`;
  }
  return t || '（无匹配产品）';
}
