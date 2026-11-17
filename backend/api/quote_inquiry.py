"""询价查询 API（阶段 3）：前端右栏报价处理台的数据源。

数据由阶段 2 守门分流落表（services/quote_dispatch），状态机见 models/quote_inquiry.py。
price_json 为阶段 4 回写的报价卡（契约 A r 结构 + pricing 块），sent_at 阶段 5 回写。

权限口径与工作台一致：只能看自己绑定设备会话的询价（Conversation.openid ∈ 绑定设备）。
"""
from flask import Blueprint, g, jsonify, request

from backend.extensions import db
from backend.models.conversation import Conversation
from backend.models.quote_inquiry import QuoteInquiry
from backend.services import anonymize
from backend.services.auth import require_role
from backend.services.devices import user_openids

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
