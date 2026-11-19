"""报价计算编排（阶段 4）：pending 询价 → 译码 → OE → 产品价 → 客户等级系数 → 话术。

链路（docs/auto-quote-plan.md 阶段 4；字段名以 docs/quick-quote-api-test.md 实测为准）：
  1. car：有 VIN → vininfo（真实字段 carModelName/fuelType/saleModelName 映射契约 A car 子集）
  2. OE：AI 提取的 oem_no 优先；否则 VIN+配件名走 partno 按名译码（oeCodeTrim，可带 A 前缀）
  3. 产品：OE → product_list（data.data 首行归一成契约 A product；no_exist_oe/空行 = 无档案）
  4. 系数：contact_remark_config.level（群看群/单聊看用户）→ quote_config.price_map
  5. 话术：模板含 OE / 品牌比价行 / 系数后报价 / 4S 对照（多件换行分隔逐件成块）
  6. price_json 回写 QuoteInquiry = 契约 A r 结构（car/product/partImagesList）+ pricing 块

失败语义（契约 B 未尽的兜底，宁进人工不发错价）：
  - 服务方网络/上游异常（QuoteApiError）→ 保持 pending，price_json 记 error 可重算
  - 有件名但译不出 OE / 查无产品档案 → 转 review，price_json 记 error 人工跟进
  - 只有 VIN 无件名（车型卡场景）→ 正常出 car 卡，product 为 null，保持 pending
  - 爆炸图 partImagesList V1 不拉（真实数据上游 502 不稳定，契约 A 可选项）
"""
import logging
import re

from backend import qq_client
from backend.api.quote_config import merged_config
from backend.extensions import db
from backend.models.contact_remark_config import ContactRemarkConfig
from backend.models.conversation import Conversation
from backend.models.quote_inquiry import QuoteInquiry

log = logging.getLogger(__name__)

# 年款/排量无独立字段，从 saleModelName 抽取（实测样例「…2021 2.0T 手自一体…」）
_YEAR_RE = re.compile(r"(?:19|20)\d{2}")
_DISP_RE = re.compile(r"\d\.\d\s?[TtLl]")


# ---------- 编排入口 ----------


def price_inquiries(rows):
    """批量报价（阶段 2 分流后调用）：逐条计算并回写，单条失败不影响其余。"""
    for row in rows:
        try:
            price_inquiry(row)
        except Exception:  # noqa: BLE001 编排失败不拖垮分析流程
            log.exception("询价报价失败 inquiry=%s", row.id)
    db.session.commit()


def price_inquiry(row):
    """单条询价计算报价并回写 price_json（调用方需持有 app_context）。

    幂等：非 pending（已人工/已拦截/已发送）不重算。
    """
    if row.status != QuoteInquiry.ST_PENDING:
        return row
    conv = Conversation.query.filter_by(id=row.conversation_id, deleted_at=None).first()
    if conv is None:
        return row

    level, rate = _customer_rate(conv)
    ctx = {"level": level, "rate": rate, "car": None, "items": [], "error": None}
    interrupted = False
    try:
        ctx["car"] = _car_block(row.vin)
        ctx["items"] = [_price_item(item, rate) for item in _resolve_items(row)]
    except qq_client.QuoteApiError as exc:
        interrupted = True
        ctx["error"] = str(exc)

    if interrupted:
        # 服务方异常：保持 pending 可重算，已拿到的部分照样带上
        row.price_json = _assemble(ctx, row)
        return row

    has_demand = bool(_split_lines(row.part_name) or _split_lines(row.oem_no))
    if not ctx["items"]:
        if has_demand:
            # 有件名但定不了 OE（缺 VIN 或译码无结果）→ 人工补
            ctx["error"] = "无法解析 OE（缺 VIN 或译码无结果），转人工"
            row.status = QuoteInquiry.ST_REVIEW
        row.price_json = _assemble(ctx, row)  # 纯 VIN 也落车型卡（car 有值、无价格区）
        return row
    if all(item["product"] is None for item in ctx["items"]):
        ctx["error"] = "产品库查无此件，转人工"
        row.status = QuoteInquiry.ST_REVIEW
        row.price_json = _assemble(ctx, row)
        return row

    row.price_json = _assemble(ctx, row)
    log.info("询价报价完成 inquiry=%s 件数=%d 首件价=%s", row.id, len(ctx["items"]),
             ctx["items"][0]["final_price"])
    return row


def rebuild_quote_text(row, price=None):
    """人工发送前改价 → 话术联动重建（改价=发送前手动改价，price_json 记改后价）。

    price 有值且首件有报价时：替换首件 final_price（两位小数）、联动重算 4S 节省
    百分比，重生成话术并回写 price_json；无件可价（纯车型卡/异常卡）或改价缺省、
    非法时原样返回已存话术。
    """
    r = row.price_json or {}
    pricing = dict(r.get("pricing") or {})
    stored = (pricing.get("text") or "").strip()
    if price is None:
        return stored
    items = list(pricing.get("items") or [])
    if not items:
        return stored
    try:
        final = f"{float(price):.2f}"
    except (TypeError, ValueError):
        return stored
    first = dict(items[0])
    first["final_price"] = final
    try:
        store = float(first.get("store_price") or 0)
        if store > 0:
            first["save_percent"] = max(0, round((1 - float(final) / store) * 100))
    except (TypeError, ValueError):
        pass
    pricing["items"] = [first] + items[1:]
    pricing["final_price"] = final
    pricing["text"] = _quote_text(row, r.get("car"), pricing["items"])
    row.price_json = {**r, "pricing": pricing}
    return pricing["text"]


# ---------- 链路各段 ----------


def _customer_rate(conv):
    """客户等级 → 系数：群会话看群行、单聊看用户行（与资格判定同口径），无行默认普通。"""
    scope = "group" if conv.chat_type == Conversation.CHAT_GROUP else "user"
    row = ContactRemarkConfig.query.filter_by(
        scope_type=scope, target_wxid=conv.wxid, deleted_at=None,
    ).first()
    level = (row.level if row else None) or ContactRemarkConfig.LEVEL_NORMAL
    price_map = merged_config(0)["price_map"]
    try:
        rate = float(price_map.get(level) or price_map[ContactRemarkConfig.LEVEL_NORMAL])
    except (TypeError, ValueError):
        rate = float(price_map[ContactRemarkConfig.LEVEL_NORMAL])
    if not 0 < rate <= 1:
        rate = float(price_map[ContactRemarkConfig.LEVEL_NORMAL])
    return level, rate


def _car_block(vin):
    """VIN → 契约 A car 子集（vininfo 真实字段映射）。查无此车 / 无 VIN 返回 None。"""
    vin = (vin or "").strip()
    if not vin:
        return None
    data = qq_client.vininfo(vin)
    rows = data if isinstance(data, list) else []
    info = rows[0] if rows and isinstance(rows[0], dict) else {}
    return _car_from_info(info, vin)


def _car_from_info(info, vin=""):
    """vininfo 单行 → 契约 A car 子集；carBrandCode 供爆炸图 carBrandId 取值（手动查询用）。"""
    if not (info.get("carBrandName") or info.get("carModelName")):
        return None
    sale = info.get("saleModelName") or ""
    year = _YEAR_RE.search(sale)
    disp = _DISP_RE.search(sale)
    return {
        "vin": info.get("vin") or vin,
        "brandName": info.get("carBrandName") or "",
        "model": info.get("carModelName") or "",
        "yearPattern": year.group(0) if year else "",
        "displacement": disp.group(0).replace(" ", "").upper() if disp else "",
        "fuel": info.get("fuelType") or "",
        "saleModelName": sale,
        "carBrandCode": info.get("carBrandCode") or "",
    }


def _split_lines(value):
    """多件原文拆分：part_name/oem_no 一一对应换行分隔（实测行为）。"""
    return [t.strip() for t in (value or "").split("\n") if t.strip()]


def _decode_oe(vin, part):
    """VIN+配件名 → 标准 OE（partno 按名译码，实测接受名称）。译不出返回空串。"""
    data = qq_client.partno(vin, part)
    rows = data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
    info = rows[0] if rows and isinstance(rows[0], dict) else {}
    # oeCode 带空格（"11 53 8 635 689"）、译码输出可能补 A 前缀——
    # product_list 接受 OE/store/PARTENT 且服务侧归一化，原样传即可，只去空格
    return (info.get("oeCodeTrim") or info.get("oeCode") or "").replace(" ", "").strip()


def _resolve_items(row):
    """询价行 → 待价件列表 [{part, oe}]。OE 优先用 AI 提取值，缺了按名译码。

    多件换行分隔；无法定 OE 的件跳过（全部跳过时由调用方转人工）。
    """
    parts = _split_lines(row.part_name)
    oems = _split_lines(row.oem_no)
    items = []
    for i, part in enumerate(parts):
        oe = oems[i] if i < len(oems) else ""
        if not oe and row.vin:
            oe = _decode_oe(row.vin.strip(), part)
        if oe:
            items.append({"part": part, "oe": oe})
    if not items and oems:  # AI 只提取了编号没给件名
        items = [{"part": oe, "oe": oe} for oe in oems]
    return items


def _price_item(item, rate):
    """件 → 报价行：OE 查产品档案 → 系数价。查无档案 product=None。"""
    data = qq_client.product_list(item["oe"])
    product = _norm_product(_first_product(data, item["oe"]))
    cost = final = store = None
    if product and product["cost_price"]:
        try:
            cost = float(product["cost_price"])
            store = float(product["store_price"] or 0)
            final = f"{cost * rate:.2f}"
        except (TypeError, ValueError):
            cost = final = None
    save = max(0, round((1 - cost * rate / store) * 100)) if (cost and final and store > 0) else None
    return {
        **item,
        "product": product,
        "cost_price": f"{cost:.2f}" if cost is not None else "",
        "store_price": f"{store:.2f}" if store else "",
        "final_price": final,
        "save_percent": save,
    }


def _product_rows(data):
    """product_list data → (产品行列表, 未命中回显)。

    实测三层信封（同 purchaseHistory）：data = {status, msg, data:{分页器}}，
    产品行在 data.data.data、no_exist_oe 在分页器层；文档「data.data 直接是行列表」有误。
    兼容 PHP 数字键对象化漂移（{"0": 行, ...}）与无内层信封形态。
    """
    if not isinstance(data, dict):
        return [], []
    payload = data.get("data")
    if not isinstance(payload, dict):
        rows = payload if isinstance(payload, list) else []
        return rows, [str(x) for x in (data.get("no_exist_oe") or [])]
    rows = payload.get("data")
    if isinstance(rows, dict):  # PHP 数组数字键被序列化成对象
        rows = list(rows.values())
    rows = rows if isinstance(rows, list) else []
    return rows, [str(x) for x in (payload.get("no_exist_oe") or [])]


def _first_product(data, oe):
    """product_list data → 首个产品组行；查无档案返回 None。

    实测（2026-11-17 真链路验证）：组行只有 {no, child:[品牌行]} 两个键，
    名称/价格/图/编号全挂在品牌行上（文档「父行含产品字段」系 mock 时代误记）。
    """
    rows, missing = _product_rows(data)
    key = re.sub(r"^[A-Za-z]+", "", str(oe))  # 服务侧回显剥离前缀字母
    if key and key in missing:
        return None
    for row in rows:
        if isinstance(row, dict) and any(isinstance(c, dict) for c in row.get("child") or []):
            return row
    return None  # 空行 / 占位行（无品牌行）


def _norm_product(row):
    """产品组行 → 契约 A product 稳定结构（真实字段名归一，前端只认契约键）。

    契约 A product 取首个品牌行为主行（原型「首行高亮推荐」同款），
    其余品牌行归一进 child 表（前端比价区）；图用 bigpic（实测真实图片 URL，
    服务方图片域 data.gzbbr.com——前置确认①产品图来源即此字段）。
    """
    if row is None:
        return None
    brand_rows = [c for c in (row.get("child") or []) if isinstance(c, dict)]
    if not brand_rows:
        return None
    main = brand_rows[0]
    nums = {
        str(i.get("key") or "").lower(): (i.get("number") or "")
        for i in (main.get("display_number") or []) if isinstance(i, dict)
    }
    child = []
    for c in brand_rows[:10]:
        try:
            stock = int(c.get("stock") if c.get("stock") is not None else 0)
        except (TypeError, ValueError):
            stock = 0
        child.append({
            "brand_name": c.get("brand_name") or "",
            "cost_price": str(c.get("cost_price") or ""),
            "store_price": str(c.get("store_price") or ""),
            "stock": stock,
        })
    return {
        "product_id": main.get("product_id"),
        "store_number": nums.get("store") or "",
        "partent_number": nums.get("partent") or "",
        "display_number": {"key": "OE", "value": nums.get("oe") or ""},
        "product_name": main.get("name") or main.get("l_name_zh") or main.get("l_name_zh_default") or "",
        "brand_name": main.get("brand_name") or "",
        "cost_price": str(main.get("cost_price") or ""),
        "store_price": str(main.get("store_price") or ""),
        "image": main.get("bigpic") or main.get("first_image_url") or main.get("pic") or "",
        "sell_point": main.get("l_model_zh") or "",
        "child": child,
    }


# ---------- 结果组装 ----------


def _assemble(ctx, row):
    """计算上下文 → 契约 A r 结构 + pricing 块（price_json 落库形态）。"""
    items = ctx["items"]
    first = next((it for it in items if it["product"]), None)
    return {
        "car": ctx["car"],
        "product": first["product"] if first else None,
        "partImagesList": None,  # V1 不拉爆炸图（上游 502 不稳定）
        "pricing": {
            "level": ctx["level"],
            "rate": ctx["rate"],
            "final_price": first["final_price"] if first else None,
            "items": items,
            "text": _quote_text(row, ctx["car"], items),
        },
        "error": ctx["error"],
    }


_QUOTE_LINK_PREFIX = "https://jh.fsbbr.net/wx_quotation?id="
_QUOTE_LINK_TOKEN = "J9MMjulKQKtVqTtt"  # 占位 token：真实报价单页接入前统一使用


def _resolve_real_name(sender_name, conv):
    """V2：优先用真实名称/备注，不直接用 wxid。

    查找优先级：
      1. sender_name 有值且不是 wxid → 直接用（AI 提取的昵称/姓名就是真实名）
      2. 单聊 → Contact 表按 conv.wxid 查 name/备注
      3. 群聊 sender_name 是 wxid → Contact 查
      4. 兜底 conv.name → "客户"
    """
    from backend.models.contact import Contact

    sn = (sender_name or "").strip()

    # 1. AI 提取的 sender_name 本身就是昵称/姓名（不是 wxid_ 开头），直接用
    if sn and not sn.startswith("wxid_"):
        return sn

    # 2. 单聊：用 conv.wxid 查对方真实名/备注
    if conv and conv.chat_type == Conversation.CHAT_SINGLE and conv.wxid:
        c = Contact.query.filter(Contact.wxid == conv.wxid, Contact.deleted_at.is_(None)).first()
        if c and c.name:
            return c.name.strip()

    # 3. sender_name 是 wxid，Contact 查
    if sn.startswith("wxid_"):
        c = Contact.query.filter(Contact.wxid == sn, Contact.deleted_at.is_(None)).first()
        if c and c.name:
            return c.name.strip()

    # 4. 兜底
    if conv and conv.name:
        return conv.name.strip()
    return sn or "客户"


def _fmt_price(p):
    """格式化价格：空/0 → 不显示，非数字 → 原值，否则 ¥N。"""
    if p is None or p == "":
        return None
    try:
        v = float(p)
    except (TypeError, ValueError):
        return str(p) or None
    if v <= 0:
        return None
    return f"¥{v:.0f}"


def _quote_text(row, car, items):
    """话术模板（2026-11-19 V2）：
    @真实名称 + VIN + 车型 + 分隔线 + ★n 配件(OE) + 品牌比价行 + 选购链接。

    - @ 优先查 Contact 表真实名称/备注，不用 wxid
    - 品牌比价行取 child 里有价格的条目，最多显示 10 个
    - 查无产品的件不进话术，人工跟进
    """
    blocks = []
    priced = [it for it in items if it["product"]]
    has_car = bool(car and (car["brandName"] or car["model"]))
    if not priced and not has_car:
        return ""  # 无车型无产品：没有可发内容（转人工场景）
    conv = db.session.get(Conversation, row.conversation_id)
    who = _resolve_real_name(row.sender_name, conv)
    blocks.append(f"@{who}")
    if row.vin:
        blocks.append(row.vin)
    if has_car:
        if car.get("saleModelName"):
            head = " ".join(t for t in (car["brandName"], car["saleModelName"]) if t)
        else:
            head = " ".join(t for t in (car["brandName"], car["model"]) if t)
            if car["yearPattern"]:
                head += f" {car['yearPattern']}款"
            if car["displacement"]:
                head += f" {car['displacement']}"
        blocks.append(head)
    if priced:
        blocks.append("—" * 10)
        for n, it in enumerate(priced, 1):
            p = it["product"]
            name = p["product_name"] or it["part"]
            oe = it.get("oe") or ""
            blocks.append(f"★{n}、{name} ({oe})")
            # 品牌比价行（最多 10 个，有价格才显示）
            child = p.get("child") or []
            shown = 0
            circles = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩"]
            for c in child[:20]:
                brand = (c.get("brand_name") or "").strip()
                price = _fmt_price(c.get("store_price"))
                if not brand or not price:
                    continue
                blocks.append(f"  {circles[shown]} {brand} {price}")
                shown += 1
                if shown >= 10:
                    break
        blocks.append("")
        blocks.append("选购链接：")
        blocks.append(_QUOTE_LINK_PREFIX + _QUOTE_LINK_TOKEN)
    return "\n".join(blocks)
