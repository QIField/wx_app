/* ===== 快捷报价 · 接口层 =====
   端点、传参与响应结构 100% 对齐 docs/quick-quote-api.md（实测版）
   MOCK=true 时走本地同构数据；置 false 即按真实契约直连服务（联调用）。 */

const QQ_BASE_URL = 'http://wx_api.fsbbr.net/wechat_x';
const QQ_OPENID = '5A8D08A1A292061C4B52B3E5DF035B53'; // 快捷报价服务专用 openid（与中间方不通用）

/* 端点映射（接口文档《接口总表》全 11 个） */
const QQ_ENDPOINTS = {
  productList:      { path: '/crm_api/product_list',        name: '产品列表' },
  purchaseHistory:  { path: '/crm_api/purchaseHistory_list', name: '采购历史' },
  extractParts:     { path: '/ai_api/extract_parts_demand',  name: '聊天提取配件需求' },
  vininfo:          { path: '/decoding_api/vininfo',         name: 'VIN解析' },
  partno:           { path: '/decoding_api/partno',          name: 'OE译码查询' },
  partImages:       { path: '/decoding_api/partImages',      name: '单个OE爆炸图' },
  partImagesList:   { path: '/decoding_api/partImages_list', name: '爆炸图+周边配件' },
  localVin:         { path: '/ocr_api/local_vin',            name: '本地OCR识别VIN' },
  txVin:            { path: '/ocr_api/tx_vin',               name: '腾讯云OCR识别VIN' },
  jqr:              { path: '/platform_api/jqr',             name: '机汽人平台' },
  zpy:              { path: '/platform_api/zpy',             name: '兆配云平台' },
};

let QQ_MOCK = true; // 顶栏环境徽章可切换

const sleep = ms => new Promise(r => setTimeout(r, ms));

/**
 * 统一调用：POST form（application/x-www-form-urlencoded）
 * 响应契约：{ code, msg, data }；401=openid 缺失/未注册；500=上游异常（非 JSON）
 */
async function qqCall(key, params = {}, { openid = QQ_OPENID, timeout = 90000 } = {}) {
  const ep = QQ_ENDPOINTS[key];
  if (!ep) throw new Error(`未知端点: ${key}`);

  if (QQ_MOCK) {
    await sleep(280 + Math.random() * 620); // 模拟网络延迟
    return window.QQMock.resolve(key, params);
  }

  const body = new URLSearchParams({ openid, ...params });
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeout);
  let res;
  try {
    res = await fetch(QQ_BASE_URL + ep.path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: body.toString(),
      signal: ctrl.signal,
    });
  } catch (e) {
    throw new Error('网络异常/超时（接口文档：仅 HTTP 可用）');
  } finally {
    clearTimeout(timer);
  }

  const ct = res.headers.get('Content-Type') || '';
  if (!ct.includes('application/json')) {
    // 实测：上游异常返回 Flask HTML 错误页（非 JSON）
    throw new Error(`${ep.name}：HTTP ${res.status}（服务端异常，非 JSON 返回）`);
  }
  const json = await res.json();
  if (res.status === 401) throw new Error(json.msg || 'openid 不存在或已关闭');
  if (json.code !== 0) throw new Error(json.msg || `code=${json.code}`);
  return json.data;
}

window.qqCall = qqCall;
window.QQ_BASE_URL = QQ_BASE_URL;
window.QQ_ENDPOINTS = QQ_ENDPOINTS;
window.QQ_OPENID = QQ_OPENID;
window.QQSetMock = v => { QQ_MOCK = v; };
window.QQIsMock = () => QQ_MOCK;
