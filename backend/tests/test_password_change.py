"""强制改密：初始密码账号登录后必须自助改密，未改密期间业务接口全部拦截。"""
from backend.models.audit_log import AuditLog
from backend.services.auth import create_token
from backend.tests.conftest import login_headers, make_user


def _login(app, username, password):
    return app.test_client().post(
        "/api/auth/login", json={"username": username, "password": password})


def test_created_account_must_change_password(app):
    """新增账号（初始密码）登录后带强制改密标记，业务接口被拦、/me 放行。"""
    make_user(must_change_password=1)

    resp = _login(app, "cs01", "123456")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["user"]["must_change_password"] is True
    headers = {"Authorization": f"Bearer {data['token']}"}

    # 业务接口被拦，错误码供前端识别弹强制改密窗（客服可访问的接口）
    blocked = app.test_client().get("/api/conversations", headers=headers)
    assert blocked.status_code == 403
    assert blocked.get_json()["err"] == "PASSWORD_CHANGE_REQUIRED"

    # /me 与改密接口放行（弹窗恢复会话和提交改密都靠它们）
    me = app.test_client().get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.get_json()["data"]["must_change_password"] is True


def test_change_password_success(app):
    """改密成功：标记清除、业务接口恢复、旧密码失效新密码可登录。"""
    user = make_user(must_change_password=1)
    headers = login_headers(user)
    c = app.test_client()

    resp = c.put("/api/auth/password",
                 json={"old_password": "123456", "new_password": "abc12345"},
                 headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["data"]["must_change_password"] is False

    # 业务接口恢复（客服可访问的会话列表）
    assert app.test_client().get("/api/conversations", headers=headers).status_code == 200

    # 旧密码登录失败，新密码登录成功
    assert _login(app, "cs01", "123456").status_code == 401
    assert _login(app, "cs01", "abc12345").status_code == 200

    log = AuditLog.query.filter_by(action="修改密码").order_by(AuditLog.id.desc()).first()
    assert log.result == AuditLog.RESULT_SUCCESS


def test_change_password_rejections(app):
    """改密失败矩阵：旧密码错 / 新密码过短 / 新旧相同，均拒绝并记 fail 日志。"""
    user = make_user(must_change_password=1)
    headers = login_headers(user)
    c = app.test_client()

    cases = [
        ({"old_password": "wrong!", "new_password": "abc12345"}, "旧密码错误"),
        ({"old_password": "123456", "new_password": "123"}, "新密码至少 6 位"),
        ({"old_password": "123456", "new_password": "123456"}, "新密码不能与旧密码相同"),
    ]
    for body, msg in cases:
        resp = c.put("/api/auth/password", json=body, headers=headers)
        assert resp.status_code == 400, body
        assert resp.get_json()["msg"] == msg

        log = AuditLog.query.filter_by(action="修改密码").order_by(AuditLog.id.desc()).first()
        assert log.result == AuditLog.RESULT_FAIL

    # 失败后仍是初始密码状态，业务接口依旧被拦
    assert c.get("/api/conversations", headers=headers).get_json()["err"] == "PASSWORD_CHANGE_REQUIRED"


def test_change_password_requires_login(app):
    """未登录不能调改密接口。"""
    resp = app.test_client().put(
        "/api/auth/password", json={"old_password": "x", "new_password": "y123456"})
    assert resp.status_code == 401


def test_reset_password_sets_flag(app):
    """管理端重置密码后，账号回到强制改密状态。"""
    make_user(username="admin01", name="管理员", role="admin")
    target = make_user(must_change_password=0)

    from backend.extensions import db
    from backend.models.user import User
    admin_user = User.query.filter_by(username="admin01").one()
    c = app.test_client()
    resp = c.put(f"/api/accounts/{target.id}/password", headers=login_headers(admin_user))
    assert resp.status_code == 200

    refreshed = db.session.get(User, target.id)
    assert refreshed.must_change_password == 1
    # 重置后登录应被拦（客服可访问的接口）
    login = _login(app, "cs01", "123456")
    headers = {"Authorization": f"Bearer {login.get_json()['data']['token']}"}
    assert c.get("/api/conversations", headers=headers).get_json()["err"] == "PASSWORD_CHANGE_REQUIRED"


def test_send_message_blocked_before_send_flag(app, conversation):
    """发消息接口的手动鉴权同样走强制改密门控（在发送开关判断之前）。"""
    user = make_user(must_change_password=1)
    resp = app.test_client().post(
        f"/api/conversations/{conversation.id}/messages",
        json={"msg_type": 1, "content": "hi", "payload": {}},
        headers=login_headers(user))
    assert resp.status_code == 403
    assert resp.get_json()["err"] == "PASSWORD_CHANGE_REQUIRED"
