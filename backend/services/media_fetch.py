"""媒体下载与落盘缓存：API 按需下载和同步预下载共用的唯一实现。

流程（见 docs/api.md 第一部分「媒体」与附录「联调实测记录」）：
查缓存 → 未命中调中间方下载接口（POST 拿 CDN 预签名地址 fileUrl/url
→ GET 拉回文件字节）→ 按魔数判断真实类型 → 落盘缓存。

缓存落盘：backend/media/{消息日期}/{message_id}[_t{img_type}]{ext}，
按消息 create_time 的日期分目录（如 2026-10-31/），目录可经 .env MEDIA_DIR 覆盖。
"""
import mimetypes
import threading
import xml.etree.ElementTree as ET

from backend.adapter import client as middle_client
from backend.adapter.client import MiddleApiError
from backend.config import MEDIA_DIR
from backend.extensions import db
from backend.models.conversation import Conversation
from backend.models.message import Message

# msg_type → 中间方下载接口（V2 新增，无 uuid；返回 JSON+CDN 地址，client 内部做二次 GET）
DOWNLOAD_ACTION = {
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

# 中间方按设备限制并发下载任务数（实测超限报 50003「下载任务已达上限」）。
# 同设备的所有下载——同步预下载 + 接口兜底——在此排队串行；不同设备互不影响。
_DEVICE_LOCKS = {}
_LOCKS_GUARD = threading.Lock()


def _device_lock(openid):
    """取（或建）该设备的下载锁。"""
    with _LOCKS_GUARD:
        lock = _DEVICE_LOCKS.get(openid)
        if lock is None:
            lock = _DEVICE_LOCKS[openid] = threading.Lock()
        return lock


def build_params(msg, img_type):
    """按类型拼中间方下载参数（参数表见 docs/api.md 附录 messag_api）。"""
    xml = msg.content or ""
    if msg.msg_type == Message.MSG_IMAGE:
        return {"xml": xml, "img_type": img_type}
    if msg.msg_type == Message.MSG_VOICE:
        return {"xml": xml, "msg_id": msg.middle_msg_id or ""}
    if msg.msg_type == Message.MSG_EMOJI:
        return {"emoji_md5": _emoji_md5(msg)}
    return {"xml": xml}  # 文件 / 视频


def cache_dir_for(msg):
    """该消息的缓存目录：按消息日期分文件夹，避免媒体根目录散乱。"""
    return MEDIA_DIR / msg.create_time.strftime("%Y-%m-%d")


def cached_path(msg, img_type):
    """本地缓存命中返回文件路径；未命中返回 None。"""
    cache_dir = cache_dir_for(msg)
    if not cache_dir.is_dir():
        return None
    matches = sorted(cache_dir.glob(f"{_cache_stem(msg, img_type)}.*"))
    return matches[0] if matches else None


def fetch_and_cache(msg, img_type=2):
    """查缓存 → 未命中排队下载（同设备串行）→ 按魔数定型 → 落盘，返回缓存路径。

    失败抛 MiddleApiError；已有缓存直接返回（预下载靠它做查重续传）。
    """
    cached = cached_path(msg, img_type)
    if cached is not None:
        return cached

    openid = _openid_of(msg)
    with _device_lock(openid):
        # 排到队首再查一次：等锁期间可能已被前面排队的请求下载好
        cached = cached_path(msg, img_type)
        if cached is not None:
            return cached

        data, content_type = middle_client.call_download(
            "messag_api", DOWNLOAD_ACTION[msg.msg_type], build_params(msg, img_type),
            openid=openid,
        )
        if not data:
            raise MiddleApiError("媒体内容为空")

        content_type, ext = sniff_type(data, content_type)
        if ext == ".json":
            # 实测错误报文会被当文件拉回（如「下载任务已达上限」），
            # 落盘会冒充媒体在页面裂图，直接按失败处理
            raise MiddleApiError("下载返回异常内容（非媒体文件）")
        path = cache_path(msg, img_type, ext)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return path


def mimetype_of(path):
    """缓存扩展名 → Content-Type（下载时的类型落在了扩展名上）。"""
    return _MIME_BY_EXT.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def file_name(msg, path):
    """下载名：文件类消息从 xml 里取原标题，其余用缓存文件名。"""
    if msg.msg_type != Message.MSG_FILE:
        return None
    return _xml_first_text(msg, "title") or path.name


def cache_path(msg, img_type, ext):
    return cache_dir_for(msg) / f"{_cache_stem(msg, img_type)}{ext}"


def sniff_type(data, fallback):
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


def _cache_stem(msg, img_type):
    """图片按清晰度分开缓存，其余一个消息一个文件。"""
    return f"{msg.id}_t{img_type}" if msg.msg_type == Message.MSG_IMAGE else str(msg.id)


def _ext_for(content_type):
    """Content-Type → 缓存扩展名。"""
    return _EXT_OVERRIDES.get(content_type) or mimetypes.guess_extension(content_type) or ".bin"


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


def _xml_first_text(msg, tag):
    """取 content xml 里第一个指定标签的文本。"""
    try:
        root = ET.fromstring(msg.content or "")
    except ET.ParseError:
        return ""
    el = root.find(f".//{tag}")
    return (el.text or "").strip() if el is not None and el.text else ""
