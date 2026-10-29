"""会话与聊天记录 API：给前端读库（都过滤软删除）。"""
from flask import Blueprint, jsonify, request

from backend.extensions import db
from backend.models.conversation import Conversation
from backend.models.message import Message

bp = Blueprint("conversations", __name__)

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


@bp.get("/api/conversations")
def list_conversations():
    """会话列表：置顶优先，其余按最后消息时间倒序。"""
    rows = (
        Conversation.query.filter(Conversation.deleted_at.is_(None))
        .order_by(
            Conversation.pinned.desc(),
            Conversation.last_msg_at.desc().nullslast(),
        )
        .all()
    )
    return jsonify(code=0, msg="success", data=[_conv_json(c) for c in rows])


@bp.get("/api/conversations/<int:conversation_id>/messages")
def list_messages(conversation_id):
    """聊天记录：时间正序，?before_id 游标翻页（拿上一页最小 id 往前翻）。"""
    conv = (
        Conversation.query.filter(
            Conversation.id == conversation_id,
            Conversation.deleted_at.is_(None),
        ).first()
    )
    if conv is None:
        return jsonify(code=404, msg="会话不存在"), 404

    page_size = request.args.get("page_size", DEFAULT_PAGE_SIZE, type=int)
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))
    before_id = request.args.get("before_id", type=int)

    q = Message.query.filter(
        Message.conversation_id == conversation_id,
        Message.deleted_at.is_(None),
    )
    if before_id:
        q = q.filter(Message.id < before_id)

    rows = q.order_by(Message.id.desc()).limit(page_size).all()
    rows.reverse()  # 库里倒序取最新一页，翻转成正序给前端

    has_more = len(rows) == page_size
    return jsonify(
        code=0,
        msg="success",
        data={
            "conversation": _conv_json(conv),
            "messages": [_msg_json(m) for m in rows],
            "next_before_id": rows[0].id if has_more and rows else None,
        },
    )


def _conv_json(c):
    return {
        "id": c.id,
        "wxid": c.wxid,
        "chat_type": c.chat_type,
        "name": c.name,
        "unread_count": c.unread_count,
        "pinned": c.pinned,
        "last_msg": c.last_msg,
        "last_msg_at": c.last_msg_at.strftime("%Y-%m-%d %H:%M:%S") if c.last_msg_at else None,
    }


def _msg_json(m):
    return {
        "id": m.id,
        "msg_type": m.msg_type,
        "direction": m.direction,
        "sender_wxid": m.sender_wxid,
        "sender_name": m.sender_name,
        "content": m.content,
        "payload": m.payload,
        "create_time": m.create_time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": m.status,
    }
