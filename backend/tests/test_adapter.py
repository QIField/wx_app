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


class FakeBytesResp:
    def __init__(self, content, content_type="application/octet-stream"):
        self.content = content
        self.headers = {"Content-Type": content_type}

    def raise_for_status(self):
        return None


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


def test_call_download_two_steps(monkeypatch):
    """实测流程：POST 拿 JSON 里的 fileUrl，再 GET 该地址拉文件字节。"""
    captured = {}

    def fake_post(url, data=None, timeout=None):
        captured["post_data"] = data
        return FakeResp({"code": 0, "msg": "success",
                         "data": {"ret": 200, "msg": "操作成功",
                                  "data": {"fileUrl": "https://cdn/x?sig=1"}}})

    def fake_get(url, timeout=None):
        captured["get_url"] = url
        return FakeBytesResp(b"FILEBYTES", "application/octet-stream")

    monkeypatch.setattr(client.requests, "post", fake_post)
    monkeypatch.setattr(client.requests, "get", fake_get)
    data, ctype = client.call_download("messag_api", "get_download_image",
                                       {"xml": "<msg/>", "img_type": 2}, openid="dev01")

    assert captured["post_data"]["openid"] == "dev01"
    assert captured["post_data"]["img_type"] == 2
    assert captured["get_url"] == "https://cdn/x?sig=1"
    assert data == b"FILEBYTES"
    assert ctype == "application/octet-stream"  # CDN 类型不可信，透传给上层按魔数判断


def test_call_download_emoji_uses_url_field(monkeypatch):
    """表情接口的文件地址字段是 url 而非 fileUrl（实测差异）。"""
    def fake_post(url, data=None, timeout=None):
        return FakeResp({"code": 0, "data": {"ret": 200, "msg": "操作成功",
                                             "data": {"url": "https://qq/emoji"}}})

    monkeypatch.setattr(client.requests, "post", fake_post)
    monkeypatch.setattr(client.requests, "get",
                        lambda url, timeout=None: FakeBytesResp(b"EMOJI"))
    data, _ = client.call_download("messag_api", "get_download_emoji", {"emoji_md5": "m"})
    assert data == b"EMOJI"


def test_call_download_business_error_raises(monkeypatch):
    """ret != 200 要抛 MiddleApiError（如 ret:-1 请求超时）。"""
    def fake_post(url, data=None, timeout=None):
        return FakeResp({"code": 0, "data": {"ret": -1, "msg": "请求超时", "data": None}})

    monkeypatch.setattr(client.requests, "post", fake_post)
    with pytest.raises(MiddleApiError) as exc_info:
        client.call_download("messag_api", "get_download_file", {"xml": "<msg/>"})
    assert exc_info.value.msg == "请求超时"


def test_call_download_missing_url_raises(monkeypatch):
    """ret=200 但没带文件地址也要抛错，不能返回空字节。"""
    def fake_post(url, data=None, timeout=None):
        return FakeResp({"code": 0, "data": {"ret": 200, "msg": "操作成功", "data": {}}})

    monkeypatch.setattr(client.requests, "post", fake_post)
    with pytest.raises(MiddleApiError) as exc_info:
        client.call_download("messag_api", "get_download_video", {"xml": "<msg/>"})
    assert "未返回文件地址" in exc_info.value.msg
