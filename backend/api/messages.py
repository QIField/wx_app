"""消息相关 API：发送消息入口 + 撤回。

WebSocket 推送没有请求头上下文，所以这里不用装饰器，
改为手动取令牌校验（逻辑统一在 services/auth.py）。
"""
from datetime import datetime
from uuid import uuid4

from flask import Blueprint, jsonify, request

from backend.adapter import sender as middle_sender
from backend.config import SEND_ENABLED
from backend.extensions import db
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.services.auth import must_change_guard, request_user
from backend.sync import task_query
from backend.sync.send_service import SendDispatchError, send_message

bp = Blueprint("messages", __name__)

_VALID_TYPES = {1, 2, 3, 4, 5}  # 文本/图片/文件/视频/链接卡片
REVOKE_WINDOW = 120  # 微信限制：发出 2 分钟内可撤回


@bp.post("/api/conversations/<int:conversation_id>/messages")
def send_message_api(conversation_id):
    """发消息，参数约定见 docs/api.md。

    返回 data.message_id + status（0=发送中，等 WebSocket 推最终结果）。
    只能往自己绑定设备的会话里发。
    """
    user = request_user()
    if user is None:
        return jsonify(code=401, msg="登录已失效，请重新登录"), 401
    blocked = must_change_guard(user)
    if blocked is not None:
        return blocked

    if not SEND_ENABLED:
        return jsonify(code=403, msg="发送功能未启用（联调收消息阶段禁用，.env 改 SEND_ENABLED 后重启）"), 403

    body = request.get_json(silent=True) or {}
    msg_type = body.get("msg_type")
    if msg_type not in _VALID_TYPES:
        return jsonify(code=400, msg="msg_type 不合法（1文本 2图片 3文件 4视频 5链接卡片）"), 400

    payload = body.get("payload") or {}
    if not isinstance(payload, dict):
        return jsonify(code=400, msg="payload 必须是对象"), 400

    conv = (
        Conversation.query.filter(
            Conversation.id == conversation_id,
            Conversation.deleted_at.is_(None),
            Conversation.openid == (user.open_id or ""),
        ).first()
    )
    if conv is None:
        return jsonify(code=404, msg="会话不存在"), 404

    try:
        msg = send_message(conversation_id, msg_type, body.get("content", ""), payload)
    except SendDispatchError as exc:
        return jsonify(code=502, msg=f"下发失败：{exc}"), 502

    return jsonify(
        code=0,
        msg="success",
        data={"message_id": msg.id, "status": msg.status},
    )


@bp.post("/api/messages/<int:message_id>/revoke")
def revoke_message_api(message_id):
    """撤回自己发的消息（微信限制发出 2 分钟内）。

    2026-10-31 实测：文字消息发送结果 msgId=0，撤回靠 new_msg_id 定位，
    msg_id 传 "0" 即可；new_msg_id 由 confirm_worker 从发送结果回填。
    成功后消息打 revoked 标记并推送 message_revoked。
    """
    user = request_user()
    if user is None:
        return jsonify(code=401, msg="登录已失效，请重新登录"), 401
    blocked = must_change_guard(user)
    if blocked is not None:
        return blocked

    msg = (
        Message.query.join(Conversation, Message.conversation_id == Conversation.id)
        .filter(
            Message.id == message_id,
            Message.deleted_at.is_(None),
            Conversation.deleted_at.is_(None),
            Conversation.openid == (user.open_id or ""),
        )
        .first()
    )
    if msg is None:
        return jsonify(code=404, msg="消息不存在"), 404
    if msg.direction != Message.DIR_OUT:
        return jsonify(code=400, msg="只能撤回自己发的消息"), 400
    payload = dict(msg.payload or {})
    if payload.get("revoked"):
        return jsonify(code=400, msg="该消息已撤回"), 400
    if not msg.new_msg_id:
        return jsonify(code=400, msg="缺少撤回要素（发送结果未确认回填或历史消息）"), 400
    created = msg.create_time or datetime.now()
    if (datetime.now() - created).total_seconds() > REVOKE_WINDOW:
        return jsonify(code=400, msg="超过 2 分钟，无法撤回"), 400

    conv = db.session.get(Conversation, msg.conversation_id)
    openid = (conv.openid or "") if conv else ""
    uuid = str(uuid4())
    try:
        middle_sender.revoke(
            to_wxid=conv.wxid,
            msg_id=msg.middle_msg_id or "0",
            new_msg_id=msg.new_msg_id,
            create_time=str(int(created.timestamp())),
            uuid=uuid,
            openid=openid,
        )
    except Exception as exc:
        return jsonify(code=502, msg=f"撤回下发失败：{exc}"), 502

    record = task_query.query_record("send_api", "get_revoke_message", uuid, openid=openid)
    if record is None:
        return jsonify(code=504, msg="撤回结果未确认，请稍后刷新查看"), 504
    result = task_query.as_dict(record.get("processing_result"))
    if result.get("ret") != 200:
        return jsonify(code=502, msg=f"撤回失败：{result.get('msg') or '未知错误'}"), 502

    payload["revoked"] = True
    msg.payload = payload
    db.session.commit()

    from backend.ws import hub
    hub.broadcast("message_revoked", {
        "message_id": msg.id,
        "conversation_id": msg.conversation_id,
    })
    return jsonify(code=0, msg="success", data={"message_id": msg.id})
