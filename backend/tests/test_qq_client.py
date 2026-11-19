"""快捷报价客户端单测：form 组装 / code 校验 / 401·500·非 JSON 兜底 / 超时。

网络层全 mock（monkeypatch requests.post），不触真实服务；
真实链路验证为独立的手工步骤（阶段 1 验收记录见 docs/auto-quote-plan.md）。
"""
import json

import pytest
import requests

from backend import qq_client


class FakeResp:
    def __init__(self, status=200, body=None, text=""):
        self.status_code = status
        self._body = body
        self.text = text if text else (json.dumps(body) if body is not None else "")

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


@pytest.fixture()
def openid(monkeypatch):
    monkeypatch.setattr(qq_client, "QQ_OPENID", "test-openid")


@pytest.fixture()
def capture(monkeypatch):
    """替换 requests.post，记录 (url, data) 并返回预设响应。"""
    holder = {}

    def _install(resp):
        def fake_post(url, data=None, timeout=None):
            holder["url"] = url
            holder["data"] = data
            holder["timeout"] = timeout
            return resp
        monkeypatch.setattr(qq_client.requests, "post", fake_post)
        return holder

    return _install


def test_form_encoding_and_endpoint_url(openid, capture):
    """端点拼接、openid 注入、None 参数过滤、form 传参（非 JSON body）。"""
    holder = capture(FakeResp(body={"code": 0, "msg": "success", "data": {"ok": 1}}))
    data = qq_client.call("partno", {"vin": "WBAWX3100G0L69597", "originalPartsNos": "节温器", "extra": None})
    assert data == {"ok": 1}
    assert holder["url"].endswith("/decoding_api/partno")
    assert holder["data"]["openid"] == "test-openid"
    assert holder["data"]["vin"] == "WBAWX3100G0L69597"
    assert "extra" not in holder["data"]


def test_openid_missing_raises(openid, capture, monkeypatch):
    """未配置 openid → 明确报错，不发出请求。"""
    monkeypatch.setattr(qq_client, "QQ_OPENID", "")
    with pytest.raises(qq_client.QuoteApiError, match="openid"):
        qq_client.call("vininfo", {"vin": "X"})
    assert "url" not in capture(FakeResp(body={"code": 0, "data": None}))


def test_success_returns_data(openid, capture):
    capture(FakeResp(body={"code": 0, "msg": "success", "data": [1, 2]}))
    assert qq_client.call("productList", {"number": "1665000075"}) == [1, 2]


def test_auth_401(openid, capture):
    """401 带 JSON msg → 错误消息透出。"""
    capture(FakeResp(status=401, body={"code": 401, "msg": "openid不存在或已关闭"}))
    with pytest.raises(qq_client.QuoteApiError, match="openid不存在或已关闭"):
        qq_client.call("vininfo", {"vin": "X"})


def test_upstream_500_html(openid, capture):
    """上游异常返回 500 Flask HTML（非 JSON）→ 统一兜底不崩。"""
    capture(FakeResp(status=500, text="<html>Internal Server Error</html>"))
    with pytest.raises(qq_client.QuoteApiError, match="HTTP 500"):
        qq_client.call("jqr", {"number": "1665000075"})


def test_non_json_200(openid, capture):
    """200 但 body 非 JSON → 兜底。"""
    capture(FakeResp(status=200, text="<html>ok</html>"))
    with pytest.raises(qq_client.QuoteApiError, match="非 JSON"):
        qq_client.call("zpy", {"number": "1665000075"})


def test_business_nonzero_code(openid, capture):
    """HTTP 200 但 code!=0 → 业务失败透出 msg。"""
    capture(FakeResp(body={"code": 500, "msg": "上游超时", "data": None}))
    with pytest.raises(qq_client.QuoteApiError, match="上游超时"):
        qq_client.call("vininfo", {"vin": "X"})


def test_timeout_and_unreachable(openid, capture, monkeypatch):
    """超时 / 网络异常 → 统一 QuoteApiError。"""

    def fake_timeout(url, data=None, timeout=None):
        raise requests.Timeout()
    monkeypatch.setattr(qq_client.requests, "post", fake_timeout)
    with pytest.raises(qq_client.QuoteApiError, match="超时"):
        qq_client.call("vininfo", {"vin": "X"})

    def fake_conn(url, data=None, timeout=None):
        raise requests.ConnectionError("refused")
    monkeypatch.setattr(qq_client.requests, "post", fake_conn)
    with pytest.raises(qq_client.QuoteApiError, match="不可达"):
        qq_client.call("vininfo", {"vin": "X"})


def test_unknown_endpoint(openid, capture):
    with pytest.raises(qq_client.QuoteApiError, match="未知"):
        qq_client.call("nope", {})


def test_extract_parts_serializes_chinese(openid, capture):
    """chat_content 序列化：不带 ensure_ascii=False，中文字符统一 \\uXXXX 转义（跟随服务方接口规定）。"""
    holder = capture(FakeResp(body={"code": 0, "data": {"list": []}}))
    content = [{"type": "input_text", "text": "2026-11-17 10:00:00【老王】：节温器多少钱"}]
    qq_client.extract_parts(content)
    sent = holder["data"]["chat_content"]
    assert "\\u3010\\u8001\\u738b\\u3011" in sent         # 【老王】变成 \\uXXXX
    assert json.loads(sent)[0]["text"].endswith("节温器多少钱")  # 解析后仍正确


def test_convenience_wrappers_map_endpoints(openid, capture):
    """便捷包装 → 正确端点与参数（抽查 4 个）。"""
    holder = capture(FakeResp(body={"code": 0, "data": None}))

    qq_client.ocr_vin("http://img/1.jpg")                       # tx 优先
    assert holder["url"].endswith("/ocr_api/tx_vin")
    qq_client.ocr_vin("http://img/1.jpg", prefer_tx=False)      # local 兜底
    assert holder["url"].endswith("/ocr_api/local_vin")
    qq_client.purchase_history("1665000075", page=2, limit=5)
    assert holder["data"] == {"number": "1665000075", "page": 2, "limit": 5, "openid": "test-openid"}
    qq_client.part_images_list("VIN", "10097483", "1665000075", "BMW")
    assert holder["data"]["carBrandId"] == "BMW"
    qq_client.vininfo("WBAWX3100G0L69597")
    assert holder["url"].endswith("/decoding_api/vininfo")
