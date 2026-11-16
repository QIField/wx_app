"""自定义铃声 API：上传（双重校验）、列表、软删除、音频播放。

播放路由 GET /media/ringtones/<name> 不做登录鉴权——<audio> 标签带不了请求头；
安全靠文件名本身：uuid4 hex 不可猜测 + 白名单强正则防目录穿越 + nosniff。
上传三重校验：扩展名白名单 → 大小上限 → 文件头 magic number（伪造扩展名直接拒）。
"""
import re
import shutil
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, g, jsonify, request, send_file

from backend.config import (
    MEDIA_DIR,
    RINGTONE_ALLOWED_EXTS,
    RINGTONE_MAX_BYTES,
    RINGTONE_MAX_COUNT,
    RINGTONE_MIN_FREE_BYTES,
)
from backend.extensions import db
from backend.models.audit_log import AuditLog
from backend.models.ringtone import UserRingtone
from backend.services.audit import AuditModule, log_action
from backend.services.auth import require_role

bp = Blueprint("ringtones", __name__)

_SUBDIR = "ringtones"
# 下载文件名只允许 uuid4 hex + 白名单扩展名，别的一律 404
_NAME_RE = re.compile(r"^[0-9a-f]{32}\.(mp3|m4a|wav|ogg)$")
_MIME = {
    "mp3": "audio/mpeg",
    "m4a": "audio/mp4",
    "wav": "audio/wav",
    "ogg": "audio/ogg",
}

_EXT_TIP = "、".join(ext.upper() for ext in RINGTONE_ALLOWED_EXTS)


def _ringtones_dir() -> Path:
    return MEDIA_DIR / _SUBDIR


def _sniff_ext(blob: bytes):
    """从文件头识别音频格式（magic number）；识别不出返回 None。

    mp3：ID3 头或 MPEG 帧同步（0xFFEx）；wav：RIFF....WAVE；
    m4a：偏移 4 的 ftyp 盒；ogg：OggS。
    """
    if blob[:3] == b"ID3" or (
        len(blob) > 1 and blob[:1] == b"\xff" and blob[1:2] != b"\x00" and (blob[1] & 0xE0) == 0xE0
    ):
        return "mp3"
    if blob[:4] == b"RIFF" and blob[8:12] == b"WAVE":
        return "wav"
    if blob[4:8] == b"ftyp":
        return "m4a"
    if blob[:4] == b"OggS":
        return "ogg"
    return None


def _clean_name(filename: str) -> str:
    """展示名：取文件主名，去掉扩展名与首尾空白，超长截断。"""
    stem = (filename or "").rsplit(".", 1)[0].strip()
    return (stem or "自定义铃声")[:64]


def _upload_guard(user, file):
    """上传前置校验（顺序：缺失→格式→空→大小→魔数→数量→磁盘水位）。

    校验失败时同步写审计日志（存储空间不足场景）。
    返回 (视图返回值|None, 扩展名|None, 文件字节|None)：失败时视图返回值为 (响应, 400)。
    """
    if file is None or not file.filename:
        return (jsonify(code=400, msg="缺少文件（multipart 字段 file）"), 400), None, None

    ext = (file.filename.rsplit(".", 1)[-1] or "").lower()
    if ext not in RINGTONE_ALLOWED_EXTS:
        return (jsonify(code=400, msg=f"不支持的格式，仅支持 {_EXT_TIP}"), 400), None, None

    blob = file.read()
    if not blob:
        return (jsonify(code=400, msg="文件内容为空"), 400), None, None
    if len(blob) > RINGTONE_MAX_BYTES:
        return (jsonify(code=400, msg=f"铃声文件超过 {RINGTONE_MAX_BYTES // (1024 * 1024)}MB 上限"), 400), None, None

    if _sniff_ext(blob) != ext:
        return (jsonify(code=400, msg="文件内容与扩展名不符，或不是有效音频文件"), 400), None, None

    if (
        UserRingtone.query.filter_by(user_id=user.id, deleted_at=None).count()
        >= RINGTONE_MAX_COUNT
    ):
        return (jsonify(code=400, msg=f"最多上传 {RINGTONE_MAX_COUNT} 个自定义铃声"), 400), None, None

    if shutil.disk_usage(MEDIA_DIR).free < RINGTONE_MIN_FREE_BYTES:
        log_action(AuditModule.SYSTEM, "上传铃声", file.filename,
                   result=AuditLog.RESULT_FAIL, detail="存储空间不足", operator=user)
        return (jsonify(code=400, msg="存储空间不足，请联系管理员"), 400), None, None

    return None, ext, blob


@bp.post("/api/ringtones")
@require_role()
def upload_ringtone():
    """上传自定义铃声：multipart 字段 file，仅 MP3/M4A/WAV/OGG，≤5MB。"""
    user = g.current_user
    file = request.files.get("file")
    err, ext, blob = _upload_guard(user, file)
    if err:
        return err

    stored = uuid4().hex + "." + ext
    _ringtones_dir().mkdir(parents=True, exist_ok=True)
    (_ringtones_dir() / stored).write_bytes(blob)

    row = UserRingtone(
        user_id=user.id,
        name=_clean_name(file.filename),
        file_name=file.filename,
        stored_name=stored,
        size=len(blob),
        fmt=ext,
    )
    db.session.add(row)
    db.session.commit()
    log_action(AuditModule.SYSTEM, "上传铃声", row.name, detail=f"{stored} {len(blob)}B", operator=user)
    return jsonify(code=0, msg="success", data=row.to_json())


@bp.get("/api/ringtones")
@require_role()
def list_ringtones():
    """当前登录人的自定义铃声列表（软删除的不返回）。"""
    rows = (
        UserRingtone.query.filter_by(user_id=g.current_user.id, deleted_at=None)
        .order_by(UserRingtone.id.desc())
        .all()
    )
    return jsonify(code=0, msg="success", data=[r.to_json() for r in rows])


@bp.delete("/api/ringtones/<int:ring_id>")
@require_role()
def delete_ringtone(ring_id):
    """删除自定义铃声：软删除只打标记；磁盘文件保留。"""
    user = g.current_user
    row = UserRingtone.query.filter_by(
        id=ring_id, user_id=user.id, deleted_at=None
    ).first()
    if row is None:
        return jsonify(code=404, msg="铃声不存在或已删除"), 404

    row.soft_delete()
    db.session.commit()
    log_action(AuditModule.SYSTEM, "删除铃声", row.name, detail=row.stored_name, operator=user)
    return jsonify(code=0, msg="success")


@bp.get("/media/ringtones/<name>")
def play_ringtone(name):
    """音频播放：不鉴权（<audio> 带不了请求头），uuid 文件名不可猜测。"""
    if not _NAME_RE.match(name or ""):
        return jsonify(code=404, msg="文件不存在"), 404
    path = _ringtones_dir() / name
    if not path.is_file():
        return jsonify(code=404, msg="文件不存在"), 404
    ext = name.rsplit(".", 1)[-1]
    resp = send_file(path, mimetype=_MIME.get(ext, "application/octet-stream"), conditional=True)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Cache-Control"] = "max-age=86400"  # 同一铃声反复播放走浏览器磁盘缓存
    return resp
