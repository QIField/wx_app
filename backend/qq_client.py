"""快捷报价服务客户端（对接契约 docs/quick-quote-api.md，2026-11-17 实测版）。

- 全部 POST + application/x-www-form-urlencoded（服务不支持 JSON body）
- openid 服务方独立签发，与中间方设备 openid 不通用，配置 .env QQ_OPENID
- 统一返回 {code,msg,data}：code=0 成功；401=openid 缺失/未注册/已关闭
- 上游异常返回 500 Flask HTML（非 JSON）——统一兜底成 QuoteApiError，调用方只管捕获
"""
import json

import requests

from backend.config import QQ_API_BASE_URL, QQ_OPENID, QQ_TIMEOUT_SECONDS

# 端点表：键名与前端原型 prototypes/quick-quote-panel/js/api.js 保持一致
ENDPOINTS = {
    "productList": "crm_api/product_list",
    "purchaseHistory": "crm_api/purchaseHistory_list",
    "vininfo": "decoding_api/vininfo",
    "partno": "decoding_api/partno",
    "partImages": "decoding_api/partImages",
    "partImagesList": "decoding_api/partImages_list",
    "extractParts": "ai_api/extract_parts_demand",
    "localVin": "ocr_api/local_vin",
    "txVin": "ocr_api/tx_vin",
    "zpy": "platform_api/zpy",
    "jqr": "platform_api/jqr",
}


class QuoteApiError(Exception):
    """快捷报价调用失败（未配置 openid / 鉴权失败 / 上游异常 / 非 JSON / 超时）。"""


def _build_form(params, openid):
    """业务参数过滤 None 后注入 openid（服务端只认 form 字段）。"""
    if not openid:
        raise QuoteApiError("未配置快捷报价 openid（.env QQ_OPENID）")
    form = {k: v for k, v in (params or {}).items() if v is not None}
    form["openid"] = openid
    return form


def call(key, params=None, *, timeout=None, openid=None):
    """统一调用入口：POST form → 校验 code → 返回 data（结构契约见文档各接口详规）。

    - key 见 ENDPOINTS；params 只传业务参数，openid 自动注入
    - 任何失败抛 QuoteApiError，成功返回 data（list / dict / str 三种形态按接口不同）
    """
    endpoint = ENDPOINTS.get(key)
    if endpoint is None:
        raise QuoteApiError(f"未知快捷报价端点：{key}")
    url = QQ_API_BASE_URL.rstrip("/") + "/" + endpoint
    form = _build_form(params, openid or QQ_OPENID)
    seconds = timeout or QQ_TIMEOUT_SECONDS
    try:
        resp = requests.post(url, data=form, timeout=seconds)
    except requests.Timeout:
        raise QuoteApiError(f"快捷报价服务超时（{seconds}s）：{key}") from None
    except requests.RequestException as exc:
        raise QuoteApiError(f"快捷报价服务不可达：{exc}") from None

    if resp.status_code == 401:
        try:
            msg = resp.json().get("msg") or "鉴权失败"
        except ValueError:
            msg = "鉴权失败"
        raise QuoteApiError(f"快捷报价鉴权失败：{msg}")
    if resp.status_code >= 500:
        # 实测：上游异常返回 Flask HTML 错误页，统一兜底
        raise QuoteApiError(f"快捷报价服务异常（HTTP {resp.status_code}）：{key}")
    try:
        body = resp.json()
    except ValueError:
        raise QuoteApiError(f"快捷报价服务返回非 JSON（HTTP {resp.status_code}）：{key}") from None
    if not isinstance(body, dict) or body.get("code") != 0:
        msg = body.get("msg") if isinstance(body, dict) else None
        raise QuoteApiError(f"快捷报价业务失败：{msg or '未知错误'}")
    return body.get("data")


# ---------- 便捷包装（阶段 2+ 编排层调用；参数名对齐文档各接口详规） ----------


def vininfo(vin):
    """VIN → 车型译码（品牌/车系/年款/排量/油品）。"""
    return call("vininfo", {"vin": vin})


def product_list(number):
    """OE / store 号（A+OE）/ PARTENT 号 → 产品档案（含品牌比价 child）。"""
    return call("productList", {"number": number})


def purchase_history(number, page=1, limit=5):
    """OE → 采购历史（三层嵌套：data.data.{total, list}）。"""
    return call("purchaseHistory", {"number": number, "page": page, "limit": limit})


def partno(vin, original_parts_nos):
    """VIN+配件名称（或直接 OE）→ OE 编号；originalPartsNos 实测可传配件名。"""
    return call("partno", {"vin": vin, "originalPartsNos": original_parts_nos})


def part_images(vin, oe_code):
    """VIN+OE → 爆炸图 imageId。"""
    return call("partImages", {"vin": vin, "oeCode": oe_code})


def part_images_list(vin, image_ids, oe_code, car_brand_id):
    """爆炸图+周边配件表；carBrandId 传 vininfo 的 carBrandCode。"""
    return call("partImagesList", {
        "vin": vin, "imageIds": image_ids, "oeCode": oe_code, "carBrandId": car_brand_id,
    })


def extract_parts(chat_content):
    """聊天记录（list[dict]）→ AI 询价要素提取；chat_content 序列化为 JSON 字符串。

    按服务方接口规定：json.dumps 不带 ensure_ascii=False，中文字符统一用 \\uXXXX 转义。
    """
    return call("extractParts", {"chat_content": json.dumps(chat_content)})


def ocr_vin(image_url, prefer_tx=True):
    """图片 → VIN。腾讯云 OCR 优先（实测 local_vin 失败仅返回空串无错误码）。"""
    return call("txVin" if prefer_tx else "localVin", {"image_url": image_url})


def zpy(number):
    """兆配云全网比价（中文键名，按城市多行）。"""
    return call("zpy", {"number": number})


def jqr(number):
    """机汽人平台竞价查询。"""
    return call("jqr", {"number": number})
