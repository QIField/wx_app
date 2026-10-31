"""会话与聊天记录 API：给前端读库（都过滤软删除）。

多设备：所有查询按当前登录人绑定的微信设备（open_id）过滤，
未绑定设备的账号看到的列表为空。
"""
from flask import Blueprint, g, jsonify, request

from backend.extensions import db
from backend.models.contact import Contact
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.services import conversations as conversation_service
from backend.services.auth import require_role

bp = Blueprint("conversations", __name__)

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


def _my_openid():
    """当前登录人绑定的设备标识；未绑定为 None。"""
    return g.current_user.open_id or None


def _my_conversation(conversation_id):
    """取属于当前登录人设备的会话；跨设备/已删除的会话当不存在。"""
    if _my_openid() is None:
        return None
    return (
        Conversation.query.filter(
            Conversation.id == conversation_id,
            Conversation.deleted_at.is_(None),
            Conversation.openid == _my_openid(),
        ).first()
    )


@bp.get("/api/conversations")
@require_role()
def list_conversations():
    """会话列表：本设备内 置顶优先，其余按最后消息时间倒序（NULL 排最后）。"""
    if _my_openid() is None:
        return jsonify(code=0, msg="success", data=[])

    rows = (
        Conversation.query.filter(
            Conversation.deleted_at.is_(None),
            Conversation.openid == _my_openid(),
        )
        .order_by(
            Conversation.pinned.desc(),
            Conversation.last_msg_at.is_(None).asc(),  # 兼容 MySQL 5.7（无 NULLS LAST）
            Conversation.last_msg_at.desc(),
        )
        .all()
    )
    return jsonify(code=0, msg="success", data=[_conv_json(c) for c in rows])


@bp.post("/api/conversations")
@require_role()
def open_conversation():
    """主动发起会话：按 wxid 建/取会话（联系人须在该设备的通讯录里）。

    body: {"wxid": "...", "chat_type": 1|2}；已存在直接返回，没有则新建。
    """
    openid = _my_openid()
    if openid is None:
        return jsonify(code=400, msg="当前账号未绑定微信设备"), 400

    body = request.get_json(silent=True) or {}
    wxid = (body.get("wxid") or "").strip()
    try:
        chat_type = int(body.get("chat_type"))
    except (TypeError, ValueError):
        chat_type = 0
    if not wxid or chat_type not in (Conversation.CHAT_SINGLE, Conversation.CHAT_GROUP):
        return jsonify(code=400, msg="wxid 与 chat_type（1单聊/2群聊）必填且合法"), 400

    contact_type = (
        Contact.TYPE_FRIEND if chat_type == Conversation.CHAT_SINGLE else Contact.TYPE_GROUP
    )
    exists = Contact.query.filter_by(openid=openid, wxid=wxid, type=contact_type).first()
    if exists is None:
        return jsonify(code=404, msg="通讯录中没有该联系人"), 404

    conv = conversation_service.get_or_create(openid, wxid, chat_type)
    db.session.commit()
    return jsonify(code=0, msg="success", data=_conv_json(conv))


@bp.get("/api/conversations/<int:conversation_id>/messages")
@require_role()
def list_messages(conversation_id):
    """聊天记录：时间正序，?before_id 游标翻页（拿上一页最小 id 往前翻）。"""
    conv = _my_conversation(conversation_id)
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
        "avatar": c.avatar,
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
