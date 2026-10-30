"""适配器 client 单测：mock requests，验证表单参数与错误处理。"""
import pytest

from backend.adapter import client
from backend.adapter.client import MiddleApiError


class FakeResp:
    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self._body


def test_call_sends_common_params(monkeypatch):
    """公共参数 openid/uuid 必须带上，外部传入的 uuid 优先。"""
    captured = {}

    def fake_post(url, data=None, timeout=None):
        captured["url"] = url
        captured["data"] = data
        return FakeResp({"code": 0, "msg": "success"})

    monkeypatch.setattr(client.requests, "post", fake_post)
    body = client.call("send_api", "post_text_message", {"to_wxid": "wxid_x"},
                       uuid="u-1", openid="dev01")

    assert captured["url"].endswith("/wx_app/send_api/post_text_message")
    assert captured["data"]["openid"] == "dev01"  # 多设备后按调用方传入
    assert captured["data"]["uuid"] == "u-1"
    assert captured["data"]["to_wxid"] == "wxid_x"
    assert body["code"] == 0


def test_call_generates_uuid_when_missing(monkeypatch):
    """不传 uuid 时自动生成。"""
    captured = {}

    def fake_post(url, data=None, timeout=None):
        captured["data"] = data
        return FakeResp({"code": 0, "msg": "success"})

    monkeypatch.setattr(client.requests, "post", fake_post)
    client.call("login_api", "check_online")

    assert captured["data"]["uuid"]  # 有值即可，具体值不关心


def test_call_raises_on_error_code(monkeypatch):
    """code != 0 要抛 MiddleApiError 并带上 msg。"""

    def fake_post(url, data=None, timeout=None):
        return FakeResp({"code": 1, "msg": "设备离线"})

    monkeypatch.setattr(client.requests, "post", fake_post)
    with pytest.raises(MiddleApiError) as exc_info:
        client.call("login_api", "check_online")
    assert exc_info.value.msg == "设备离线"


def test_call_wraps_network_error(monkeypatch):
    """网络异常要包成 MiddleApiError，不能裸抛 requests 异常。"""
    import requests as requests_lib

    def fake_post(url, data=None, timeout=None):
        raise requests_lib.ConnectionError("连不上")

    monkeypatch.setattr(client.requests, "post", fake_post)
    with pytest.raises(MiddleApiError):
        client.call("login_api", "check_online")
