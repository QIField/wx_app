"""自定义铃声端点单测：双重校验、数量上限、归属隔离、软删除、无鉴权播放。"""
import io
import tempfile
from pathlib import Path

from backend.api import ringtones as ringtones_api
from backend.models.audit_log import AuditLog
from backend.models.ringtone import UserRingtone
from backend.models.user import ROLE_AGENT, User
from backend.services.audit import AuditModule

from backend.tests.conftest import login_headers, make_user

# 各格式最小有效文件头（magic number 真实形态）
MP3_ID3 = b"ID3\x03\x00" + b"\x00" * 16
MP3_SYNC = b"\xff\xfb\x90\x44" + b"\x00" * 16
WAV = b"RIFF\x24\x08\x00\x00WAVEfmt " + b"\x00" * 16
M4A = b"\x00\x00\x00\x18ftypM4A \x00" + b"\x00" * 16
OGG = b"OggS\x00\x02\x00\x00" + b"\x00" * 16


def _tmp_media(monkeypatch):
    """把铃声落盘目录指到临时目录，避免污染 backend/media。"""
    tmp = Path(tempfile.mkdtemp())
    monkeypatch.setattr(ringtones_api, "MEDIA_DIR", tmp)
    return tmp


def _upload(client, filename, content):
    return client.post(
        "/api/ringtones",
        data={"file": (io.BytesIO(content), filename)},
        content_type="multipart/form-data",
    )


def db_row(rid):
    """按 id 取铃声行（含软删除行）。"""
    from backend.extensions import db

    return db.session.get(UserRingtone, rid)


def test_upload_requires_login(app):
    """没带令牌 401（require_role 兜底）。"""
    assert app.test_client().post("/api/ringtones").status_code == 401


def test_upload_mp3_ok_and_playable(app, client, monkeypatch):
    """上传 MP3：uuid 命名落盘、返回 url/name/size/fmt；无鉴权可播放且带 nosniff。"""
    tmp = _tmp_media(monkeypatch)

    resp = _upload(client, "我的铃声音.mp3", MP3_ID3)

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["name"] == "我的铃声音"  # 展示名 = 文件主名
    assert data["fmt"] == "mp3"
    assert data["size"] == len(MP3_ID3)
    assert data["url"].startswith("/media/ringtones/")
    stored = tmp / "ringtones" / data["url"].rsplit("/", 1)[1]
    assert stored.is_file() and stored.read_bytes() == MP3_ID3

    got = app.test_client().get(data["url"])  # <audio> 场景：不带令牌直接拉
    assert got.status_code == 200
    assert got.data == MP3_ID3
    assert got.headers["X-Content-Type-Options"] == "nosniff"


def test_upload_all_formats(client, monkeypatch):
    """四种白名单格式都能通过 magic number 校验。"""
    _tmp_media(monkeypatch)
    for fn, blob in (("a.mp3", MP3_SYNC), ("b.wav", WAV), ("c.m4a", M4A), ("d.ogg", OGG)):
        assert _upload(client, fn, blob).status_code == 200
    assert len(client.get("/api/ringtones").get_json()["data"]) == 4


def test_upload_rejects_bad_ext_and_content(client, monkeypatch):
    """格式白名单拒绝 + magic number 拒绝伪造扩展名 + 空文件拒绝。"""
    _tmp_media(monkeypatch)

    assert _upload(client, "song.txt", b"text").status_code == 400  # 格式不在白名单
    assert _upload(client, "noext", MP3_ID3).status_code == 400  # 无扩展名
    assert _upload(client, "fake.mp3", b"\x89PNG-fake").status_code == 400  # 内容与扩展名不符
    assert _upload(client, "empty.mp3", b"").status_code == 400  # 空文件
    assert UserRingtone.query.count() == 0


def test_upload_oversize_rejected(client, monkeypatch):
    """超过大小上限 400。"""
    _tmp_media(monkeypatch)
    monkeypatch.setattr(ringtones_api, "RINGTONE_MAX_BYTES", 10)

    assert _upload(client, "big.mp3", MP3_ID3).status_code == 400
    assert _upload(client, "ok.mp3", MP3_SYNC[:3]).status_code == 200  # ≤10B 的合法帧头


def test_upload_count_limit(client, monkeypatch):
    """每用户数量上限：超限 400，磁盘不留孤儿文件。"""
    tmp = _tmp_media(monkeypatch)
    monkeypatch.setattr(ringtones_api, "RINGTONE_MAX_COUNT", 2)

    assert _upload(client, "one.mp3", MP3_ID3).status_code == 200
    assert _upload(client, "two.mp3", MP3_SYNC).status_code == 200
    assert _upload(client, "three.mp3", WAV).status_code == 400
    files = list((tmp / "ringtones").iterdir())
    assert len(files) == 2  # 第三个未落盘


def test_upload_storage_full_rejected(client, monkeypatch):
    """磁盘剩余空间不足：400 + fail 审计日志。"""
    _tmp_media(monkeypatch)
    monkeypatch.setattr(ringtones_api, "RINGTONE_MIN_FREE_BYTES", 1 << 50)  # 1PB，必不满足

    resp = _upload(client, "x.mp3", MP3_ID3)
    assert resp.status_code == 400
    assert "存储空间不足" in resp.get_json()["msg"]
    assert AuditLog.query.filter_by(
        module=AuditModule.SYSTEM, action="上传铃声", result=AuditLog.RESULT_FAIL
    ).count() == 1


def test_list_scoped_to_owner(app, client, monkeypatch):
    """列表只返回当前登录人自己的铃声：别人的不可见。"""
    _tmp_media(monkeypatch)
    other = make_user(username="cs02", name="客服02", role=ROLE_AGENT)
    assert _upload(client, "mine.mp3", MP3_ID3).status_code == 200

    resp = app.test_client().post(
        "/api/ringtones",
        data={"file": (io.BytesIO(MP3_SYNC), "his.mp3")},
        content_type="multipart/form-data",
        headers=login_headers(other),
    )
    assert resp.status_code == 200

    mine = client.get("/api/ringtones").get_json()["data"]
    his = app.test_client().get("/api/ringtones", headers=login_headers(other)).get_json()["data"]
    assert [r["file_name"] for r in mine] == ["mine.mp3"]
    assert [r["file_name"] for r in his] == ["his.mp3"]


def test_delete_soft_and_scope(app, client, monkeypatch):
    """删除：软删除打标（行保留）、列表消失；删别人的/不存在 404。"""
    _tmp_media(monkeypatch)
    other = make_user(username="cs02", name="客服02", role=ROLE_AGENT)
    data = _upload(client, "mine.mp3", MP3_ID3).get_json()["data"]
    other_row = app.test_client().post(
        "/api/ringtones",
        data={"file": (io.BytesIO(MP3_SYNC), "his.mp3")},
        content_type="multipart/form-data",
        headers=login_headers(other),
    ).get_json()["data"]

    assert client.delete(f"/api/ringtones/{other_row['id']}").status_code == 404  # 不是自己的
    assert client.delete("/api/ringtones/9999").status_code == 404
    assert client.delete(f"/api/ringtones/{data['id']}").status_code == 200

    row = db_row(data["id"])
    assert row is not None and row.is_deleted  # 软删除：行还在
    assert client.get("/api/ringtones").get_json()["data"] == []  # 列表不再返回
    assert client.delete(f"/api/ringtones/{data['id']}").status_code == 404  # 重复删 404


def test_download_name_guard(app, client, monkeypatch):
    """播放路由：名字不符合 uuid+白名单规则（含穿越尝试）一律 404。"""
    _tmp_media(monkeypatch)
    bare = app.test_client()

    for bad in ("../etc/passwd", "a.txt", "a.mp3", "x" * 33):
        assert bare.get(f"/media/ringtones/{bad}").status_code == 404
    assert bare.get(f"/media/ringtones/{'a' * 32}.mp3").status_code == 404  # 名字合法但文件不存在
