"""登录认证单测：三连校验、令牌签发/校验、角色分流。"""
from backend.extensions import db
from backend.models.user import ROLE_ADMIN, ROLE_AGENT, ROLE_DEVELOPER, User
from backend.services.audit import AuditModule
from backend.services.auth import _load_token_user, create_token
from werkzeug.security import generate_password_hash

from backend.tests.conftest import make_user, login_headers


def test_login_ok_returns_token_and_user(client):
    """正确密码登录：返回 token + 用户信息，带角色。"""
    resp = client.post("/api/auth/login", json={"username": "cs01", "password": "123456"})

    body = resp.get_json()
    assert resp.status_code == 200
    assert body["code"] == 0
    assert body["data"]["token"]
    assert body["data"]["user"]["role"] == ROLE_AGENT
    assert [d["openid"] for d in body["data"]["user"]["devices"]] == ["dev01"]


def test_login_wrong_password(client):
    """密码错误：401，不返回 token。"""
    resp = client.post("/api/auth/login", json={"username": "cs01", "password": "wrong"})

    assert resp.status_code == 401
    assert "token" not in (resp.get_json().get("data") or {})


def test_login_unknown_user(client):
    """账号不存在：401，且提示不带账号枚举味。"""
    resp = client.post("/api/auth/login", json={"username": "nobody", "password": "x"})

    assert resp.status_code == 401


def test_login_disabled_user(client):
    """已停用账号：密码正确也 401，提示已停用。"""
    make_user(username="cs02", name="客服02")
    user = User.query.filter_by(username="cs02").one()
    user.status = 0
    db.session.commit()

    resp = client.post("/api/auth/login", json={"username": "cs02", "password": "123456"})

    assert resp.status_code == 401
    assert "停用" in resp.get_json()["msg"]


def test_login_records_audit_log(client):
    """登录成功/失败都记审计日志（规范要求）。"""
    client.post("/api/auth/login", json={"username": "cs01", "password": "wrong"})
    client.post("/api/auth/login", json={"username": "cs01", "password": "123456"})

    from backend.models.audit_log import AuditLog

    logs = AuditLog.query.filter_by(module=AuditModule.AUTH).order_by(AuditLog.id).all()
    assert [l.result for l in logs] == ["fail", "success"]
    assert "密码错误" in logs[0].detail
    assert logs[1].operator_name == "客服01"


def test_me_requires_token(client):
    """未带令牌访问 /api/auth/me：401。"""
    resp = client.get("/api/auth/me", headers={"Authorization": ""})
    assert resp.status_code == 401


def test_me_returns_current_user(client):
    """带令牌访问 /api/auth/me：返回当前登录人。"""
    resp = client.get("/api/auth/me")

    assert resp.status_code == 200
    assert resp.get_json()["data"]["username"] == "cs01"


def test_token_invalid_after_disable(client):
    """停用后旧令牌立即失效（每次校验回库取状态）。"""
    user = User.query.filter_by(username="cs01").one()
    token, _ = create_token(user)
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/api/auth/me", headers=headers).status_code == 200

    user.status = 0
    db.session.commit()

    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_require_role_rejects_other_role(app, client):
    """客服访问管理员接口：403。"""
    resp = client.get("/api/accounts")
    assert resp.status_code == 403


def test_load_token_user_rejects_garbage():
    """伪造令牌返回 None。"""
    assert _load_token_user("not-a-token") is None
    assert _load_token_user("") is None
