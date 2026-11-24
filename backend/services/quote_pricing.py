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


def price_inquiries(rows, force=False):
    """批量报价（阶段 2 分流后调用）：逐条计算并回写，单条失败不影响其余。"""
    for row in rows:
        try:
            price_inquiry(row, force=force)
        except Exception:  # noqa: BLE001 编排失败不拖垮分析流程
            log.exception("询价报价失败 inquiry=%s", row.id)
    db.session.commit()


def recompute_pending():
    """系数/等级变更后：重算所有 pending + review 询价。"""
    rows = QuoteInquiry.query.filter(
        QuoteInquiry.status.in_([QuoteInquiry.ST_PENDING, QuoteInquiry.ST_REVIEW]),
    ).all()
    if not rows:
        return 0
    price_inquiries(rows, force=True)
    log.info("系数/等级变更后重算询价 %d 条", len(rows))
    return len(rows)


def price_inquiry(row, force=False):
    """单条询价计算报价并回写 price_json（调用方需持有 app_context）。

    幂等：非 pending（已人工/已拦截/已发送）不重算，除非 force=True（系数/等级变更后）。
    """
    if not force and row.status != QuoteInquiry.ST_PENDING:
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
    # ★ 同步更新首产品的首品牌 child sell_price/sell_price_fmt
    # （_quote_text 现已从 brand-level 读价，不是 item-level）
    product = first.get("product")
    if product:
        children = list(product.get("child") or [])
        if children:
            c0 = dict(children[0])
            c0["sell_price"] = final
            try:
                c0["sell_price_fmt"] = f"¥{float(final):.0f}" if float(final) > 0 else ""
            except (TypeError, ValueError):
                c0["sell_price_fmt"] = ""
            children[0] = c0
            product = {**product, "child": children}
            first["product"] = product
    pricing["items"] = [first] + items[1:]
    pricing["final_price"] = final
    pricing["text"] = _quote_text(row, r.get("car"), pricing["items"], pricing.get("level"), pricing.get("rate"))
    row.price_json = {**r, "pricing": pricing}
    return pricing["text"]


def rebuild_quote_text_with_override(row, price=None):
    """重建话术（支持行内改价覆盖）。优先级：
      1. override_pricing（人工详情页行内改价 → 所有配件价都变了）
      2. body.price（QuoteCard 顶栏单卡改价 → 只改首件）
      3. 原始话术（都没改就原样返回）
    """
    ov = row.override_pricing or {}
    ov_items = list(ov.get("items") or [])
    r = row.price_json or {}
    pricing = dict(r.get("pricing") or {})
    stored = (pricing.get("text") or "").strip()

    # 优先级 1：override_pricing 整包覆盖
    if ov_items:
        pitems = list(pricing.get("items") or [])
        if pitems:
            by_oe = {str(x.get("oe") or ""): x for x in ov_items}
            merged_total = 0.0
            new_items = []
            for it in pitems:
                oe = str(it.get("oe") or "")
                if oe in by_oe:
                    new_items.append({**it, "final_price": by_oe[oe]["final_price"]})
                else:
                    new_items.append(dict(it))
                try:
                    merged_total += float(new_items[-1].get("final_price") or 0)
                except (TypeError, ValueError):
                    pass
            pricing["items"] = new_items
            if merged_total > 0:
                pricing["final_price"] = f"{round(merged_total, 2):.2f}"
            pricing["text"] = _quote_text(row, r.get("car"), pricing["items"], pricing.get("level"), pricing.get("rate"))
            row.price_json = {**r, "pricing": pricing}
            return pricing["text"]

    # 优先级 2：body.price（单卡顶栏改价）
    if price is not None:
        return rebuild_quote_text(row, price)

    # 都没改 → 原样返回
    return stored


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
    """VIN → 契约 A car 子集（vininfo 真实字段映射）。查无此车 / 无 VIN / 脏值 'None' 返回 None。"""
    vin = _clean_str(vin)
    if not vin:
        return None
    data = qq_client.vininfo(vin)
    rows = data if isinstance(data, list) else []
    info = rows[0] if rows and isinstance(rows[0], dict) else {}
    return _car_from_info(info, vin)


def _clean_str(val):
    """和 quote_dispatch._clean 同逻辑：把字符串 'None'/'null'/'undefined' 清洗成空串。"""
    if val is None:
        return ""
    if isinstance(val, str):
        v = val.strip()
        if v.lower() in ("none", "null", "undefined", "nan"):
            return ""
        return v
    return str(val).strip()


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
    """多件原文拆分：part_name/oem_no 一一对应，按换行或逗号分隔（两种都支持）。

    AI extract_parts 返回换行分隔，rule_extract 用逗号拼接——两种来源都要吃。
    """
    if not value:
        return []
    # 先换行，再逗号，去掉两端空白和空串
    parts = re.split(r"[\n,，]", str(value))
    return [p.strip() for p in parts if p.strip()]


def _decode_oes(vin, part):
    """VIN+配件名 → 全部匹配的 OE 列表（partno 按名译码可能返回多行：前下摆臂→左+右）。

    返回 list[dict]，每项：
      {oe, oe_name, price4s}   oe 去空格紧凑码，oe_name=partno 的 oeName 语义名（左前下摆臂）
    译不出返回空 list。
    """
    data = qq_client.partno(vin, part)
    rows = data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
    results = []
    for info in rows:
        if not isinstance(info, dict):
            continue
        oe = (info.get("oeCodeTrim") or info.get("oeCode") or "").replace(" ", "").strip()
        if oe:
            results.append({
                "oe": oe,
                "oe_name": info.get("oeName") or "",
                "price4s": info.get("price4s") or "",
            })
    return results


def _decode_oe(vin, part):
    """单 OE 兼容包装（manual-search 编排层仍取首个；自动报价已改走 _decode_oes 展开）。"""
    rows = _decode_oes(vin, part)
    return rows[0]["oe"] if rows else ""


def _resolve_items(row):
    """询价行 → 待价件列表 [{part, oe, oe_name?, price4s?}]。

    多件换行分隔；OE 优先用 AI 提取值（1:1 对应 part_name），
    缺 OE 时走 _decode_oes 按名译码 → partno 返回几个 OE 就展开成几条 item
    （例：前下摆臂 → 左A1643303407 + 右A1643303507 两条独立报价）。

    译码失败也要产出占位 item（oe="0"），确保话术里能列出 ★标题
    （Block B 里 ★3、前分动箱 (0) 这种形态）。
    全部 item 都译不出 OE/查无档案时由调用方转人工。
    """
    parts = _split_lines(row.part_name)
    oems = _split_lines(row.oem_no)
    items = []
    for i, part in enumerate(parts):
        oe_direct = oems[i] if i < len(oems) else ""
        if oe_direct:
            # AI 已给 OE → 直接用（不展开，避免 partno 二次调用）
            items.append({"part": part, "oe": oe_direct})
        elif row.vin:
            decoded = _decode_oes(row.vin.strip(), part)
            if decoded:
                for d in decoded:
                    items.append({
                        "part": part,
                        "oe": d["oe"],
                        "oe_name": d["oe_name"],
                        "price4s": d["price4s"],
                    })
            else:
                # partno 译码失败 → 占位 item，oe="0"，确保话术里能出 ★标题
                items.append({"part": part, "oe": "0"})
        else:
            # 无 VIN → 占位 item
            items.append({"part": part, "oe": "0"})
    if not items and oems:  # AI 只提取了编号没给件名
        items = [{"part": oe, "oe": oe} for oe in oems]
    return items


def _kaisi_price_of(child):
    """child 品牌行 → 开思价 float；空/非法/0 → None。

    _norm_product 已归一 retail_price 取值链为 price → store_cass_price → 空。
    """
    try:
        f = float(child.get("retail_price") or 0)
    except (TypeError, ValueError):
        return None
    return f if f > 0 else None


def _price_item(item, rate):
    """件 → 报价行：OE 查产品档案 → 系数价。查无档案 product=None。

    每条品牌行（child）现在带：
      - retail_price / retail_price_fmt  — 开思价（优先 price，降级 store_cass_price）
      - sell_price  / sell_price_fmt    — retail_price × rate 我方实际报价
      - image                            — 每个品牌自己的产品图
      - product_name / oe / partent_number — 品牌级完整信息
    顶层 final_price 取首个有有效开思价的 child（兼容旧字段）。

    开思价缺失 → sell_price 也空，话术模板按 sell_price_fmt 自动过滤这条不报。
    """
    data = qq_client.product_list(item["oe"])
    product = _norm_product(_first_product(data, item["oe"]))

    # 逐品牌计算我方报价（开思价 × rate）
    if product:
        for c in product.get("child") or []:
            kaisi = _kaisi_price_of(c)
            sell_f = kaisi * rate if kaisi else None
            c["sell_price"] = f"{sell_f:.2f}" if sell_f is not None else ""
            c["sell_price_fmt"] = f"¥{sell_f:.0f}" if sell_f and sell_f > 0 else ""
            c["retail_price_fmt"] = f"¥{kaisi:.0f}" if kaisi else ""
        # OE 一致性校验：「原厂」「原厂国内4S件」各自独立对比接口返回 oe vs 询价原始 oe
        _mark_oe_consistency(product, item.get("oe") or "")

    # 顶层 final_price + save_percent（取首个有有效开思价的 child）
    final = store = None
    if product:
        for fc in product.get("child") or []:
            kaisi = _kaisi_price_of(fc)
            if kaisi:
                final = f"{kaisi * rate:.2f}"
                try:
                    store = float(fc.get("store_price") or 0) or None
                except (TypeError, ValueError):
                    store = None
                break
    final_val = float(final) if final else None
    save = (max(0, round((1 - final_val / store) * 100))
            if (final_val and store and store > 0) else None)

    # 顶层保留 cost_price / store_price（契约兼容，取首 child 原值）
    head = (product.get("child") or [None])[0] if product else None
    top_cost = f"{float(head['cost_price']):.2f}" if head and head.get("cost_price") else ""
    top_store = f"{store:.2f}" if store else ""

    return {
        **item,  # 含 oe_name / price4s（来自 partno 译码层）
        "product": product,
        "cost_price": top_cost,
        "store_price": top_store,
        "final_price": final,
        "save_percent": save,
    }


# ---------- OE 一致性校验（原厂系品牌独立对比） ----------


# 需要做独立 OE 一致性校验的「原厂系」品牌名（小写形式，接口返回统一 lower() 后匹配）
# 接口返回实测："原厂国内4s件"（小写 s）；可能也有用户写的 "原厂国内4S件"（大写 S）
_OEM_BRAND_NAMES = {"原厂", "原厂国内4s件"}


def _mark_oe_consistency(product, input_oe):
    """对 product.child 中的每个「原厂系」品牌行，独立对比其接口返回的 oe 与询价输入的原始 oe。

    每个品牌各自判定，互不影响：
      - brand_name.lower() ∈ _OEM_BRAND_NAMES 且 oe 非空 → 标记 oe_match = "match" / "diff"
      - 其他品牌或 oe 缺失 → 不标记

    标记写入 child 字典本身（dict 引用修改，调用方持有的 product 自动生效）。
    """
    if not product or not input_oe:
        return
    input_norm = input_oe.replace(" ", "").strip()
    if not input_norm:
        return
    for c in product.get("child") or []:
        bn = (c.get("brand_name") or "").lower().replace(" ", "")
        if bn not in _OEM_BRAND_NAMES:
            continue
        child_oe = (c.get("oe") or "").replace(" ", "").strip()
        if not child_oe:
            continue
        c["oe_match"] = "match" if child_oe == input_norm else "diff"


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
    其余品牌行归一进 child 表（前端比价区）；图从 product_list 返回的
    child[].pic 字段挑（服务方已处理好的 CDN URL），下载校验 MD5 过滤占位图。
    全部是占位图 → 降级为空串不发图。
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
    # 从品牌行里挑第一张真实产品图（MD5 校验过滤占位图）
    image = qq_client.pick_product_pic(brand_rows)
    child = []
    for c in brand_rows[:10]:
        try:
            stock = int(c.get("stock") if c.get("stock") is not None else 0)
        except (TypeError, ValueError):
            stock = 0
        dn = {
            str(i.get("key") or "").lower(): (i.get("number") or "")
            for i in (c.get("display_number") or []) if isinstance(i, dict)
        }
        child.append({
            # 原有字段（保持契约兼容）
            "brand_name": c.get("brand_name") or "",
            "cost_price": str(c.get("cost_price") or ""),
            "store_price": str(c.get("store_price") or ""),
            "stock": stock,
            # ★ 新增字段：每个品牌自己的完整信息
            "product_name": c.get("name") or c.get("l_name_zh") or c.get("l_name_zh_default") or "",
            "product_id": c.get("product_id"),
            "retail_price": str(c.get("price") or c.get("store_cass_price") or ""),  # 开思价：优先 price，降级 store_cass_price；实测两者通常相同
            "image": c.get("pic") or c.get("bigpic") or "",      # 每个品牌自己的产品图
            "oe": dn.get("oe") or "",                            # 这个品牌实际对应的 OE（≠ 查询用的 OE）
            "partent_number": dn.get("partent") or "",
            "quote_product_remark": c.get("quote_product_remark") or "",  # 快捷报价备注名，模板优先显示
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
        "image": image,
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
            "text": _quote_text(row, ctx["car"], items, ctx["level"], ctx["rate"]),
        },
        "error": ctx["error"],
    }


# 纯 ASCII 字母数字下划线 + @openim/大写字母的 pattern → 很可能是 wxid/账号，不是昵称
# 真实昵称通常包含中文、emoji 或特殊符号（「是揚啊！」「广州名配🔜林远津」「佛山巴博瑞-烊」）
_WXID_RE = re.compile(r'^[a-zA-Z0-9_\-]+(@openim)?$')


def _looks_like_wxid(s: str) -> bool:
    """判断一个字符串是否像 wxid/账号（而非真实昵称）。

    wxid 有几种形态：
      - wxid_xxx 开头的内部 ID
      - 纯字母数字的账号（kangweiyang001, zhufengyou002, au358m）
      - 数字串 + @openim（25984982326870927@openim）
    真实昵称通常带中文或 emoji，不会全 ASCII。
    """
    if not s:
        return False
    return bool(_WXID_RE.match(s))


def _resolve_real_name(sender_name, conv):
    """V3：优先用真实名称/备注，不直接用 wxid。

    查找优先级：
      1. sender_name 有值且不像 wxid → 直接用（真实昵称/姓名）
      2. 单聊 → Contact 表按 conv.wxid 查 name
      3. 群聊 + sender_name 像 wxid → GroupMember 表按 (conv.wxid=群ID, sender_name=成员wxid) 查 nickname
      4. sender_name 像 wxid → Contact 表按 sender_name 查 name
      5. 兜底 conv.name → "客户"
    """
    from backend.models.contact import Contact

    sn = (sender_name or "").strip()
    is_wxid = _looks_like_wxid(sn)

    # 1. sender_name 不像 wxid → 真实昵称/姓名，直接用
    if sn and not is_wxid:
        return sn

    # 2. 单聊：用 conv.wxid 查对方真实名
    if conv and conv.chat_type == Conversation.CHAT_SINGLE and conv.wxid:
        c = Contact.query.filter(
            Contact.wxid == conv.wxid, Contact.deleted_at.is_(None),
        ).first()
        if c and c.name:
            return c.name.strip()

    # 3. 群聊 + sender_name 像 wxid → GroupMember 查群内昵称
    if conv and conv.chat_type == Conversation.CHAT_GROUP and conv.wxid and is_wxid:
        from backend.models.group_member import GroupMember
        g = GroupMember.query.filter(
            GroupMember.chatroom_wxid == conv.wxid,
            GroupMember.wxid == sn,
            GroupMember.deleted_at.is_(None),
        ).first()
        if g and g.nickname:
            return g.nickname.strip()

    # 4. sender_name 像 wxid → Contact 查（可能是好友的 wxid）
    if is_wxid:
        c = Contact.query.filter(
            Contact.wxid == sn, Contact.deleted_at.is_(None),
        ).first()
        if c and c.name:
            return c.name.strip()

    # 5. 兜底
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


def _quote_text(row, car, items, level=None, rate=None):
    """话术模板（2026-11-21 V7）：品牌按 sell_price 升序，品牌名+产品名+价格三列对齐。

    ────────────────── 头部 ──────────────────
    @真实名称 + VIN + 车型（saleModelName 已含品牌则不再重复拼接）

    ────────────────── ★ 区块（所有 item 都显示，无产品的只出标题） ──────────────────
    ★n、{oe_name 或 product_name} ({oe})
    ① {brand}[({product_name 若 ≠ brand 且 ≠ title})]    {sell}
    ② ...

    改动（对比 V5）：
    - 分隔线 10→16 字符；品牌行无缩进
    - 品牌按 sell_price 升序排序
    - ★块间加空行（首块除外）
    - 无 product 的 item 也显示 ★标题 + OE
    - 括号条件恢复 V5：p_name != brand AND p_name != title 才追加
    - 每个 ★块内按 brand_display 最大宽度左填充，价格列对齐
    """
    rate = rate or 1.0
    blocks = []
    has_car = bool(car and (car["brandName"] or car["model"]))
    if not items and not has_car:
        return ""

    # 头部
    conv = db.session.get(Conversation, row.conversation_id)
    who = _resolve_real_name(row.sender_name, conv)
    blocks.append(f"@{who}")

    # 读当前会话/用户的「原厂OE详号」开关（决定标识后是否追加括号里的原始 OE 号）
    # 口径和 _customer_rate 一致：单聊 scope=user + target_wxid=conv.wxid；群聊 scope=group + target_wxid=conv.wxid
    oe_detail_enabled = False
    try:
        from backend.models.contact_remark_config import ContactRemarkConfig, SCOPE_GROUP, SCOPE_USER
        if conv and conv.wxid:
            scope = SCOPE_GROUP if conv.chat_type == Conversation.CHAT_GROUP else SCOPE_USER
            cfg = ContactRemarkConfig.query.filter_by(
                scope_type=scope, target_wxid=conv.wxid, deleted_at=None,
            ).first()
            oe_detail_enabled = bool(cfg.oe_detail_enabled) if cfg else False
    except Exception:
        oe_detail_enabled = False
    if row.vin:
        blocks.append(row.vin)
    if has_car:
        if car.get("saleModelName"):
            # saleModelName 已含品牌（"奔驰 GLC 300 L 4MATIC 2020 ..."），不再重复拼 brandName
            head = car["saleModelName"]
        else:
            head = " ".join(t for t in (car["brandName"], car["model"]) if t)
            if car["yearPattern"]:
                head += f" {car['yearPattern']}款"
            if car["displacement"]:
                head += f" {car['displacement']}"
        blocks.append(head)

    # ★ 区块（按配件类型固定优先级排序）
    if items:
        # 优先级：半轴类 → 分动箱类 → 油底壳类 → 其他（保持原序）
        _PRIORITY = [
            ("半轴", "传动轴"),    # 0
            ("分动箱",),          # 1
            ("油底壳",),          # 2
        ]
        def _part_rank(it):
            text = (it.get("part") or it.get("oe_name") or "").lower()
            for rank, kws in enumerate(_PRIORITY):
                if any(kw in text for kw in kws):
                    return rank
            return 99
        items_sorted = sorted(items, key=_part_rank)

        blocks.append("—" * 16)
        circles = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩"]
        for n, it in enumerate(items_sorted, 1):
            # ★块间空行（首块不加）
            if n > 1:
                blocks.append("")

            p = it.get("product") or {}
            # ★ 标题：优先 partno 的 oe_name（更贴近客户询价词），其次 product_name，最后原 part
            title = (it.get("oe_name")
                     or p.get("product_name")
                     or it.get("part")
                     or "")
            oe = (it.get("oe")
                  or (p.get("display_number", {}) or {}).get("value")
                  or "")
            blocks.append(f"★{n}、{title} ({oe})")

            # 有产品档案 → 列出品牌报价（按我方报价升序 + 价格列对齐）；无档案 → 标题后结束
            child = p.get("child") or []
            if child:
                def _sort_key(c):
                    try:
                        return float(c.get("sell_price") or 0)
                    except (TypeError, ValueError):
                        return float("inf")
                child_sorted = sorted(child, key=_sort_key)

                # 先算所有品牌行，拿到最大 brand_display 宽度用于对齐
                rows = []  # [(brand_display, sell, oe_match_tag), ...]
                for c in child_sorted:
                    brand = (c.get("brand_name") or "").strip()
                    if not brand:
                        continue
                    sell = c.get("sell_price_fmt") or ""
                    if not sell:
                        continue
                    # 名称优先用 quote_product_remark（开思自定义备注名），
                    # 为空则不显示名称段 —— 直接品牌｜¥价格
                    remark = (c.get("quote_product_remark") or "").strip()
                    if remark:
                        brand_display = f"{brand}｜{remark}｜"
                    else:
                        brand_display = f"{brand}｜"
                    # OE 一致性标识：|替换 / |对号（oe_match=diff→替换, match→对号）
                    oe_match = c.get("oe_match")  # "diff" / "match" / None
                    if oe_match:
                        oe_raw = (c.get("oe") or "").strip()
                        if oe_detail_enabled and oe_raw:
                            # 开关开：直接展示接口返回的原始 OE 号，"替换/对号"标记藏掉
                            oe_tag = oe_raw
                        else:
                            oe_tag = "替换" if oe_match == "diff" else "对号"
                    else:
                        oe_tag = ""
                    rows.append((brand_display, sell, oe_tag))
                    if len(rows) >= 10:
                        break

                # 输出：品牌｜产品名｜¥价格[|替换/|对号]
                shown = 0
                for bd, sell, oe_tag in rows:
                    suffix = f"｜{oe_tag}" if oe_tag else ""
                    blocks.append(f"{circles[shown]} {bd}{sell}{suffix}")
                    shown += 1
    return "\n".join(blocks)
