"""发送日志 API：谁（系统账号）· 何时 · 用哪个聊天账号 · 发给谁。

数据源是 message 表里 direction=2 的行 + 操作人快照字段，不另建日志表——
消息本身就是最全的发送记录（含发送中/失败状态）。
"""
from flask import Blueprint, g, jsonify, request

from backend.extensions import db
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.services.auth import require_role
from backend.services.devices import user_devices

bp = Blueprint("send_logs", __name__)

DEFAULT_LIMIT = 100
MAX_LIMIT = 500


@bp.get("/api/send-logs")
@require_role()
def list_send_logs():
    """当前账号全部绑定设备的发出消息，时间倒序；?openid= 可只看某台设备。

    与工作台数据同权限口径：只能查自己绑定设备产生的发送记录。
    """
    openids = [d.openid for d in user_devices(g.current_user.id)]
    if not openids:
        return jsonify(code=0, msg="success", data=[])

    requested = (request.args.get("openid") or "").strip()
    if requested:
        if requested not in openids:
            return jsonify(code=403, msg="无权访问该设备"), 403
        openids = [requested]

    limit = request.args.get("limit", DEFAULT_LIMIT, type=int)
    limit = max(1, min(limit, MAX_LIMIT))

    rows = (
        db.session.query(Message, Conversation)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(
            Message.deleted_at.is_(None),
            Message.direction == Message.DIR_OUT,
            Conversation.deleted_at.is_(None),
            Conversation.openid.in_(openids),
        )
        .order_by(Message.id.desc())
        .limit(limit)
        .all()
    )
    return jsonify(code=0, msg="success", data=[_log_json(msg, conv) for msg, conv in rows])


def _log_json(msg, conv):
    """一条发送记录：操作人/设备/会话/内容摘要/发送结果。"""
    return {
        "id": msg.id,
        "time": msg.create_time.strftime("%Y-%m-%d %H:%M:%S") if msg.create_time else None,
        "operator_name": msg.operator_name or "",
        "openid": conv.openid,
        "conv_name": conv.name or conv.wxid,
        "wxid": conv.wxid,
        "msg_type": msg.msg_type,
        "content": msg.content or "",
        "status": msg.status,
    }
