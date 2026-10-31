"""媒体消息出口：统一给前端拉图片/文件/视频/语音/表情的原始媒体。

流程（见 docs/api.md 第一部分「媒体」与附录「联调实测记录」）：
鉴权 + 数据隔离 → 查本地缓存 → 未命中调中间方下载接口
（POST 拿 CDN 预签名地址 fileUrl/url → GET 拉回文件字节）→ 按魔数判断真实类型
→ 落盘缓存 → 回传文件流。

缓存落盘：backend/media/{message_id}[_t{img_type}]{ext}，目录可经 .env MEDIA_DIR 覆盖。
"""
import mimetypes
import xml.etree.ElementTree as ET

from flask import Blueprint, jsonify, request, send_file

from backend.adapter import client as middle_client
from backend.adapter.client import MiddleApiError
from backend.config import MEDIA_DIR
from backend.extensions import db
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.services.audit import AuditLog, AuditModule, log_action
from backend.services.auth import must_change_guard, request_user, user_from_token

bp = Blueprint("media", __name__)

# msg_type → 中间方下载接口（V2 新增，无 uuid；返回 JSON+CDN 地址，client 内部做二次 GET）
_DOWNLOAD_ACTION = {
    Message.MSG_IMAGE: "get_download_image",
    Message.MSG_FILE: "get_download_file",  # 预留：收到的文件现归 49→链接，后续拆分时接入
    Message.MSG_VIDEO: "get_download_video",
    Message.MSG_VOICE: "get_download_voice",
    Message.MSG_EMOJI: "get_download_emoji",
}

# Content-Type → 缓存扩展名（微信语音 amr/silk 等系统表覆盖不全，用自有映射）
_EXT_OVERRIDES = {
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/png": ".png",
    "image/webp": ".webp",
    "audio/amr": ".amr",
    "audio/silk": ".silk",
    "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "application/octet-stream": ".bin",
}
_MIME_BY_EXT = {v: k for k, v in _EXT_OVERRIDES.items()}

_IMG_TYPES = {1, 2, 3}  # 1高清 2常规 3缩略图（V2 约定，默认 2）


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
    if msg.msg_type not in _DOWNLOAD_ACTION:
        return jsonify(code=400, msg="该消息类型没有可拉取的媒体"), 400

    img_type = request.args.get("img_type", type=int) or 2
    if msg.msg_type == Message.MSG_IMAGE and img_type not in _IMG_TYPES:
        img_type = 2

    cached = _find_cache(msg, img_type)
    if cached is not None:
        return send_file(cached, mimetype=_mimetype_of(cached), conditional=True)

    return _download_and_cache(msg, img_type)


def _load_message(message_id, user):
    """取消息并做数据隔离：只能拉自己绑定设备会话的媒体（项目硬约束）。"""
    return (
        Message.query.join(Conversation, Message.conversation_id == Conversation.id)
        .filter(
            Message.id == message_id,
            Message.deleted_at.is_(None),
            Conversation.deleted_at.is_(None),
            Conversation.openid == (user.open_id or ""),
        )
        .first()
    )


def _download_and_cache(msg, img_type):
    """未命中缓存：调中间方下载 → 落盘 → 回文件流。失败记审计日志（仅 fail）。"""
    params = _build_params(msg, img_type)
    try:
        data, content_type = middle_client.call_download(
            "messag_api", _DOWNLOAD_ACTION[msg.msg_type], params, openid=_openid_of(msg),
        )
    except MiddleApiError as exc:
        log_action(AuditModule.SYNC, "媒体下载", f"消息 {msg.id}",
                   result=AuditLog.RESULT_FAIL, detail=str(exc)[:255])
        return jsonify(code=502, msg=f"媒体下载失败：{exc}"), 502

    if not data:
        return jsonify(code=404, msg="媒体内容为空"), 404

    content_type, ext = _sniff_type(data, content_type)
    path = _cache_path(msg, img_type, ext)
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return send_file(path, mimetype=content_type, conditional=True,
                     as_attachment=msg.msg_type == Message.MSG_FILE,
                     download_name=_file_name(msg, path))


def _build_params(msg, img_type):
    """按类型拼中间方下载参数（参数表见 docs/api.md 附录 messag_api）。"""
    xml = msg.content or ""
    if msg.msg_type == Message.MSG_IMAGE:
        return {"xml": xml, "img_type": img_type}
    if msg.msg_type == Message.MSG_VOICE:
        return {"xml": xml, "msg_id": msg.middle_msg_id or ""}
    if msg.msg_type == Message.MSG_EMOJI:
        return {"emoji_md5": _emoji_md5(msg)}
    return {"xml": xml}  # 文件 / 视频


def _emoji_md5(msg):
    """表情的 md5 在 content xml 的节点属性里（属性名以联调真实报文校准）。"""
    try:
        root = ET.fromstring(msg.content or "")
    except ET.ParseError:
        return ""
    for el in root.iter():
        if "md5" in el.attrib:
            return el.attrib["md5"]
    return ""


def _openid_of(msg):
    """call_download 的设备标识：顺着消息查所属会话的 openid。"""
    conv = db.session.get(Conversation, msg.conversation_id)
    return (conv.openid if conv else "") or ""


def _cache_stem(msg, img_type):
    """图片按清晰度分开缓存，其余一个消息一个文件。"""
    return f"{msg.id}_t{img_type}" if msg.msg_type == Message.MSG_IMAGE else str(msg.id)


def _find_cache(msg, img_type):
    """按前缀找缓存文件；扩展名下载时才确定，所以用 glob。"""
    if not MEDIA_DIR.is_dir():
        return None
    matches = sorted(MEDIA_DIR.glob(f"{_cache_stem(msg, img_type)}.*"))
    return matches[0] if matches else None


def _cache_path(msg, img_type, ext):
    return MEDIA_DIR / f"{_cache_stem(msg, img_type)}{ext}"


def _ext_for(content_type):
    """Content-Type → 缓存扩展名。"""
    return _EXT_OVERRIDES.get(content_type) or mimetypes.guess_extension(content_type) or ".bin"


def _sniff_type(data, fallback):
    """按魔数判断真实 (Content-Type, 扩展名)，识别不出用 fallback。

    实测 CDN 响应的 Content-Type 恒为 application/octet-stream（还拼错过），
    预签名 URL 的扩展名也不可信，只能看字节头（docs/api.md 附录实测记录）。
    """
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if data.startswith(b"\x89PNG"):
        return "image/png", ".png"
    if data.startswith(b"GIF8"):
        return "image/gif", ".gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp", ".webp"
    if data.startswith(b"#!SILK_V3"):
        return "audio/silk", ".silk"
    if data.startswith(b"#!AMR"):
        return "audio/amr", ".amr"
    if len(data) > 12 and data[4:8] == b"ftyp":
        return "video/mp4", ".mp4"
    if data.startswith(b"\x1aE\xdf\xa3"):
        return "video/webm", ".webm"
    if data.startswith(b"PK\x03\x04"):
        return "application/zip", ".zip"
    if data.startswith(b"%PDF"):
        return "application/pdf", ".pdf"
    return fallback, _ext_for(fallback)


def _mimetype_of(path):
    """缓存扩展名 → Content-Type（下载时的类型落在了扩展名上）。"""
    return _MIME_BY_EXT.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def _file_name(msg, path):
    """下载名：文件类消息从 xml 里取原标题，其余用缓存文件名。"""
    if msg.msg_type != Message.MSG_FILE:
        return None
    return _xml_first_text(msg, "title") or path.name


def _xml_first_text(msg, tag):
    """取 content xml 里第一个指定标签的文本。"""
    try:
        root = ET.fromstring(msg.content or "")
    except ET.ParseError:
        return ""
    el = root.find(f".//{tag}")
    return (el.text or "").strip() if el is not None and el.text else ""
