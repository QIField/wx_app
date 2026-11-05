"""媒体消息出口：统一给前端拉图片/文件/视频/语音/表情的原始媒体。

流程（见 docs/api.md 第一部分「媒体」与附录「联调实测记录」）：
鉴权 + 数据隔离 → 查本地缓存（同步任务已预下载，绝大多数命中）
→ 未命中才调中间方下载并落盘（共用实现见 services/media_fetch.py）→ 回传文件流。
"""
from flask import Blueprint, jsonify, request, send_file

from backend.adapter.client import MiddleApiError
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.services import media_fetch
from backend.services.audit import AuditLog, AuditModule, log_action
from backend.services.auth import must_change_guard, request_user, user_from_token

bp = Blueprint("media", __name__)

_IMG_TYPES = {1, 2, 3}  # 实测中间方语义：2=大图/高清；1 与 3 返回的均为缩略图（默认 2）


@bp.get("/api/messages/<int:message_id>/media")
def get_media(message_id):
    """返回该条消息的媒体文件流；?img_type= 仅图片有效（1高清 2常规 3缩略图）。

    鉴权：优先 Authorization 头；<img>/<audio> 带不了头，允许 ?token= 兜底。
    """
    user = request_user() or user_from_token(request.args.get("token", ""))
    if user is None:
        return jsonify(code=401, msg="登录已失效，请重新登录"), 401
    blocked = must_change_guard(user)
    if blocked is not None:
        return blocked

    msg = _load_message(message_id, user)
    if msg is None:
        return jsonify(code=404, msg="消息不存在"), 404
    if msg.msg_type not in media_fetch.DOWNLOAD_ACTION:
        return jsonify(code=400, msg="该消息类型没有可拉取的媒体"), 400

    img_type = request.args.get("img_type", type=int) or 2
    if msg.msg_type == Message.MSG_IMAGE and img_type not in _IMG_TYPES:
        img_type = 2

    cached = media_fetch.cached_path(msg, img_type)
    if cached is not None:
        # max-age 长缓存：媒体按消息 id 不可变，命中后浏览器不再回源（含 304 协商）
        return send_file(cached, mimetype=media_fetch.mimetype_of(cached),
                         conditional=True, max_age=86400)

    return _download_and_cache(msg, img_type)


def _load_message(message_id, user):
    """取消息并做数据隔离：只能拉自己绑定设备会话的媒体（项目硬约束）。"""
    from backend.services.devices import user_openids

    openids = user_openids(user.id)
    if not openids:
        return None
    return (
        Message.query.join(Conversation, Message.conversation_id == Conversation.id)
        .filter(
            Message.id == message_id,
            Message.deleted_at.is_(None),
            Conversation.deleted_at.is_(None),
            Conversation.openid.in_(openids),
        )
        .first()
    )


def _download_and_cache(msg, img_type):
    """未命中缓存：调中间方下载 → 落盘 → 回文件流。失败记审计日志（仅 fail）。"""
    try:
        path = media_fetch.fetch_and_cache(msg, img_type)
    except MiddleApiError as exc:
        log_action(AuditModule.SYNC, "媒体下载", f"消息 {msg.id}",
                   result=AuditLog.RESULT_FAIL, detail=str(exc)[:255])
        return jsonify(code=502, msg=f"媒体下载失败：{exc}"), 502
    return send_file(path, mimetype=media_fetch.mimetype_of(path), conditional=True,
                     max_age=86400,
                     as_attachment=msg.msg_type == Message.MSG_FILE,
                     download_name=media_fetch.file_name(msg, path))
