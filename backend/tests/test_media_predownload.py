"""同步预下载单测：新媒体入库即串行拉回缓存；失败跳过；已缓存不重复下载。"""
from datetime import datetime

import pytest

from backend.extensions import db
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.services import media_fetch
from backend.sync import media_predownload


@pytest.fixture()
def conv(app):
    """设备 dev01 → 客户 wxid_customer 的会话。"""
    c = Conversation(openid="dev01", wxid="wxid_customer", chat_type=1, name="张师傅")
    db.session.add(c)
    db.session.commit()
    return c


def make_media_msg(conv_id, msg_type, content, middle_msg_id="m1"):
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


def make_pushed(msg):
    """模拟 message_sync._save_message 返回的推送字典形状。"""
    return [{
        "message_id": msg.id,
        "conversation_id": msg.conversation_id,
        "direction": Message.DIR_IN,
        "msg_type": msg.msg_type,
        "sender_wxid": "wxid_customer",
        "sender_name": "张师傅",
        "content": msg.content,
        "payload": {},
        "create_time": msg.create_time,
    }]


def mock_download(monkeypatch, data=b"MEDIABYTES", content_type="image/png"):
    """替换中间方下载调用并记录每次参数。"""
    calls = []

    def fake(module, action, params=None, openid=""):
        calls.append({"action": action, "params": params, "openid": openid})
        return data, content_type, ""

    monkeypatch.setattr(media_fetch.middle_client, "call_download_with_url", fake)
    return calls


def test_predownload_image_returns_first_tier(app, conv, tmp_path, monkeypatch):
    """图片预下载：1 档高清成功即停，每条只落一张。"""
    monkeypatch.setattr(media_fetch, "MEDIA_DIR", tmp_path)
    msg = make_media_msg(conv.id, Message.MSG_IMAGE, '<msg><img aeskey="k" /></msg>')
    calls = mock_download(monkeypatch)

    media_predownload.predownload_media(make_pushed(msg))

    assert [c["params"]["img_type"] for c in calls] == [1]  # 成功就不再请求 2、3 档
    assert all(c["action"] == "get_download_image" for c in calls)
    assert calls[0]["openid"] == "dev01"
    assert len(list(media_fetch.cache_dir_for(msg).glob(f"{msg.id}*.*"))) == 1


def test_predownload_image_falls_back_to_next_tier(app, conv, tmp_path, monkeypatch):
    """1 档失败自动降级 2 档：按 1→2 顺序请求，2 档成功即停。"""
    from backend.adapter.client import MiddleApiError

    monkeypatch.setattr(media_fetch, "MEDIA_DIR", tmp_path)
    msg = make_media_msg(conv.id, Message.MSG_IMAGE, '<msg><img aeskey="k" /></msg>')
    calls = []

    def fake(module, action, params=None, openid=""):
        calls.append(params["img_type"])
        if params["img_type"] == 1:
            raise MiddleApiError("高清档不可用")
        return b"\x89PNG\r\n\x1a\nDATA", "image/png", ""

    monkeypatch.setattr(media_fetch.middle_client, "call_download_with_url", fake)

    media_predownload.predownload_media(make_pushed(msg))

    assert calls == [1, 2]
    assert len(list(media_fetch.cache_dir_for(msg).glob(f"{msg.id}*.*"))) == 1


def test_predownload_skips_text_and_cached(app, conv, tmp_path, monkeypatch):
    """文本消息不触发下载；已有缓存的消息不再调中间方。"""
    monkeypatch.setattr(media_fetch, "MEDIA_DIR", tmp_path)
    text = make_media_msg(conv.id, Message.MSG_TEXT, "你好")
    cached = make_media_msg(conv.id, Message.MSG_IMAGE, '<msg><img aeskey="k" /></msg>')
    cached_dir = media_fetch.cache_dir_for(cached)
    cached_dir.mkdir(parents=True, exist_ok=True)
    (cached_dir / f"{cached.id}_q1.png").write_bytes(b"OLD")  # 旧版按档位拆分的文件也算已缓存
    calls = mock_download(monkeypatch)

    media_predownload.predownload_media(make_pushed(text) + make_pushed(cached))

    assert calls == []


def test_predownload_failure_continues(app, conv, tmp_path, monkeypatch):
    """单条下载失败只跳过该条，后续消息照常预下载。"""
    from backend.adapter.client import MiddleApiError

    monkeypatch.setattr(media_fetch, "MEDIA_DIR", tmp_path)
    bad = make_media_msg(conv.id, Message.MSG_VIDEO, '<msg><videomsg aeskey="k" /></msg>')
    good = make_media_msg(conv.id, Message.MSG_EMOJI, '<msg><emoji md5="m1" /></msg>')

    def flaky(module, action, params=None, openid=""):
        if action == "get_download_video":
            raise MiddleApiError("已达上限")
        return b"GIF89", "image/gif", ""

    monkeypatch.setattr(media_fetch.middle_client, "call_download_with_url", flaky)

    media_predownload.predownload_media(make_pushed(bad) + make_pushed(good))

    assert list(media_fetch.cache_dir_for(good).glob(f"{good.id}.*"))     # 失败之后的表情照常落盘
    assert not list(media_fetch.cache_dir_for(bad).glob(f"{bad.id}.*"))  # 失败的不落盘
