"""媒体下载与落盘缓存：API 按需下载和同步预下载共用的唯一实现。

流程（见 docs/api.md 第一部分「媒体」与附录「联调实测记录」）：
查缓存 → 未命中调中间方下载接口（POST 拿 CDN 预签名地址 fileUrl/url
→ GET 拉回文件字节）→ 按魔数判断真实类型 → 落盘缓存。

缓存落盘：backend/media/{消息日期}/{message_id}[_q{rank}]{ext}，
按消息 create_time 的日期分目录（如 2026-10-31/），目录可经 .env MEDIA_DIR 覆盖。
图片 rank 是「清晰度名次」而非中间方固定档位：先把 1/2/3 三档全部下载，
按像素面积排序，q1=最清、q3=缩略图；非图片消息仍是 {message_id}{ext}。
"""
import io
import mimetypes
import threading
import xml.etree.ElementTree as ET

from PIL import Image

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

# 中间方图片档位与外对清晰度名次共用 1/2/3：1 最清、2 中间、3 缩略图。
# 实测三档常返回同一 URL，不能直接拿档位当清晰度，必须下载后比较像素再排名。
IMAGE_RANKS = (1, 2, 3)

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


def cached_path(msg, rank):
    """本地缓存命中返回文件路径；未命中返回 None。图片按清晰度名次找 _q{rank}。"""
    cache_dir = cache_dir_for(msg)
    if not cache_dir.is_dir():
        return None
    matches = sorted(cache_dir.glob(f"{_cache_stem(msg, rank)}.*"))
    return matches[0] if matches else None


def fetch_and_cache(msg, rank=3):
    """媒体缓存统一入口：图片先备齐三档并排名，其余单文件下载后返回缓存路径。

    - 图片 rank=1/2/3 表示清晰度名次（1 最清、3 缩略图），无论取哪一档都会先准备三档；
      非法值回退 3（聊天缩略图）。
    - 失败抛 MiddleApiError；已有缓存直接返回（预下载靠它做查重续传）。
    """
    if msg.msg_type == Message.MSG_IMAGE:
        return fetch_image_tiers(msg, rank)

    cached = cached_path(msg, rank)
    if cached is not None:
        return cached

    openid = _openid_of(msg)
    with _device_lock(openid):
        # 排到队首再查一次：等锁期间可能已被前面排队的请求下载好
        cached = cached_path(msg, rank)
        if cached is not None:
            return cached

        data, content_type = middle_client.call_download(
            "messag_api", DOWNLOAD_ACTION[msg.msg_type],
            build_params(msg, 0),  # 非图片参数不含 img_type，占位值会被忽略
            openid=openid,
        )
        if not data:
            raise MiddleApiError("媒体内容为空")

        content_type, ext = sniff_type(data, content_type)
        if ext == ".json":
            # 实测错误报文会被当文件拉回（如「下载任务已达上限」），
            # 落盘会冒充媒体在页面裂图，直接按失败处理
            raise MiddleApiError("下载返回异常内容（非媒体文件）")
        path = cache_path(msg, rank, ext)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return path


def fetch_image_tiers(msg, rank=1):
    """图片三档全下载 → 像素比较 → 按清晰度排名写 q1/q2/q3 → 返回 rank 档路径。

    名次不固定对应中间方 img_type：谁像素多谁是 q1（同像素按字节数，再按原始档位）。
    三档文件齐全时直接命中；同设备并发请求由设备锁排队，锁内二次查缓存避免重复下载。
    """
    if rank not in IMAGE_RANKS:
        rank = 3

    ready = _image_tiers(msg)
    if ready is not None:
        return ready[rank]

    openid = _openid_of(msg)
    with _device_lock(openid):
        ready = _image_tiers(msg)
        if ready is not None:
            return ready[rank]
        tiers = _download_all_image_tiers(msg, openid)
        return _store_image_tiers(msg, tiers)[rank]


def _image_tiers(msg):
    """三档缓存齐全返回 {rank: path}；缺任何一档返回 None（需重新下载三档）。"""
    paths = {}
    for rank in IMAGE_RANKS:
        path = cached_path(msg, rank)
        if path is None:
            return None
        paths[rank] = path
    return paths


def _download_all_image_tiers(msg, openid):
    """按中间方 1/2/3 档全部请求；单档失败跳过，三档全失败才抛错。

    实测三档常返回同一个 CDN 地址：POST 仍各请求一次，但文件只 GET 一次并复用字节，
    避免同一张大图下载三遍（首次打开会话时这是主要耗时来源）。
    """
    tiers, errors, by_object = [], [], {}
    for spec in IMAGE_RANKS:
        try:
            data, content_type, file_url = middle_client.call_download_with_url(
                "messag_api", DOWNLOAD_ACTION[msg.msg_type],
                build_params(msg, spec), openid=openid,
            )
        except MiddleApiError as exc:
            errors.append(f"img_type={spec}: {exc}")
            continue
        if not data:
            errors.append(f"img_type={spec}: 内容为空")
            continue
        object_key = (file_url or "").split("?")[0]  # 去掉签名参数，只比对象路径
        if object_key and object_key in by_object:
            cached = by_object[object_key]
            tiers.append({"spec": spec, "data": cached["data"], "ext": cached["ext"]})
            continue
        content_type, ext = sniff_type(data, content_type)
        if ext == ".json":
            errors.append(f"img_type={spec}: 返回异常内容（非媒体文件）")
            continue
        tier = {"data": data, "ext": ext}
        if object_key:
            by_object[object_key] = tier
        tiers.append({"spec": spec, **tier})
    if not tiers:
        raise MiddleApiError("图片三档均下载失败：" + "；".join(errors)[:200])
    return tiers


def _store_image_tiers(msg, tiers):
    """像素排序后写 q1~q3；不足三档用最后一档（最弱）补齐，保证每个名次都有文件。"""
    ranked = sorted(
        tiers,
        key=lambda t: (_pixel_area(t["data"]), len(t["data"]), -t["spec"]),
        reverse=True,
    )
    while len(ranked) < len(IMAGE_RANKS):
        ranked.append(ranked[-1])
    paths = {}
    for rank, tier in zip(IMAGE_RANKS, ranked):
        path = cache_path(msg, rank, tier["ext"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(tier["data"])
        paths[rank] = path
    return paths


def _pixel_area(data):
    """像素总数（宽×高）；读不出尺寸返回 0，交给字节数兜底排序。"""
    try:
        with Image.open(io.BytesIO(data)) as im:
            return im.width * im.height
    except Exception:
        return 0


def mimetype_of(path):
    """缓存扩展名 → Content-Type（下载时的类型落在了扩展名上）。"""
    return _MIME_BY_EXT.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def file_name(msg, path):
    """下载名：文件类消息从 xml 里取原标题，其余用缓存文件名。"""
    if msg.msg_type != Message.MSG_FILE:
        return None
    return _xml_first_text(msg, "title") or path.name


def cache_path(msg, rank, ext):
    return cache_dir_for(msg) / f"{_cache_stem(msg, rank)}{ext}"


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


def _cache_stem(msg, rank):
    """图片按清晰度名次分开缓存（q1 最清），其余一个消息一个文件。"""
    return f"{msg.id}_q{rank}" if msg.msg_type == Message.MSG_IMAGE else str(msg.id)


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
