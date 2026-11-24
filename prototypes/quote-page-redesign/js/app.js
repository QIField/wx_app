/**
 * app.js — 报价页面交互引擎
 * 状态管理：集中管理当前选中配件、编辑中的表格行、汇总联动
 */
import { DB } from './mock.js';
import {
  fetchVehicle, fetchCustomer, fetchParts, fetchQuoteItems,
  fetchSummary, previewQuote, sendQuote, updateQuoteItem,
  removeQuoteItem
} from './api.js';

/* ============================================================
   Global State
   ============================================================ */
const state = {
  vehicle: null,
  customer: null,
  parts: [],
  quoteItems: [],
  summary: null,
  activePartId: null,
  selectedRowId: null,
  editedFields: new Map() // rowId -> { field: value }
};

/* ============================================================
   Formatting Helpers
   ============================================================ */
const fmt = {
  money(n) {
    if (n == null || isNaN(n)) return '¥0.00';
    return '¥' + Number(n).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  },
  num(n) {
    if (n == null || isNaN(n)) return '0';
    return Number(n).toString();
  },
  date(d) {
    if (!d) return '';
    return new Date(d).toISOString().slice(0, 10);
  }
};

/* ============================================================
   Toast
   ============================================================ */
function toast(msg, type = 'info') {
  const c = document.getElementById('toastContainer');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  const icons = {
    success: '<svg class="i-16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="color:#15803d"><polyline points="20 6 9 17 4 12"/></svg>',
    error: '<svg class="i-16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="color:#dc2626"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>',
    info: '<svg class="i-16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="color:#3b82f6"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>'
  };
  el.innerHTML = `${icons[type] || icons.info}<span>${msg}</span>`;
  c.appendChild(el);
  setTimeout(() => {
    el.style.opacity = '0';
    el.style.transform = 'translateX(30px)';
    el.style.transition = 'all 0.25s';
    setTimeout(() => el.remove(), 250);
  }, 2500);
}

/* ============================================================
   Renderers
   ============================================================ */

// --- Vehicle Banner ---
function renderVehicle() {
  const v = state.vehicle;
  if (!v) return;
  document.getElementById('vbTitle').textContent =
    `${v.brand} ${v.model} ${v.yearPattern} ${v.displacement}`;

  const fields = [
    { label: '发动机', value: v.engineModel },
    { label: '燃油', value: v.fuelType },
    { label: '底盘', value: v.chassisModel },
    { label: '变速箱', value: v.transmission },
    { label: 'VIN', value: v.vin, mono: true }
  ];
  document.getElementById('vbFields').innerHTML = fields.map(f => `
    <div class="vb-field">
      <span class="vb-field__label">${f.label}</span>
      <span class="vb-field__value" ${f.mono ? '' : ''}>${f.value}</span>
    </div>
  `).join('');
}

// --- Customer Info ---
function renderCustomer() {
  const c = state.customer;
  if (!c) return;
  const rows = [
    { label: '询价群', value: c.name },
    { label: '询价人', value: `${c.inquiryPerson}（${c.wechatId}）` },
    { label: '客户类型', value: c.type },
    { label: '询价单号', value: c.inquiryNo },
    { label: '创建时间', value: c.createdAt },
    { label: '初始报价单价', value: c.quotePrice, highlight: true }
  ];
  document.getElementById('customerInfo').innerHTML = rows.map(r => `
    <div class="info-card__row">
      <span class="info-card__label">${r.label}</span>
      <span class="info-card__value ${r.highlight ? 'highlight' : ''}">${r.value}</span>
    </div>
  `).join('');
}

// --- Part Sidebar List ---
function renderParts() {
  const list = document.getElementById('partList');
  document.getElementById('partCount').textContent = `共 ${state.parts.length} 项`;

  list.innerHTML = state.parts.map((p, idx) => `
    <div class="part-card ${p.id === state.activePartId ? 'active' : ''}" data-id="${p.id}"
         onclick="App.selectPart(${p.id})">
      <div class="part-card__head">
        <div class="part-card__index">${idx + 1}</div>
        <div class="part-card__name">${p.name}</div>
        <button class="part-card__remove" onclick="event.stopPropagation();App.removePart(${p.id})" title="移除">
          <svg class="i-14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>
      <div class="part-card__meta">
        <span>OE <span>${p.oe}</span></span>
        <span class="part-card__price">${fmt.money(p.unitPrice)}</span>
        <span>×${p.quantity}</span>
      </div>
    </div>
  `).join('');
}

// --- Active Part Header ---
function renderActivePartHeader() {
  const p = state.parts.find(x => x.id === state.activePartId) || state.parts[0];
  if (!p) return;
  document.getElementById('activePartName').textContent = p.name;
  document.getElementById('activeOeTag').textContent = `OE ${p.oe}`;
}

// --- QUOTE SUMMARY CARD (KEY HIGHLIGHT) ---
function renderSummary() {
  const s = state.summary;
  if (!s) return;

  const discountAbs = s.discount || 0;
  const discountPct = s.subtotal > 0 ? ((discountAbs / s.subtotal) * 100).toFixed(1) : 0;

  document.getElementById('quoteSummary').innerHTML = `
    <div class="quote-summary__header">
      <div class="quote-summary__title">
        <svg class="i-14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
        报价汇总摘要
      </div>
      <span class="quote-summary__badge">最终生效</span>
    </div>
    <div class="quote-summary__main">
      <div class="quote-summary__price">
        <div class="quote-summary__price-label">最终报价</div>
        <div class="quote-summary__price-value">
          <span class="currency">¥</span>${s.finalPrice.toFixed(2)}
        </div>
        <div class="quote-summary__price-sub">
          共 ${s.itemCount} 项配件 · 含税费 · 已减优惠
        </div>
      </div>
      <div class="quote-summary__stats">
        <div class="qs-stat">
          <div class="qs-stat__label">配件小计</div>
          <div class="qs-stat__value">${fmt.money(s.subtotal)}</div>
        </div>
        <div class="qs-stat">
          <div class="qs-stat__label">税费合计</div>
          <div class="qs-stat__value">${fmt.money(s.taxTotal)}</div>
        </div>
        <div class="qs-stat">
          <div class="qs-stat__label">优惠金额</div>
          <div class="qs-stat__value discount">
            ${discountAbs > 0 ? `-${fmt.money(discountAbs)}` : '¥0.00'}
            <span style="font-size:11px;color:rgba(255,255,255,0.55);margin-left:4px">(${discountPct}%)</span>
          </div>
        </div>
        <div class="qs-stat">
          <div class="qs-stat__label">有效期至</div>
          <div class="qs-stat__value expiry">
            <svg class="i-14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:-3px;margin-right:3px">
              <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
            </svg>
            ${s.expiryDate}
          </div>
        </div>
      </div>
    </div>
    <div class="quote-summary__footer">
      <div class="qs-terms">
        <span>
          <svg class="i-12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
          含税报价
        </span>
        <span>
          <svg class="i-12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
          支持对公转账
        </span>
        <span>
          <svg class="i-12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
          7 天无理由退换
        </span>
      </div>
      <div>${new Date().toLocaleString('zh-CN')} 生成</div>
    </div>
  `;
}

// --- Quote Items Table ---
function renderQuoteTable() {
  const tbody = document.getElementById('quoteTableBody');
  document.getElementById('tableCount').textContent = `共 ${state.quoteItems.length} 条`;

  tbody.innerHTML = state.quoteItems.map((it, idx) => {
    // Stock badge
    let stockBadge = '';
    if (it.stock > 10) stockBadge = `<span class="stock-badge in">${it.stock}</span>`;
    else if (it.stock > 0) stockBadge = `<span class="stock-badge low">仅剩 ${it.stock}</span>`;
    else stockBadge = `<span class="stock-badge out">缺货</span>`;

    // Image cell
    const imgCell = it.image
      ? `<td style="width:58px">
           <img class="part-thumb" src="${it.image}" alt="" loading="lazy" title="点击查看大图"
                onclick="App.previewImg('${it.image}')">
         </td>`
      : `<td style="width:58px"><div class="part-thumb placeholder">图</div></td>`;

    return `
      <tr data-id="${it.id}" class="${it.id === state.selectedRowId ? 'editing' : ''}">
        ${imgCell}
        <td class="td-oe">
          <input class="tinput oe-input" value="${it.oe}" data-field="oe" data-id="${it.id}">
        </td>
        <td class="td-input-cell">
          <input class="tinput" value="${it.customCode || ''}" data-field="customCode" data-id="${it.id}">
        </td>
        <td class="td-input-cell">
          <input class="tinput brand-input" value="${it.brand || ''}" data-field="brand" data-id="${it.id}">
        </td>
        <td class="td-input-cell">
          <input class="tinput" value="${it.spec || ''}" data-field="spec" data-id="${it.id}" style="min-width:120px">
        </td>
        <td>
          <input class="tinput num" style="text-align:right;width:90px" value="${it.salePrice}" data-field="salePrice" data-id="${it.id}">
        </td>
        <td>
          <span style="font-family:var(--f-num);color:var(--c-text-sub)">${fmt.money(it.costPrice)}</span>
        </td>
        <td>
          <span class="tax-display" style="font-family:var(--f-num);color:var(--c-text);text-align:right;display:block">${fmt.money(it.tax)}</span>
        </td>
        <td style="text-align:center">
          ${stockBadge}
        </td>
        <td class="td-input-cell">
          <input class="tinput" value="${it.warranty || ''}" data-field="warranty" data-id="${it.id}">
        </td>
        <td class="td-input-cell">
          <input class="tinput" value="${it.remark || ''}" data-field="remark" data-id="${it.id}" style="min-width:110px">
        </td>
        <td style="text-align:center">
          <div class="row-actions" style="display:flex;justify-content:center">
            <button class="row-btn" title="复制行" onclick="App.duplicateRow(${it.id})">
              <svg class="i-14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
            </button>
            <button class="row-btn danger" title="删除" onclick="App.deleteRow(${it.id})">
              <svg class="i-14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-2 14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2L5 6"/></svg>
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join('');

  // Update footer totals
  const subtotal = state.quoteItems.reduce((a, b) => a + Number(b.salePrice || 0), 0);
  const costSubtotal = state.quoteItems.reduce((a, b) => a + Number(b.costPrice || 0), 0);
  const taxSubtotal = state.quoteItems.reduce((a, b) => a + Number(b.tax || 0), 0);
  document.getElementById('ftSaleSub').textContent = fmt.money(subtotal);
  document.getElementById('ftCostSub').textContent = fmt.money(costSubtotal);
  document.getElementById('ftTaxSub').textContent = fmt.money(taxSubtotal);

  // Bind input events
  tbody.querySelectorAll('input.tinput').forEach(input => {
    input.addEventListener('input', (e) => {
      const id = Number(e.target.dataset.id);
      const field = e.target.dataset.field;
      const row = state.quoteItems.find(x => x.id === id);
      if (!row) return;
      const newVal = e.target.value;
      row[field] = field.includes('Price') || field === 'tax' ? Number(newVal) || 0 : newVal;

      // Auto-recalc tax if sale price changes (simple 13%)
      if (field === 'salePrice') {
        row.tax = Number((Number(newVal) * 0.13).toFixed(2));
        updateDisplayTax(id);
      }
      updateDisplaySummary();
    });
    input.addEventListener('focus', () => {
      state.selectedRowId = Number(input.dataset.id);
      tbody.querySelectorAll('tr').forEach(tr => tr.classList.remove('editing'));
      tbody.querySelector(`tr[data-id="${state.selectedRowId}"]`)?.classList.add('editing');
    });
  });
}

function updateDisplayTax(rowId) {
  const row = document.querySelector(`tr[data-id="${rowId}"]`);
  if (!row) return;
  const it = state.quoteItems.find(x => x.id === rowId);
  if (!it) return;
  const taxDisplay = row.querySelector('.tax-display');
  if (taxDisplay) taxDisplay.textContent = fmt.money(it.tax);
}

function updateDisplaySummary() {
  const s = state.summary;
  if (!s) return;
  const subtotal = state.quoteItems.reduce((a, b) => a + Number(b.salePrice || 0), 0);
  const taxTotal = state.quoteItems.reduce((a, b) => a + Number(b.tax || 0), 0);
  s.subtotal = subtotal;
  s.taxTotal = taxTotal;
  s.finalPrice = subtotal + taxTotal - (s.discount || 0);
  s.itemCount = state.quoteItems.length;
  renderSummary();

  // Update footer totals
  document.getElementById('ftSaleSub').textContent = fmt.money(subtotal);
  document.getElementById('ftTaxSub').textContent = fmt.money(taxTotal);
}

/* ============================================================
   Actions (exposed as global App)
   ============================================================ */
window.App = {

  async init() {
    const [vRes, cRes, pRes, qRes, sRes] = await Promise.all([
      fetchVehicle(1), fetchCustomer(1), fetchParts(1),
      fetchQuoteItems(1), fetchSummary(1)
    ]);
    state.vehicle = vRes.data;
    state.customer = cRes.data;
    state.parts = pRes.data;
    state.quoteItems = qRes.data;
    state.summary = sRes.data;
    state.activePartId = state.parts[0]?.id;

    renderVehicle();
    renderCustomer();
    renderParts();
    renderActivePartHeader();
    renderSummary();
    renderQuoteTable();

    // Bind footer inputs
    const discountEl = document.getElementById('discountInput');
    discountEl.addEventListener('input', (e) => {
      state.summary.discount = Number(e.target.value) || 0;
      updateDisplaySummary();
    });
    const validDaysEl = document.getElementById('validDaysInput');
    validDaysEl.addEventListener('input', (e) => {
      const days = Number(e.target.value) || 0;
      const expiry = new Date();
      expiry.setDate(expiry.getDate() + days);
      state.summary.validDays = days;
      state.summary.expiryDate = expiry.toISOString().slice(0, 10);
      document.getElementById('expiryDate').textContent = state.summary.expiryDate;
      renderSummary();
    });
  },

  selectPart(id) {
    state.activePartId = id;
    renderParts();
    renderActivePartHeader();
  },

  addPart() {
    const newPart = {
      id: Date.now(),
      name: '新配件',
      oe: 'A' + Date.now().toString().slice(-8),
      brand: '待填写',
      brandType: '',
      quantity: 1,
      stock: 0,
      unitPrice: 0
    };
    state.parts.push(newPart);
    state.activePartId = newPart.id;
    renderParts();
    renderActivePartHeader();
    toast(`已添加配件「${newPart.name}」`, 'info');
  },

  removePart(id) {
    const idx = state.parts.findIndex(p => p.id === id);
    if (idx >= 0) {
      state.parts.splice(idx, 1);
      if (state.activePartId === id) {
        state.activePartId = state.parts[0]?.id;
      }
      renderParts();
      renderActivePartHeader();
      toast('已移除配件', 'info');
    }
  },

  addQuoteRow() {
    const newRow = {
      id: Date.now(),
      oe: 'A' + Date.now().toString().slice(-8),
      customCode: '',
      brand: '',
      brandColor: '',
      spec: '',
      salePrice: 0,
      costPrice: 0,
      tax: 0,
      stock: 0,
      warranty: '',
      remark: ''
    };
    state.quoteItems.push(newRow);
    renderQuoteTable();
    updateDisplaySummary();
    toast('已新增一行报价项', 'info');
  },

  async deleteRow(id) {
    await removeQuoteItem(1, id);
    state.quoteItems = state.quoteItems.filter(x => x.id !== id);
    renderQuoteTable();
    updateDisplaySummary();
    toast('已删除该报价项', 'info');
  },

  duplicateRow(id) {
    const src = state.quoteItems.find(x => x.id === id);
    if (!src) return;
    const copy = { ...src, id: Date.now(), oe: src.oe + '(复)' };
    state.quoteItems.push(copy);
    renderQuoteTable();
    updateDisplaySummary();
    toast('已复制该报价项', 'info');
  },

  setDiscountQuick() {
    const sub = state.summary.subtotal;
    const pct = prompt('输入优惠百分比（如 5 代表 5%）：', '5');
    if (pct !== null) {
      const amount = (sub * Number(pct) / 100).toFixed(2);
      document.getElementById('discountInput').value = amount;
      state.summary.discount = Number(amount);
      updateDisplaySummary();
      toast(`已设置优惠 ¥${amount}`, 'success');
    }
  },

  async showPreview() {
    const res = await previewQuote(1);
    const content = document.getElementById('previewContent');
    content.textContent = res.data.text;
    document.getElementById('previewModal').classList.add('show');
  },

  closeModal(id) {
    document.getElementById(id).classList.remove('show');
  },

  copyPreview() {
    const text = document.getElementById('previewContent').textContent;
    navigator.clipboard.writeText(text).then(() => {
      toast('话术已复制到剪贴板', 'success');
    }).catch(() => {
      toast('复制失败，请手动选择复制', 'error');
    });
  },

  async sendQuote(silent = false) {
    const btn = event?.target?.closest('.btn-primary');
    if (btn) { btn.disabled = true; btn.innerHTML = btn.innerHTML + '...'; }
    try {
      await sendQuote(1, {});
      toast('报价已发送至客户会话', 'success');
    } catch (e) {
      toast('发送失败：' + e.message, 'error');
    } finally {
      if (btn) { btn.disabled = false; }
    }
  },

  previewImg(src) {
    const overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.85);display:grid;place-items:center;z-index:300;cursor:zoom-out';
    overlay.innerHTML = `<img src="${src}" style="max-width:90vw;max-height:90vh;border-radius:12px">`;
    overlay.onclick = () => overlay.remove();
    document.body.appendChild(overlay);
  },

  openDetailPage() {
    toast('即将跳转报价详情页（当前已是详情页）', 'info');
  },

  jumpToBubble() {
    // 模拟定位聊天气泡
    const el = document.getElementById('quoteSummary');
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      el.style.transition = 'box-shadow 0.3s';
      el.style.boxShadow = '0 0 0 4px rgba(232,32,22,0.4), 0 8px 24px rgba(14,28,61,0.12)';
      setTimeout(() => el.style.boxShadow = '', 1500);
    }
    toast('已定位到报价卡片', 'success');
  }
};

/* ============================================================
   Clock
   ============================================================ */
function updateClock() {
  const now = new Date();
  const pad = n => String(n).padStart(2, '0');
  document.getElementById('currentTime').textContent =
    `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}`;
}
setInterval(updateClock, 60000);
updateClock();

/* ============================================================
   Boot
   ============================================================ */
document.addEventListener('DOMContentLoaded', () => {
  window.App.init();
});

/* Close modal on overlay click */
document.querySelectorAll('.modal-overlay').forEach(overlay => {
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) overlay.classList.remove('show');
  });
});
