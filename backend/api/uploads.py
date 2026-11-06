"""文件上传与下载：给发送图片/文件/视频提供中间方可拉取的 URL。

流程（对应《文件按钮发送》流程图）：
前端选任意文件 → POST /api/uploads（登录鉴权）→ uuid 命名落盘 media/uploads/
→ 返回绝对 url（发消息时给中间方下载）+ 相对 path（本地气泡预览）。

下载路由 GET /media/uploads/<name> 不做登录鉴权——中间方服务器要直接拉；
安全靠文件名本身：uuid4 hex 不可猜测 + 强正则校验防目录穿越 +
as_attachment 防上传的 HTML/SVG 借本域内联渲染执行。
"""
import mimetypes
import re
from uuid import uuid4

from flask import Blueprint, jsonify, request, send_file

from backend.config import MEDIA_DIR, PUBLIC_BASE_URL, UPLOAD_MAX_BYTES
from backend.services.audit import AuditModule, log_action
from backend.services.auth import must_change_guard, request_user

bp = Blueprint("uploads", __name__)

UPLOADS_SUBDIR = "uploads"
# 下载文件名只允许 uuid4 hex（+可选短扩展名），别的一律 404
_NAME_RE = re.compile(r"^[0-9a-f]{32}(\.[A-Za-z0-9]{1,10})?$")


def _uploads_dir():
    return MEDIA_DIR / UPLOADS_SUBDIR


def _safe_ext(filename, content_type):
    """保留原始扩展名（剔除非字母数字字符，防注入/穿越），识别不出按 Content-Type 推。"""
    ext = re.sub(r"[^A-Za-z0-9]", "", (filename or "").rsplit(".", 1)[-1])
    if 1 <= len(ext) <= 10:
        return "." + ext.lower()
    return mimetypes.guess_extension(content_type or "") or ".bin"


@bp.post("/api/uploads")
def upload_file():
    """上传文件：multipart 字段 file，任意类型。

    返回 data：url（绝对地址，发给中间方）、path（相对路径，本地预览）、
    file_name（原始文件名）、size（字节）。
    """
    user = request_user()
    if user is None:
        return jsonify(code=401, msg="登录已失效，请重新登录"), 401
    blocked = must_change_guard(user)
    if blocked is not None:
        return blocked

    file = request.files.get("file")
    if file is None or not file.filename:
        return jsonify(code=400, msg="缺少文件（multipart 字段 file）"), 400
    blob = file.read()
    if not blob:
        return jsonify(code=400, msg="文件内容为空"), 400
    if len(blob) > UPLOAD_MAX_BYTES:
        return jsonify(code=400, msg=f"文件超过 {UPLOAD_MAX_BYTES // (1024 * 1024)}MB 上限"), 400

    stored = uuid4().hex + _safe_ext(file.filename, file.mimetype)
    _uploads_dir().mkdir(parents=True, exist_ok=True)
    (_uploads_dir() / stored).write_bytes(blob)

    path = f"/media/uploads/{stored}"
    base = PUBLIC_BASE_URL or request.url_root.rstrip("/")
    log_action(AuditModule.SYNC, "上传文件", file.filename, detail=f"{stored} {len(blob)}B")
    return jsonify(code=0, msg="success", data={
        "url": base + path,
        "path": path,
        "file_name": file.filename,
        "size": len(blob),
    })


@bp.get("/media/uploads/<name>")
def download_upload(name):
    """上传文件下载：不鉴权（中间方按 url 直接拉），uuid 文件名不可猜测。"""
    if not _NAME_RE.match(name or ""):
        return jsonify(code=404, msg="文件不存在"), 404
    path = _uploads_dir() / name
    if not path.is_file():
        return jsonify(code=404, msg="文件不存在"), 404
    resp = send_file(path, mimetype=mimetypes.guess_type(name)[0] or "application/octet-stream",
                     conditional=True, as_attachment=True, download_name=name)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp
