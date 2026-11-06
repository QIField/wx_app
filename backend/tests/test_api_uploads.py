"""uploads 端点流程：鉴权 → 落盘 uuid 文件名 → 返回 url/path → 无鉴权下载（名字强校验）。"""
import io
import tempfile
from pathlib import Path

from backend.api import uploads as uploads_api


def _tmp_media(monkeypatch):
    """把上传目录指到临时目录，避免污染 backend/media。"""
    tmp = Path(tempfile.mkdtemp())
    monkeypatch.setattr(uploads_api, "MEDIA_DIR", tmp)
    return tmp


def _upload(client, filename="测试.png", content=b"\x89PNG-fake"):
    return client.post(
        "/api/uploads",
        data={"file": (io.BytesIO(content), filename)},
        content_type="multipart/form-data",
    )


def test_upload_requires_login(app):
    """没带令牌 401（用不带令牌的裸客户端）。"""
    resp = app.test_client().post("/api/uploads")
    assert resp.status_code == 401


def test_upload_saves_uuid_file_and_returns_urls(app, client, monkeypatch):
    """上传成功：uuid 命名落盘，url 绝对地址，path 相对路径；下载路由按 path 可拉。"""
    tmp = _tmp_media(monkeypatch)
    monkeypatch.setattr(uploads_api, "PUBLIC_BASE_URL", "https://pub.example.com")

    resp = _upload(client)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["file_name"] == "测试.png"
    assert data["size"] == len(b"\x89PNG-fake")
    assert data["url"].startswith("https://pub.example.com/media/uploads/")
    assert data["path"].startswith("/media/uploads/")
    stored = tmp / "uploads" / data["path"].rsplit("/", 1)[1]
    assert stored.is_file() and stored.read_bytes() == b"\x89PNG-fake"
    # 中间方视角：不带令牌直接 GET 也能拉到
    bare = app.test_client()
    got = bare.get(data["path"])
    assert got.status_code == 200
    assert got.data == b"\x89PNG-fake"


def test_upload_without_public_base_uses_url_root(app, client, monkeypatch):
    """没配 PUBLIC_BASE_URL：用请求 url_root 兜底拼绝对地址。"""
    _tmp_media(monkeypatch)
    monkeypatch.setattr(uploads_api, "PUBLIC_BASE_URL", "")

    data = _upload(client).get_json()["data"]
    assert data["url"].startswith("http://localhost/")


def test_upload_rejects_empty_and_oversize(app, client, monkeypatch):
    """空内容与超上限都 400。"""
    _tmp_media(monkeypatch)
    monkeypatch.setattr(uploads_api, "UPLOAD_MAX_BYTES", 10)

    assert _upload(client, content=b"").status_code == 400
    assert _upload(client, content=b"x" * 11).status_code == 400
    assert _upload(client, content=b"1234567890").status_code == 200


def test_upload_ext_sanitized(app, client, monkeypatch):
    """扩展名只留字母数字；无扩展名按 Content-Type 推。"""
    _tmp_media(monkeypatch)

    data = _upload(client, filename="a.b..h!!ack").get_json()["data"]
    assert data["path"].endswith(".hack")
    data = _upload(client, filename="noext", content=b"x").get_json()["data"]
    assert data["path"].rsplit(".", 1)[1]  # 有扩展名（推不出来也有 .bin 兜底）


def test_download_bad_name_404(app, client, monkeypatch):
    """下载路由：名字不符合 uuid 规则（含穿越尝试）一律 404；格式对但不存在也 404。"""
    _tmp_media(monkeypatch)
    bare = app.test_client()

    for bad in ("../etc/passwd", "a.png", "x" * 33):
        assert bare.get(f"/media/uploads/{bad}").status_code == 404
    assert bare.get(f"/media/uploads/{'a' * 32}.png").status_code == 404
