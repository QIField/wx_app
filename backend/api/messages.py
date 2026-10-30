"""消息相关 API：发送消息入口。

WebSocket 推送没有请求头上下文，所以这里不用装饰器，
改为手动取令牌校验（逻辑统一在 services/auth.py）。
"""
from flask import Blueprint, jsonify, request

from backend.config import SEND_ENABLED
from backend.models.conversation import Conversation
from backend.services.auth import must_change_guard, request_user
from backend.sync.send_service import SendDispatchError, send_message

bp = Blueprint("messages", __name__)

_VALID_TYPES = {1, 2, 3, 4, 5}  # 文本/图片/文件/视频/链接卡片


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
