/**
 * api.js — 报价模块 API 存根
 * 数据来源于 mock.js，真实部署时替换为 fetch('/api/quote/...')
 *
 * 每个函数保留了 HTTP method + path 注释，方便后续 backend-handoff 时
 * 机械提取契约。
 */
import { DB } from './mock.js';

const delay = (ms = 300) => new Promise(r => setTimeout(r, ms));

/* ========== 车辆 & 客户信息 ========== */

// TODO: GET /api/quote/inquiries/:id/vehicle
export async function fetchVehicle(id) {
  await delay(200);
  return { code: 0, data: DB.vehicle };
}

// TODO: GET /api/quote/inquiries/:id/customer
export async function fetchCustomer(id) {
  await delay(150);
  return { code: 0, data: DB.customer };
}

/* ========== 配件清单 ========== */

// TODO: GET /api/quote/inquiries/:id/parts
export async function fetchParts(inquiryId) {
  await delay(250);
  return { code: 0, data: DB.parts };
}

// TODO: POST /api/quote/inquiries/:id/parts
export async function addPart(inquiryId, partData) {
  await delay(300);
  const newPart = {
    id: Date.now(),
    ...partData,
    stock: 0,
    unitPrice: 0
  };
  DB.parts.push(newPart);
  return { code: 0, data: newPart };
}

// TODO: DELETE /api/quote/inquiries/:id/parts/:partId
export async function removePart(inquiryId, partId) {
  await delay(200);
  const idx = DB.parts.findIndex(p => p.id === partId);
  if (idx >= 0) DB.parts.splice(idx, 1);
  return { code: 0 };
}

/* ========== 报价明细表格 ========== */

// TODO: GET /api/quote/inquiries/:id/items
export async function fetchQuoteItems(inquiryId) {
  await delay(350);
  return { code: 0, data: DB.quoteItems };
}

// TODO: PUT /api/quote/inquiries/:id/items/:itemId
export async function updateQuoteItem(inquiryId, itemId, patch) {
  await delay(150);
  const item = DB.quoteItems.find(i => i.id === itemId);
  if (item) Object.assign(item, patch);
  recalcSummary();
  return { code: 0, data: item };
}

// TODO: POST /api/quote/inquiries/:id/items
export async function addQuoteItem(inquiryId, itemData) {
  await delay(250);
  const newItem = { id: Date.now(), ...itemData };
  DB.quoteItems.push(newItem);
  recalcSummary();
  return { code: 0, data: newItem };
}

// TODO: DELETE /api/quote/inquiries/:id/items/:itemId
export async function removeQuoteItem(inquiryId, itemId) {
  await delay(200);
  const idx = DB.quoteItems.findIndex(i => i.id === itemId);
  if (idx >= 0) DB.quoteItems.splice(idx, 1);
  recalcSummary();
  return { code: 0 };
}

/* ========== 费用汇总 ========== */

// TODO: GET /api/quote/inquiries/:id/summary
export async function fetchSummary(inquiryId) {
  await delay(100);
  return { code: 0, data: DB.summary };
}

// 本地重新计算汇总（前端实时联动）
function recalcSummary() {
  const items = DB.quoteItems;
  let subtotal = 0, taxTotal = 0;
  items.forEach(it => {
    subtotal += Number(it.salePrice) * 1 || 0;
    taxTotal += Number(it.tax) * 1 || 0;
  });
  DB.summary.subtotal = subtotal;
  DB.summary.taxTotal = taxTotal;
  DB.summary.finalPrice = subtotal + taxTotal - DB.summary.discount;
  DB.summary.itemCount = items.length;
}

/* ========== 发送 & 预览 ========== */

// TODO: POST /api/quote/inquiries/:id/send
export async function sendQuote(inquiryId, payload) {
  await delay(800); // 模拟网络延迟
  // 模拟随机成功/失败
  return { code: 0, data: { sentAt: new Date().toISOString() } };
}

// TODO: POST /api/quote/inquiries/:id/preview
export async function previewQuote(inquiryId) {
  await delay(400);
  const text = buildPreviewText();
  return { code: 0, data: { text, items: DB.quoteItems, summary: DB.summary } };
}

// 预览话术生成（纯函数，与后端逻辑同构）
function buildPreviewText() {
  const v = DB.vehicle;
  const s = DB.summary;
  const lines = [
    `【${v.brand} ${v.model} ${v.yearPattern}】配件报价`,
    `VIN: ${v.vin}`,
    '',
    ...DB.quoteItems.map(it =>
      `· ${it.brand} ${it.spec} — OE ${it.oe}\n  报价 ¥${it.salePrice}${it.warranty ? ` (${it.warranty})` : ''}`
    ),
    '',
    `——— 合计 ———`,
    `明细 ${DB.quoteItems.length} 项`,
    `小计 ¥${s.subtotal.toFixed(2)}`,
    `税费 ¥${s.taxTotal.toFixed(2)}`,
    s.discount > 0 ? `优惠 -¥${s.discount.toFixed(2)}` : '',
    `最终报价：¥${s.finalPrice.toFixed(2)}`,
    '',
    `报价有效期至 ${s.expiryDate}，下单请尽早确认~`
  ].filter(Boolean);
  return lines.join('\n');
}
