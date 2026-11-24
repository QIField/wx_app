"""快捷报价查询代理 API（拓展栏重做 · 手动报价视图的上游查询出口）。

上游能力 backend/qq_client.py 已封装（docs/quick-quote-api.md 实测契约），
本层只做：登录鉴权 → 参数校验 → 编排/透传 → 统一错误映射（_query_endpoint：
缺参 400 / 编排失败与上游异常 502）。查询类无副作用不落库。爆炸图上游实测
不稳定（quick-quote-api-test.md §4.13：真实数据场景静默空返回），失败降级为
partImagesList=None 不拖垮整体结果。

- POST /api/quote/query/manual-search   {q, part_name?} → r 结构 + chain 步骤名
- POST /api/quote/query/extract-parts   {text} → AI 询价要素提取
- POST /api/quote/query/zpy | jqr       {number} → 第三方比价透传
- POST /api/quote/query/purchase-history {number, page?, limit?} → 采购历史
"""
import re
from functools import wraps

from flask import Blueprint, jsonify, request

from backend import qq_client
from backend.services import quote_pricing as pricing  # 复用报价链归一化，r 结构与询价卡一致
from backend.services.auth import require_role
from backend.services.text_utils import normalize_spaced_digits

bp = Blueprint("quote_query", __name__)

# 与原型 view-manual.js detectType 同款：VIN 17 位（去 I/O/Q）、OE 前缀 ≤3 字母 + 6~12 数字
_VIN_RE = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")
_OE_RE = re.compile(r"^[A-Z]{0,3}\d{6,12}$", re.I)

# 名称查询无 VIN 时的兜底车型（原型同款：宝马 X3 试车 VIN）
DEFAULT_VIN = "WBAWX3100G0L69597"


class _QueryError(Exception):
    """manual-search 编排失败（消息含步骤名与原因），端点层统一转 502。"""


class _MissingParam(Exception):
    """必填参数缺失（消息含参数名），端点层统一转 400。"""


def _query_endpoint(fn):
    """端点统一错误映射：缺参 → 400，编排失败 / 上游异常 → 502。"""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except _MissingParam as exc:
            return jsonify(code=400, msg=str(exc)), 400
        except (_QueryError, qq_client.QuoteApiError) as exc:
            return jsonify(code=502, msg=str(exc)), 502

    return wrapper


def _detect_type(q):
    """识别查询字符串类型：vin / oe / name。

    对空格做归一化：用户可能输入 "11 53 8 635 689" 这种带空格的 OE 号，
    先合并为 "11538635689" 再用正则匹配。
    VIN 本身不会被空格分隔（工业标准 17 位连续字符），但也一并归一化以防万一。
    """
    q_norm = normalize_spaced_digits(q or "")
    if _VIN_RE.match(q_norm):
        return "vin"
    if _OE_RE.match(q_norm):
        return "oe"
    return "name"


def _json_body():
    return request.get_json(silent=True) or {}


def _require(body, key):
    """必填字符串字段：去空格后非空，空值抛 _MissingParam（装饰器统一转 400）。"""
    value = str(body.get(key) or "").strip()
    if not value:
        raise _MissingParam(f"{key} 不能为空")
    return value


def _vininfo_row(vin):
    """vininfo data → 首行车（未命中返回空 dict）。"""
    data = qq_client.vininfo(vin)
    rows = data if isinstance(data, list) else []
    return rows[0] if rows and isinstance(rows[0], dict) else {}


def _car_of(vin):
    """VIN → 契约 A car（未命中抛错，语义同原型「查无此车」）。"""
    car = pricing._car_from_info(_vininfo_row(vin), vin)
    if car is None:
        raise _QueryError("VIN 未命中车型档案（按「查无此车」处理）")
    return car


def _oe_of(vin, part_name, chain):
    """配件名 → OE 译码（partno 实测接受名称）；译不出抛错。"""
    oe = pricing._decode_oe(vin, part_name)
    if not oe:
        raise _QueryError(f"「{part_name}」名称译码失败（字段空串=无档案）")
    chain.append("OE译码")
    return oe


def _product_of(oe, chain):
    """OE → 契约 A product；查无档案抛错（带 no_exist_oe 回显）。"""
    data = qq_client.product_list(oe)
    product = pricing._norm_product(pricing._first_product(data, oe))
    if product is None:
        _, missing = pricing._product_rows(data)
        raise _QueryError(f"OE 未命中产品档案：no_exist_oe={missing or [oe]}")
    chain.append("产品档案")
    return product


def _explosion_of(vin, oe, brand_code):
    """爆炸图+周边配件（上游实测不稳定：失败/空返回一律降级 None，不影响主结果）。"""
    try:
        pi = qq_client.part_images(vin, oe)
        rows = pi if isinstance(pi, list) else []
        image_id = rows[0].get("imageId") if rows and isinstance(rows[0], dict) else ""
        if not image_id:
            return None
        data = qq_client.part_images_list(vin, image_id, oe, brand_code)
        return data if isinstance(data, list) and data else None
    except qq_client.QuoteApiError:
        return None


def _search(q, part_name):
    """manual-search 编排（流程图 2）：按类型走链式查询 → r 结构。"""
    qtype = _detect_type(q)
    chain, car, product, oe = [], None, None, ""
    if qtype == "vin":
        chain.append("VIN译码")
        car = _car_of(q)
        if part_name:
            oe = _oe_of(q, part_name, chain)
            product = _product_of(oe, chain)
    elif qtype == "oe":
        chain.append("OE直查")
        oe = q
        product = _product_of(q, chain)
    else:
        chain.append("OE译码")
        oe = _oe_of(DEFAULT_VIN, q, chain)
        chain.append("兜底车型")
        car = pricing._car_from_info(_vininfo_row(DEFAULT_VIN), DEFAULT_VIN)
        product = _product_of(oe, chain)

    images = None
    if car and product:
        images = _explosion_of(car["vin"], oe, car.get("carBrandCode") or "")
    return {
        "type": qtype, "car": car, "product": product,
        "partImagesList": images, "chain": chain,
    }


# ---------- 端点 ----------


@bp.post("/api/quote/query/manual-search")
@require_role()
@_query_endpoint
def manual_search():
    """链式查询：VIN/OE/配件名 → r 结构（车线/产品卡/爆炸图），前端 QuoteResultCard 消费。"""
    body = _json_body()
    q = _require(body, "q")
    return jsonify(code=0, msg="success",
                   data=_search(q, str(body.get("part_name") or "").strip()))


@bp.post("/api/quote/query/extract-parts")
@require_role()
@_query_endpoint
def extract_parts():
    """AI 对话子 tab：单条文本 → 询价要素提取（chat_content 契约组装）。"""
    text = _require(_json_body(), "text")
    return jsonify(code=0, msg="success",
                   data=qq_client.extract_parts([{"type": "input_text", "text": text}]))


@bp.post("/api/quote/query/ocr-vin")
@require_role()
@_query_endpoint
def ocr_vin():
    """图片 → VIN 识别：上传后拿到的绝对 url 传给腾讯云 OCR，返回识别到的 VIN 字符串。"""
    image_url = _require(_json_body(), "image_url")
    vin = qq_client.ocr_vin(image_url)
    if not vin:
        raise _QueryError("图片识别未返回 VIN")
    return jsonify(code=0, msg="success", data={"vin": vin})


@bp.post("/api/quote/query/zpy")
@require_role()
@_query_endpoint
def zpy_query():
    """兆配云全网比价（中文键名原样透传，前端统一 String 化展示）。"""
    return jsonify(code=0, msg="success", data=qq_client.zpy(_require(_json_body(), "number")))


@bp.post("/api/quote/query/jqr")
@require_role()
@_query_endpoint
def jqr_query():
    """机汽人平台竞价查询（jy_data/xj_data 原样透传）。"""
    return jsonify(code=0, msg="success", data=qq_client.jqr(_require(_json_body(), "number")))


@bp.post("/api/quote/query/purchase-history")
@require_role()
@_query_endpoint
def purchase_history():
    """采购历史（三层嵌套 {total, list} 原样透传，前端展示汇总与分页）。"""
    body = _json_body()
    number = _require(body, "number")
    try:
        page = int(body.get("page") or 1)
        # limit 前端不传 → 用 qq_client 的默认 9999（一次拉全）；传了就尊重
        raw_limit = body.get("limit")
        limit = int(raw_limit) if raw_limit is not None else None
        if limit is not None and limit < 1:
            raise _MissingParam("limit 必须 ≥ 1")
    except (TypeError, ValueError):
        raise _MissingParam("page/limit 必须是整数") from None
    kwargs = {"page": page}
    if limit is not None:
        kwargs["limit"] = limit
    return jsonify(
        code=0, msg="success",
        data=qq_client.purchase_history(number, **kwargs),
    )
