"""询价查询 + 人工动作 API（阶段 3 查询 / 阶段 6 动作）：前端右栏报价处理台的数据源与操作口。

数据由阶段 2 守门分流落表（services/quote_dispatch），状态机见 models/quote_inquiry.py。
price_json 为阶段 4 回写的报价卡（契约 A r 结构 + pricing 块），sent_at 阶段 5 回写。

- GET  /api/quote/inquiries：列表（状态/会话过滤、分页）。
- POST /api/quote/inquiries/{id}/send：人工发送报价（可选 body.price 改价 → 话术联动
  重建 → 图前文后发出，置已报价）；下发失败转 review 返 502。
- POST /api/quote/inquiries/{id}/ignore：人工忽略（置 ignored）。

权限口径与工作台一致：只能看/操作自己绑定设备会话的询价（Conversation.openid ∈ 绑定设备）。
"""
from flask import Blueprint, g, jsonify, request

from backend.config import SEND_ENABLED
from backend.extensions import db
from backend.models.conversation import Conversation
from backend.models.quote_inquiry import QuoteInquiry
from backend.services import anonymize, quote_sender
from backend.services.auth import require_role
from backend.services.devices import user_openids
from backend.services.quote_dispatch import notify_inquiry
from backend.services.quote_pricing import rebuild_quote_text, rebuild_quote_text_with_override

bp = Blueprint("quote_inquiry", __name__)

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


@bp.get("/api/quote/inquiries")
@require_role()
def list_inquiries():
    """询价列表：?status=0-4 过滤状态，?conversation_id= 定位会话，
    ?openid= 精确限定设备（多设备场景下前端传 chat.activeOpenid），id 倒序分页。
    openid 未传时 fallback 账号绑定的所有设备（向后兼容）。"""
    all_openids = user_openids(g.current_user.id)
    if not all_openids:
        return jsonify(code=0, msg="success", data={"total": 0, "page": 1, "limit": 0, "list": []})

    # 精确 openid（指定了就只查这台设备，没传就查账号绑定的全部）
    exact_openid = (request.args.get("openid") or "").strip()
    if exact_openid:
        if exact_openid not in all_openids:
            return jsonify(code=403, msg="无权访问该设备的询价"), 403
        openids = [exact_openid]
    else:
        openids = all_openids

    query = (
        db.session.query(QuoteInquiry, Conversation)
        .join(Conversation, QuoteInquiry.conversation_id == Conversation.id)
        .filter(
            QuoteInquiry.deleted_at.is_(None),
            Conversation.deleted_at.is_(None),
            Conversation.openid.in_(openids),
        )
    )

    raw_status = (request.args.get("status") or "").strip()
    if raw_status:
        try:
            status = int(raw_status)
        except ValueError:
            return jsonify(code=400, msg="status 必须是 0-4 的数字"), 400
        if status not in QuoteInquiry.STATUS_LABELS:
            return jsonify(code=400, msg=f"status 只能是 {sorted(QuoteInquiry.STATUS_LABELS)}"), 400
        query = query.filter(QuoteInquiry.status == status)

    conv_id = request.args.get("conversation_id", type=int)
    if conv_id:
        query = query.filter(QuoteInquiry.conversation_id == conv_id)

    page = max(1, request.args.get("page", 1, type=int))
    limit = max(1, min(request.args.get("limit", DEFAULT_LIMIT, type=int), MAX_LIMIT))
    total = query.count()
    rows = (
        query.order_by(QuoteInquiry.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return jsonify(code=0, msg="success", data={
        "total": total, "page": page, "limit": limit,
        "list": [_inquiry_json(row, conv) for row, conv in rows],
    })


@bp.get("/api/quote/inquiries/<int:inquiry_id>")
@require_role()
def get_inquiry(inquiry_id):
    """单条询价详情（报价处理台详情页数据源）。
    出参与 list 的行结构完全一致（复用 _inquiry_json）。"""
    row = _visible_inquiry(inquiry_id)
    if row is None:
        return jsonify(code=404, msg="询价不存在或无权限"), 404
    conv = db.session.get(Conversation, row.conversation_id)
    return jsonify(code=0, msg="success", data=_inquiry_json(row, conv))


@bp.post("/api/quote/inquiries/<int:inquiry_id>/override")
@require_role()
def save_override(inquiry_id):
    """保存行内改价覆盖（详情页表格改价 debounce 自动调）。
    body.items 为 [{oe, final_price}]；按 oe 合并到 price_json.pricing.items，
    同时写 override_pricing 存原始覆盖。已发报价后允许继续改价（重新发一次会用覆盖）。
    """
    row = _visible_inquiry(inquiry_id)
    if row is None:
        return jsonify(code=404, msg="询价不存在或无权限"), 404
    body = request.get_json(silent=True) or {}
    items = body.get("items")
    if not isinstance(items, list) or not items:
        return jsonify(code=400, msg="items 必须是非空数组"), 400
    # 校验每条
    cleaned = []
    for it in items:
        oe = str(it.get("oe") or "").strip()
        fp = it.get("final_price")
        if not oe:
            continue
        try:
            fp = round(float(fp), 2)
            if fp <= 0:
                continue
        except (TypeError, ValueError):
            continue
        cleaned.append({"oe": oe, "final_price": f"{fp:.2f}"})
    if not cleaned:
        return jsonify(code=400, msg="没有有效改价项"), 400

    # 1. 存 override_pricing（原始覆盖，方便 send 时重建话术）
    row.override_pricing = {"items": cleaned}

    # 2. merge 到 price_json.pricing.items（前端拉详情/列表都能看到合并后的）
    r = dict(row.price_json or {})
    pricing = dict(r.get("pricing") or {})
    pitems = list(pricing.get("items") or [])
    if pitems:
        by_oe = {x["oe"]: x for x in cleaned}
        merged_total = 0.0
        for i, it in enumerate(pitems):
            oe = it.get("oe")
            if oe in by_oe:
                pitems[i] = {**it, "final_price": by_oe[oe]["final_price"]}
            try:
                merged_total += float(pitems[i].get("final_price") or 0)
            except (TypeError, ValueError):
                pass
        pricing["items"] = pitems
        if merged_total > 0:
            pricing["final_price"] = f"{round(merged_total, 2):.2f}"
        r["pricing"] = pricing
        row.price_json = r

    db.session.commit()
    _notify_changed(row)
    conv = db.session.get(Conversation, row.conversation_id)
    return jsonify(code=0, msg="success", data=_inquiry_json(row, conv))


def _visible_inquiry(inquiry_id):
    """当前登录人可见的询价行（绑定设备口径与列表一致）；不存在/跨设备返回 None。"""
    openids = user_openids(g.current_user.id)
    if not openids:
        return None
    return (
        db.session.query(QuoteInquiry)
        .join(Conversation, QuoteInquiry.conversation_id == Conversation.id)
        .filter(
            QuoteInquiry.id == inquiry_id,
            QuoteInquiry.deleted_at.is_(None),
            Conversation.deleted_at.is_(None),
            Conversation.openid.in_(openids),
        )
        .first()
    )


def _inquiry_payload(row):
    """动作后的行出参（会话行按 id 重取，_inquiry_json 签名保持不变）。"""
    return _inquiry_json(row, db.session.get(Conversation, row.conversation_id))


def _notify_changed(row):
    """询价状态变更广播（拓展栏 feed 静默 refresh）。"""
    notify_inquiry([row])


@bp.post("/api/quote/inquiries/<int:inquiry_id>/send")
@require_role()
def send_inquiry(inquiry_id):
    """人工发送报价（预览流动作）：可选 body.price 改价 → 话术联动 → 图前文后发出。

    已报价拒绝重复发送 409；price 需为大于 0 的数字（两位小数）；下发失败转 review 返 502。
    """
    if not SEND_ENABLED:
        return jsonify(code=403, msg="发送功能未启用（.env 改 SEND_ENABLED 后重启）"), 403
    row = _visible_inquiry(inquiry_id)
    if row is None:
        return jsonify(code=404, msg="询价不存在"), 404
    if row.status == QuoteInquiry.ST_SENT:
        return jsonify(code=409, msg="该询价已报价，请勿重复发送"), 409

    body = request.get_json(silent=True) or {}
    price = body.get("price")
    if price is not None:
        try:
            price = round(float(price), 2)
        except (TypeError, ValueError):
            return jsonify(code=400, msg="price 必须是数字"), 400
        if price <= 0:
            return jsonify(code=400, msg="price 必须大于 0"), 400

    # 重建话术优先级：override_pricing（人工行内改价）> body.price（单卡顶栏改价）> 原始话术
    text = rebuild_quote_text_with_override(row, price)
    if not (text or "").strip():
        return jsonify(code=400, msg="暂无报价话术可发送"), 400

    if not quote_sender.send_manual(row, text, operator=g.current_user):
        err = (row.price_json or {}).get("error") or "发送失败"
        db.session.commit()  # review 状态与 error 原因落库
        _notify_changed(row)  # 失败也转了 review，前端需刷新状态
        return jsonify(code=502, msg=err), 502
    db.session.commit()
    _notify_changed(row)
    return jsonify(code=0, msg="success", data=_inquiry_payload(row))


@bp.post("/api/quote/inquiries/<int:inquiry_id>/ignore")
@require_role()
def ignore_inquiry(inquiry_id):
    """人工忽略询价（预览流动作）：置 ignored；已报价拒绝 409。"""
    row = _visible_inquiry(inquiry_id)
    if row is None:
        return jsonify(code=404, msg="询价不存在"), 404
    if row.status == QuoteInquiry.ST_SENT:
        return jsonify(code=409, msg="已报价的询价不能忽略"), 409
    row.status = QuoteInquiry.ST_IGNORED
    db.session.commit()
    _notify_changed(row)
    return jsonify(code=0, msg="success", data=_inquiry_payload(row))


def _inquiry_json(row, conv):
    """询价行出参：会话名走脱敏（与工作台一致），wxid 绝不外带。"""
    name = anonymize.resolved_name(conv.name, conv.wxid)
    return {
        "id": row.id,
        "conversation_id": row.conversation_id,
        "message_id": int(row.message_id) if row.message_id else None,
        "conversation_name": name or anonymize.anon_label(conv.wxid),
        "chat_type": conv.chat_type,
        "sender_name": row.sender_name or "",
        "vin": row.vin or "",
        "part_name": row.part_name or "",
        "oem_no": row.oem_no or "",
        "quoted": bool(row.quoted),
        "inquiry_time": row.inquiry_time or "",
        "inquiry_content": row.inquiry_content or "",
        "status": row.status,
        "status_label": QuoteInquiry.STATUS_LABELS.get(row.status, "未知"),
        "price_json": row.price_json,
        "sent_at": row.sent_at.strftime("%Y-%m-%d %H:%M:%S") if row.sent_at else None,
        "created_at": row.created_at.strftime("%Y-%m-%d %H:%M:%S") if row.created_at else None,
    }
