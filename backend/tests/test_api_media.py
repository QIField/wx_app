"""媒体端点单测：鉴权 / 数据隔离 / 缓存 / 中间方下载参数。

media 端点流程：鉴权 → 查缓存 → 未命中调 get_download_xxx（中间方负责解密）→ 落盘 → 回文件流。
"""
from datetime import datetime

import pytest

from backend.extensions import db
from backend.models.message import Message
from backend.tests.conftest import login_headers, make_user

from backend.services import media_fetch
from backend.models.conversation import Conversation


@pytest.fixture()
def media_dir(tmp_path, monkeypatch):
    """媒体缓存指到临时目录，避免污染 backend/media。"""
    monkeypatch.setattr(media_fetch, "MEDIA_DIR", tmp_path)
    return tmp_path


@pytest.fixture()
def conv(app):
    """设备 dev01 → 客户 wxid_customer 的会话。"""
    c = Conversation(openid="dev01", wxid="wxid_customer", chat_type=1, name="张师傅")
    db.session.add(c)
    db.session.commit()
    return c


def make_message(conv_id, msg_type, content, middle_msg_id="m1"):
    msg = Message(
        conversation_id=conv_id,
        msg_type=msg_type,
        direction=Message.DIR_IN,
        sender_wxid="wxid_customer",
        sender_name="张师傅",
        content=content,
        middle_msg_id=middle_msg_id,
        create_time=datetime.now(),
    )
    db.session.add(msg)
    db.session.commit()
    return msg


def cache_dir(tmp_path, msg):
    """消息对应的日期缓存目录（media_fetch 按消息 create_time 分目录）。"""
    return tmp_path / msg.create_time.strftime("%Y-%m-%d")


def mock_download(monkeypatch, data=b"MEDIABYTES", content_type="image/png"):
    """替换中间方下载调用并记录参数。"""
    captured = {}

    def fake(module, action, params=None, openid=""):
        captured.update(module=module, action=action, params=params, openid=openid)
        return data, content_type, ""

    monkeypatch.setattr(media_fetch.middle_client, "call_download_with_url", fake)
    return captured


def test_media_requires_login(app, client, conv):
    """无有效令牌（头和 ?token= 都无效）：401。"""
    msg = make_message(conv.id, Message.MSG_IMAGE, "<msg><img aeskey=\"k\" /></msg>")

    resp = client.get(f"/api/messages/{msg.id}/media",
                      headers={"Authorization": "Bearer junk"})

    assert resp.status_code == 401


def test_media_image_demo_placeholder_and_cache(app, client, conv, media_dir, monkeypatch):
    """演示模式：返回占位 PNG 并落盘；第二次命中缓存不再调中间方。"""
    from backend.adapter import client as middle_client

    monkeypatch.setattr(middle_client, "DEMO_MODE", True)
    msg = make_message(conv.id, Message.MSG_IMAGE, "<msg><img aeskey=\"k\" /></msg>")

    first = client.get(f"/api/messages/{msg.id}/media")
    assert first.status_code == 200
    assert first.headers["Content-Type"].startswith("image/png")
    files = list(cache_dir(media_dir, msg).glob(f"{msg.id}_q*.*"))  # 图片缓存带 _q{清晰度名次} 后缀
    assert len(files) == 3  # 三档全部下载并按清晰度排名落盘

    def must_not_call(*a, **k):  # 缓存命中就不该再碰中间方
        raise AssertionError("cache hit should not call middle platform")

    monkeypatch.setattr(media_fetch.middle_client, "call_download_with_url", must_not_call)
    second = client.get(f"/api/messages/{msg.id}/media")

    assert second.status_code == 200
    assert second.data == first.data


def test_media_voice_download_params(app, client, conv, media_dir, monkeypatch):
    """语音：调 get_download_voice，参数 xml + msg_id；返回字节与类型透传。"""
    xml = '<msg><voicemsg voicelength="3000" aeskey="k" /></msg>'
    msg = make_message(conv.id, Message.MSG_VOICE, xml, middle_msg_id="m99")
    captured = mock_download(monkeypatch, data=b"AMRDATA", content_type="audio/amr")

    resp = client.get(f"/api/messages/{msg.id}/media")

    assert resp.status_code == 200
    assert resp.data == b"AMRDATA"
    assert resp.headers["Content-Type"].startswith("audio/amr")
    assert captured["module"] == "messag_api"
    assert captured["action"] == "get_download_voice"
    assert captured["params"] == {"xml": xml, "msg_id": "m99"}
    assert captured["openid"] == "dev01"
    assert list(cache_dir(media_dir, msg).glob(f"{msg.id}.amr"))


def test_media_emoji_md5_from_xml(app, client, conv, media_dir, monkeypatch):
    """表情：md5 从 content xml 属性里解析，参数只传 emoji_md5。"""
    msg = make_message(conv.id, Message.MSG_EMOJI,
                       '<msg><emoji md5="abc123" len="123" /></msg>')
    captured = mock_download(monkeypatch, content_type="image/gif")

    resp = client.get(f"/api/messages/{msg.id}/media")

    assert resp.status_code == 200
    assert captured["action"] == "get_download_emoji"
    assert captured["params"] == {"emoji_md5": "abc123"}


def test_media_image_img_type_variants(app, client, conv, media_dir, monkeypatch):
    """图片：img_type 是清晰度名次（默认 3）；首次无论取哪档都会先备齐 1/2/3。"""
    msg = make_message(conv.id, Message.MSG_IMAGE, "<msg><img aeskey=\"k\" /></msg>")
    calls = []

    def fake(module, action, params=None, openid=""):
        calls.append(dict(params))
        return b"MEDIABYTES", "image/png", ""

    monkeypatch.setattr(media_fetch.middle_client, "call_download_with_url", fake)

    assert client.get(f"/api/messages/{msg.id}/media").status_code == 200
    assert [c["img_type"] for c in calls] == [1, 2, 3]  # 三档全部请求
    assert len(list(cache_dir(media_dir, msg).glob(f"{msg.id}_q*.*"))) == 3

    assert client.get(f"/api/messages/{msg.id}/media?img_type=9").status_code == 200
    assert client.get(f"/api/messages/{msg.id}/media?img_type=1").status_code == 200
    assert len(calls) == 3  # 缓存齐全后不再重复下载


def test_image_tiers_ranked_by_pixels(app, client, conv, media_dir, monkeypatch):
    """三档按实际像素排名：故意让 2 档最大、1 档最小，q1 仍必须是像素最大的那份。"""
    import io

    from PIL import Image

    def png(size, color):
        buf = io.BytesIO()
        Image.new("RGB", (size, size), color).save(buf, format="PNG")
        return buf.getvalue()

    payloads = {1: png(10, "red"), 2: png(40, "green"), 3: png(20, "blue")}
    calls = []

    def fake(module, action, params=None, openid=""):
        calls.append(params["img_type"])
        return payloads[params["img_type"]], "image/png", ""

    monkeypatch.setattr(media_fetch.middle_client, "call_download_with_url", fake)
    msg = make_message(conv.id, Message.MSG_IMAGE, "<msg><img aeskey=\"k\" /></msg>")

    resp = client.get(f"/api/messages/{msg.id}/media?img_type=3")  # 请求缩略图也要先备齐三档
    assert resp.status_code == 200
    assert sorted(calls) == [1, 2, 3]

    for rank, side in ((1, 40), (2, 20), (3, 10)):
        with Image.open(media_fetch.cached_path(msg, rank)) as im:
            assert im.size == (side, side)

    big = client.get(f"/api/messages/{msg.id}/media?img_type=1")
    assert big.status_code == 200
    with Image.open(io.BytesIO(big.data)) as im:
        assert im.size == (40, 40)  # 最清档来自原始 2 档


def test_media_text_type_rejected(app, client, conv):
    """文本消息没有媒体：400。"""
    msg = make_message(conv.id, Message.MSG_TEXT, "你好")

    resp = client.get(f"/api/messages/{msg.id}/media")

    assert resp.status_code == 400


def test_media_sniff_real_type(app, client, conv, media_dir, monkeypatch):
    """实测 CDN Content-Type 不可信：按魔数识别 JPEG，响应与缓存扩展名都纠正。"""
    jpeg = b"\xff\xd8\xff\xe0" + b"JPEGDATA"
    mock_download(monkeypatch, data=jpeg, content_type="application/octet-stream")
    msg = make_message(conv.id, Message.MSG_IMAGE, "<msg><img aeskey=\"k\" /></msg>")

    resp = client.get(f"/api/messages/{msg.id}/media")

    assert resp.status_code == 200
    assert resp.headers["Content-Type"].startswith("image/jpeg")
    assert len(list(cache_dir(media_dir, msg).glob(f"{msg.id}_q*.jpg"))) == 3


def test_media_cross_device_isolated(app, client, conv, media_dir, monkeypatch):
    """数据隔离：绑定 dev02 的账号拉不到 dev01 会话的媒体（404）。"""
    other = make_user(username="cs02", name="客服02", open_ids=["dev02"])
    msg = make_message(conv.id, Message.MSG_IMAGE, "<msg><img aeskey=\"k\" /></msg>")
    mock_download(monkeypatch)

    resp = client.get(f"/api/messages/{msg.id}/media", headers=login_headers(other))

    assert resp.status_code == 404


def test_media_download_failure_audited(app, client, conv, media_dir, monkeypatch):
    """中间方下载失败：502 + 记一条失败审计日志。"""
    from backend.adapter.client import MiddleApiError
    from backend.models.audit_log import AuditLog

    def boom(module, action, params=None, openid=""):
        raise MiddleApiError("设备离线")

    monkeypatch.setattr(media_fetch.middle_client, "call_download_with_url", boom)
    msg = make_message(conv.id, Message.MSG_VIDEO, "<msg><videomsg aeskey=\"k\" /></msg>")

    resp = client.get(f"/api/messages/{msg.id}/media")

    assert resp.status_code == 502
    log = AuditLog.query.one()
    assert log.result == AuditLog.RESULT_FAIL
    assert log.action == "媒体下载"


def test_media_json_payload_not_cached(app, client, conv, media_dir, monkeypatch):
    """错误报文被当文件拉回（如「已达上限」JSON）：502 且不落盘冒充媒体。"""
    body = '{"code":0,"data":{"msg":"已达上限","ret":50003},"msg":"success"}'.encode("utf-8")
    mock_download(monkeypatch, data=body, content_type="application/json")
    msg = make_message(conv.id, Message.MSG_IMAGE, "<msg><img aeskey=\"k\" /></msg>")

    resp = client.get(f"/api/messages/{msg.id}/media")

    assert resp.status_code == 502
    assert not list(media_dir.glob("*"))  # 不允许 .json 落进缓存目录


def test_download_serialized_per_device(app, conv, media_dir, monkeypatch):
    """同设备兜底下载排队串行：并发请求下中间方同时只有 1 个在途下载。"""
    import threading
    import time

    inflight = {"n": 0, "max": 0}
    guard = threading.Lock()

    def slow(module, action, params=None, openid=""):
        with guard:
            inflight["n"] += 1
            inflight["max"] = max(inflight["max"], inflight["n"])
        time.sleep(0.05)
        with guard:
            inflight["n"] -= 1
        return b"\xff\xd8\xff\xe0JPGDATA", "application/octet-stream", ""

    monkeypatch.setattr(media_fetch.middle_client, "call_download_with_url", slow)
    msgs = [
        make_message(conv.id, Message.MSG_IMAGE, '<msg><img aeskey="k" /></msg>',
                     middle_msg_id=f"m{i}")
        for i in range(4)
    ]

    def work(m):
        with app.app_context():
            media_fetch.fetch_and_cache(m)

    threads = [threading.Thread(target=work, args=(m,)) for m in msgs]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert inflight["max"] == 1  # 全程从未并发
    assert len(list(cache_dir(media_dir, msgs[0]).glob("*"))) == 12  # 每条图 3 档
