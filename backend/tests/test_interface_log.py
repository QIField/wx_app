"""接口调用日志单测：入站钩子 + 出站埋点（规范见 docs/interface-log.md）。"""
import json
from datetime import datetime, timedelta

import pytest
import requests as requests_lib

import backend.adapter.client as client_mod
from backend.extensions import db
from backend.models.access_log import AccessLog
from backend.models.middle_call_log import MiddleCallLog
from backend.services import middle_log
from backend.services.access_log import clean_expired as clean_access_expired
from backend.services.access_log import dumps_masked, is_exempt, mask_value
from backend.services.middle_log import clean_expired as clean_middle_expired


class FakeResp:
    """mock 中间方响应：status_code / json / text 可控。"""

    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.headers = {}
        self.content = b""

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests_lib.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        if self._payload is None:
            raise ValueError("No JSON")
        return self._payload


# ---------- 入站：记录 ----------

def test_access_log_records_request(client):
    resp = client.get("/api/conversations")
    assert resp.status_code == 200
    row = AccessLog.query.one()
    assert row.path == "/api/conversations"
    assert row.method == "GET"
    assert row.status_code == 200
    assert row.user_name == "客服01"
    assert row.user_id is not None
    assert row.duration_ms >= 0


def test_access_log_404_still_logged(app):
    """未登录请求也记录（含 404）；user 快照为空。"""
    app.test_client().get("/api/nope")
    row = AccessLog.query.one()
    assert row.status_code == 404
    assert row.user_name == ""


def test_access_log_crash_fallback(app):
    """未处理异常：after_request 不跑，teardown 兜底补记 500。"""

    @app.route("/boom")
    def boom():
        raise RuntimeError("炸了")

    with pytest.raises(RuntimeError):
        app.test_client().get("/boom")
    row = AccessLog.query.one()
    assert row.status_code == 500
    assert row.path == "/boom"


def test_access_log_records_org_snapshot(app):
    """登录人带组织时，入站日志记组织快照（方案 A：仅归属标记）。"""
    from backend.models.org import Org
    from backend.models.user import ROLE_AGENT, User
    from backend.tests.conftest import login_headers, make_user

    org = Org(name="佛山")
    db.session.add(org)
    db.session.commit()
    make_user(username="cs99", name="有组织", role=ROLE_AGENT, org_id=org.id)
    user = User.query.filter_by(username="cs99").one()

    app.test_client().get("/api/conversations", headers=login_headers(user))

    row = AccessLog.query.one()
    assert row.org_id == org.id
    assert row.org_name == "佛山"


# ---------- 入站：豁免 ----------

def test_access_log_exempt_paths(app):
    with app.test_client() as c:
        c.get("/api/health")
        c.options("/api/conversations")
    assert AccessLog.query.count() == 0


def test_is_exempt_rules():
    assert is_exempt("/api/health", "GET")
    assert is_exempt("/ws", "GET")
    assert is_exempt("/static/app.js", "GET")
    assert is_exempt("/api/conversations", "OPTIONS")
    assert not is_exempt("/api/media/1/image", "GET")  # 媒体接口不豁免
    assert not is_exempt("/api/conversations", "GET")


# ---------- 入站：脱敏 ----------

def test_access_log_masks_token_in_url_and_args(app):
    app.test_client().get("/api/conversations?token=abc123")
    row = AccessLog.query.one()
    assert "abc123" not in row.url
    assert "token=***" in row.url
    assert json.loads(row.args)["token"] == "***"


def test_access_log_masks_password_in_form(app):
    app.test_client().post("/api/auth/login",
                           json={"username": "cs01", "password": "secret123"})
    row = AccessLog.query.one()
    form = json.loads(row.form)
    assert form["password"] == "***"
    assert form["username"] == "cs01"


def test_mask_value_rules():
    data = {"password": "a", "Token": "b", "AUTHORIZATION": "c",
            "nested": {"password": "d", "ok": 1}, "list": [{"access_token": "e"}]}
    masked = mask_value(data)
    assert masked["password"] == "***"
    assert masked["Token"] == "***"
    assert masked["AUTHORIZATION"] == "***"
    assert masked["nested"] == {"password": "***", "ok": 1}
    assert masked["list"] == [{"access_token": "***"}]


def test_dumps_masked_truncates():
    assert len(dumps_masked({"k": "x" * 5000})) <= 2000
    assert dumps_masked(None) == ""


# ---------- 出站：四类场景 ----------

def test_middle_call_success(app, monkeypatch):
    monkeypatch.setattr("backend.adapter.client.requests.post",
                        lambda url, data, timeout: FakeResp(200, {"code": 0, "msg": "success"}))
    body = client_mod.call("login_api", "check_online", openid="dev01", uuid="u1")
    assert body["code"] == 0
    row = MiddleCallLog.query.one()
    assert row.success == 1
    assert row.resp_code == 0
    assert row.http_status == 200
    assert row.uuid == "u1"
    assert row.openid == "dev01"
    assert row.module == "login_api"
    assert row.user_id is None  # 定时任务/无登录人：姓名+组织快照为空
    assert row.user_name is None
    assert row.org_name is None


def test_middle_call_user_snapshot(app, monkeypatch):
    """姓名+组织快照规范：请求上下文有登录人时，出站日志抄录当时姓名+组织。"""
    from flask import request

    from backend.models.org import Org
    from backend.tests.conftest import make_user

    org = Org.query.filter_by(name="佛山").first() or Org(name="佛山")
    db.session.add(org)
    db.session.commit()
    user = make_user(name="客服01", org_id=org.id)
    monkeypatch.setattr("backend.adapter.client.requests.post",
                        lambda url, data, timeout: FakeResp(200, {"code": 0, "msg": "success"}))
    with app.test_request_context("/api/conversations"):
        request.current_user = user
        client_mod.call("send_api", "post_text", openid="dev01", uuid="u9")

    row = MiddleCallLog.query.one()
    assert row.user_id == user.id
    assert row.user_name == "客服01"
    assert row.org_name == "佛山"


def test_middle_call_business_code_fail(app, monkeypatch):
    monkeypatch.setattr("backend.adapter.client.requests.post",
                        lambda url, data, timeout: FakeResp(200, {"code": 500, "msg": "参数错误"}))
    with pytest.raises(client_mod.MiddleApiError):
        client_mod.call("send_api", "post_text", openid="dev01", uuid="u2")
    row = MiddleCallLog.query.one()
    assert row.success == 0
    assert row.resp_code == 500
    assert row.error_msg == "参数错误"


def test_middle_call_ret_fail(app, monkeypatch):
    """code=0 但 processing_result.ret=500（设备离线）：照记失败，ret 单独成列。"""
    payload = {"code": 0, "msg": "success",
               "data": [{"uuid": "u3",
                         "processing_result": json.dumps({"ret": 500, "msg": "设备已离线，appId:wx_x"})}]}
    monkeypatch.setattr("backend.adapter.client.requests.post",
                        lambda url, data, timeout: FakeResp(200, payload))
    body = client_mod.call("messag_api", "get_post_text_message", openid="dev01", uuid="u3")
    assert body["code"] == 0
    row = MiddleCallLog.query.one()
    assert row.success == 0
    assert row.ret == 500
    assert "设备已离线" in row.error_msg


def test_middle_call_http_error(app, monkeypatch):
    def boom(url, data, timeout):
        raise requests_lib.ConnectionError("connection refused")

    monkeypatch.setattr("backend.adapter.client.requests.post", boom)
    with pytest.raises(client_mod.MiddleApiError):
        client_mod.call("login_api", "x", openid="dev01")
    row = MiddleCallLog.query.one()
    assert row.success == 0
    assert row.http_status is None
    assert "请求中间方失败" in row.error_msg


def test_middle_call_non_json_truncated(app, monkeypatch):
    monkeypatch.setattr("backend.adapter.client.requests.post",
                        lambda url, data, timeout: FakeResp(200, None, text="x" * 3000))
    with pytest.raises(client_mod.MiddleApiError):
        client_mod.call("login_api", "x", openid="dev01")
    row = MiddleCallLog.query.one()
    assert row.success == 0
    assert len(row.response_body) == 2000
    assert "不是合法 JSON" in row.error_msg


def test_demo_call_logged(app, monkeypatch):
    """演示模式也记日志，响应体带 demo 标记便于区分。"""
    monkeypatch.setattr(client_mod, "DEMO_MODE", True)
    client_mod.call("send_api", "post_text", openid="dev01", uuid="u11")
    row = MiddleCallLog.query.one()
    assert row.success == 1
    assert "demo" in row.response_body


# ---------- 出站：媒体下载 ----------

def test_call_download_success(app, monkeypatch):
    payload = {"code": 0, "msg": "success",
               "data": {"ret": 200, "data": {"fileUrl": "http://cdn/f.png"}}}
    monkeypatch.setattr("backend.adapter.client.requests.post",
                        lambda url, data, timeout: FakeResp(200, payload))
    file_resp = FakeResp(200)
    file_resp.content = b"\x89PNG fake"
    file_resp.headers = {"Content-Type": "image/png"}
    monkeypatch.setattr("backend.adapter.client.requests.get", lambda url, timeout: file_resp)

    content, ctype = client_mod.call_download("messag_api", "get_download_image", openid="dev01")
    assert ctype == "image/png"
    row = MiddleCallLog.query.one()
    assert row.success == 1
    assert "[file]" in row.response_body
    assert "bytes=9" in row.response_body  # 二进制只记元信息


def test_call_download_ret_fail(app, monkeypatch):
    payload = {"code": 0, "msg": "success", "data": {"ret": 500, "msg": "设备已离线"}}
    monkeypatch.setattr("backend.adapter.client.requests.post",
                        lambda url, data, timeout: FakeResp(200, payload))
    with pytest.raises(client_mod.MiddleApiError):
        client_mod.call_download("messag_api", "get_download_image", openid="dev01")
    row = MiddleCallLog.query.one()
    assert row.success == 0
    assert row.ret == 500
    assert "设备已离线" in row.error_msg


# ---------- 触发来源 ----------

def test_trigger_source_from_job(app):
    middle_log.set_job_source("confirm_worker")
    middle_log.log_call("messag_api", "get_post_text_message", uuid="u9")
    row = MiddleCallLog.query.one()
    assert row.trigger_source == "confirm_worker"
    assert row.user_id is None  # 定时任务无用户


def test_trigger_source_from_request_path(app):
    with app.test_request_context("/api/messages/send"):
        middle_log.log_call("send_api", "post_text", uuid="u10")
    row = MiddleCallLog.query.one()
    assert row.trigger_source == "/api/messages/send"


# ---------- 清理 ----------

def _access_row(path, when):
    return AccessLog(access_time=when, path=path, method="GET", url="http://x", ip="1",
                     status_code=200, user_name="", org_name="")


def _middle_row(uuid, when):
    return MiddleCallLog(call_time=when, module="send_api", action="post_text",
                         uuid=uuid, openid="", success=1)


def test_clean_expired_access(app):
    now = datetime.now()
    db.session.add_all([
        _access_row("/old", now - timedelta(days=91)),
        _access_row("/new", now),
    ])
    db.session.commit()
    assert clean_access_expired(days=90) == 1
    assert AccessLog.query.count() == 1
    assert AccessLog.query.one().path == "/new"


def test_clean_expired_middle(app):
    now = datetime.now()
    db.session.add_all([
        _middle_row("old", now - timedelta(days=91)),
        _middle_row("new", now),
    ])
    db.session.commit()
    assert clean_middle_expired(days=90) == 1
    assert MiddleCallLog.query.count() == 1
    assert MiddleCallLog.query.one().uuid == "new"
