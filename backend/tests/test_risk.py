"""限流与登录失败锁定单测：services/risk 的算法 + 全局钩子 + 登录接口串联。"""


def _set_limits(monkeypatch, **kwargs):
    """改 config 里的阈值；risk 内部是调用时导入，所以能即时生效。"""
    import backend.config as cfg

    for key, value in kwargs.items():
        monkeypatch.setattr(cfg, key, value)


def test_check_request_allows_within_limit(monkeypatch):
    """未超限放行；超限返回 False + 剩余秒数。"""
    _set_limits(monkeypatch, API_LIMIT_PER_MINUTE=2)
    from backend.services import risk

    assert risk.check_request("/api/accounts", "GET", "1.1.1.1")[0] is True
    assert risk.check_request("/api/accounts", "GET", "1.1.1.1")[0] is True

    ok, retry = risk.check_request("/api/accounts", "GET", "1.1.1.1")
    assert ok is False
    assert retry > 0


def test_buckets_are_isolated(monkeypatch):
    """消息桶打满不影响其余接口：避免翻页限流误伤正常操作。"""
    _set_limits(monkeypatch, MESSAGES_LIMIT_PER_MINUTE=1, API_LIMIT_PER_MINUTE=1)
    from backend.services import risk

    path = "/api/conversations/1/messages"
    assert risk.check_request(path, "GET", "1.1.1.1")[0] is True
    assert risk.check_request(path, "GET", "1.1.1.1")[0] is False
    assert risk.check_request("/api/accounts", "GET", "1.1.1.1")[0] is True


def test_media_bucket_takes_priority(monkeypatch):
    """媒体路径同时含 /messages，必须命中更严的 media 桶而非 messages 桶。"""
    _set_limits(monkeypatch, MEDIA_LIMIT_PER_MINUTE=1, MESSAGES_LIMIT_PER_MINUTE=5)
    from backend.services import risk

    assert risk.check_request("/api/messages/9/media", "GET", "1.1.1.1")[0] is True
    # 媒体配额（1 次）已用完 → 立即拒绝；若误判成 messages 桶则会被放行
    assert risk.check_request("/api/messages/9/media", "GET", "1.1.1.1")[0] is False


def test_exempt_paths_never_limited():
    """健康检查、WebSocket、静态资源、预检请求不计数。"""
    from backend.services import risk

    for _ in range(50):
        assert risk.check_request("/api/health", "GET", "1.1.1.1")[0] is True
        assert risk.check_request("/ws", "GET", "1.1.1.1")[0] is True
        assert risk.check_request("/static/app.js", "GET", "1.1.1.1")[0] is True
        assert risk.check_request("/api/accounts", "OPTIONS", "1.1.1.1")[0] is True


def test_ip_isolation(monkeypatch):
    """限流按 IP 独立计数，一个 IP 打满不影响另一个。"""
    _set_limits(monkeypatch, API_LIMIT_PER_MINUTE=1)
    from backend.services import risk

    assert risk.check_request("/api/accounts", "GET", "1.1.1.1")[0] is True
    assert risk.check_request("/api/accounts", "GET", "1.1.1.1")[0] is False
    assert risk.check_request("/api/accounts", "GET", "2.2.2.2")[0] is True


def test_login_lock_after_max_fails(monkeypatch):
    """失败达到上限即锁定；成功后清零。"""
    _set_limits(monkeypatch, LOGIN_MAX_FAILS=3)
    from backend.services import risk

    key = "1.1.1.1::cs01"
    assert risk.login_blocked(key) == 0

    for _ in range(3):
        risk.record_login_failure(key)

    assert risk.login_blocked(key) > 0

    risk.reset_login(key)
    assert risk.login_blocked(key) == 0


def test_login_api_locks_after_failures(client):
    """连续输错 5 次后第 6 次 429；锁定期内正确密码同样拒绝。"""
    for _ in range(5):
        resp = client.post("/api/auth/login", json={"username": "cs01", "password": "wrong"})
        assert resp.status_code == 401

    resp = client.post("/api/auth/login", json={"username": "cs01", "password": "wrong"})
    assert resp.status_code == 429
    assert resp.get_json()["err"] == "LOGIN_LOCKED"

    resp = client.post("/api/auth/login", json={"username": "cs01", "password": "123456"})
    assert resp.status_code == 429


def test_login_success_clears_failures(client):
    """4 次失败后登录成功应清零，之后不会因为历史失败被锁。"""
    for _ in range(4):
        assert client.post(
            "/api/auth/login", json={"username": "cs01", "password": "wrong"}
        ).status_code == 401

    ok = client.post("/api/auth/login", json={"username": "cs01", "password": "123456"})
    assert ok.status_code == 200

    for _ in range(4):
        assert client.post(
            "/api/auth/login", json={"username": "cs01", "password": "wrong"}
        ).status_code == 401


def test_login_response_expires_in_matches_config(client):
    """令牌有效期下发值与配置一致（默认 12 小时）。"""
    from backend.config import TOKEN_EXPIRE_HOURS

    resp = client.post("/api/auth/login", json={"username": "cs01", "password": "123456"})
    assert resp.get_json()["data"]["expires_in"] == TOKEN_EXPIRE_HOURS * 3600


def test_hook_returns_429_shape(app, monkeypatch):
    """全局钩子生效：超过阈值返回统一 429 结构 + Retry-After。"""
    _set_limits(monkeypatch, API_LIMIT_PER_MINUTE=1)

    with app.test_client() as c:
        assert c.get("/api/auth/me").status_code == 401  # 第一次：进入业务（未登录）
        resp = c.get("/api/auth/me")  # 第二次：被限流拦在业务之前

    assert resp.status_code == 429
    assert resp.get_json()["err"] == "RATE_LIMITED"
    assert int(resp.headers["Retry-After"]) > 0
