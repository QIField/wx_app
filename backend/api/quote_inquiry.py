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
from backend.services.quote_pricing import rebuild_quote_text

bp = Blueprint("quote_inquiry", __name__)

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


@bp.get("/api/quote/inquiries")
@require_role()
def list_inquiries():
    """询价列表：?status=0-4 过滤状态，?conversation_id= 定位会话，id 倒序分页。"""
    openids = user_openids(g.current_user.id)
    if not openids:
        return jsonify(code=0, msg="success", data={"total": 0, "page": 1, "limit": 0, "list": []})

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

    text = rebuild_quote_text(row, price)
    if not (text or "").strip():
        return jsonify(code=400, msg="暂无报价话术可发送"), 400

    if not quote_sender.send_manual(row, text, operator=g.current_user):
        err = (row.price_json or {}).get("error") or "发送失败"
        db.session.commit()  # review 状态与 error 原因落库
        return jsonify(code=502, msg=err), 502
    db.session.commit()
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
    return jsonify(code=0, msg="success", data=_inquiry_payload(row))


def _inquiry_json(row, conv):
    """询价行出参：会话名走脱敏（与工作台一致），wxid 绝不外带。"""
    name = anonymize.resolved_name(conv.name, conv.wxid)
    return {
        "id": row.id,
        "conversation_id": row.conversation_id,
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
