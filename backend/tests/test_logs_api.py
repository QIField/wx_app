"""接口日志查询 API 单测：developer 权限 + 过滤参数 + 分页。"""
from datetime import datetime, timedelta

from backend.extensions import db
from backend.models.access_log import AccessLog
from backend.models.middle_call_log import MiddleCallLog
from backend.models.user import ROLE_AGENT, ROLE_DEVELOPER


def _seed_access(**over):
    fields = dict(
        access_time=datetime(2026, 11, 1, 10, 0, 0),
        user_id=1, user_name="客服01",
        path="/api/conversations", method="GET", url="http://x/api/conversations",
        ip="127.0.0.1", status_code=200,
    )
    fields.update(over)
    row = AccessLog(**fields)
    db.session.add(row)
    db.session.commit()
    return row


def _seed_middle(**over):
    fields = dict(
        call_time=datetime(2026, 11, 1, 10, 0, 0),
        trigger_source="/api/messages", module="send_api", action="post_text_message",
        uuid="u-1", openid="dev01", success=1,
    )
    fields.update(over)
    row = MiddleCallLog(**fields)
    db.session.add(row)
    db.session.commit()
    return row


def _as_developer(app, **user_over):
    """造开发者账号并返回带令牌的请求头。"""
    from backend.tests.conftest import login_headers, make_user

    user = make_user(username="dev01", name="开发者",
                     role=ROLE_DEVELOPER, **user_over)
    return login_headers(user)


def test_logs_require_developer(app):
    """agent 角色无权查询接口日志。"""
    from backend.tests.conftest import login_headers, make_user

    agent = make_user(role=ROLE_AGENT)
    resp = app.test_client().get("/api/logs/access", headers=login_headers(agent))
    assert resp.status_code == 403
    resp = app.test_client().get("/api/logs/middle", headers=login_headers(agent))
    assert resp.status_code == 403


def test_access_logs_list_and_filters(app):
    headers = _as_developer(app)
    # 种子统一放 /biz/ 前缀下，规避钩子对查询请求自身的记录
    _seed_access(path="/biz/list", status_code=200, method="GET")
    _seed_access(path="/biz/login", status_code=401, method="POST")
    _seed_access(access_time=datetime.now() - timedelta(days=95),
                 path="/biz/old", status_code=500, user_id=None, user_name="")

    c = app.test_client()
    base = "/api/logs/access?path=/biz/"
    # 全量
    data = c.get(base, headers=headers).get_json()["data"]
    assert data["total"] == 3
    # path 前缀
    data = c.get(f"{base}login", headers=headers).get_json()["data"]
    assert data["total"] == 1 and data["items"][0]["path"] == "/biz/login"
    # status >= 400
    data = c.get(f"{base}&status=>=400", headers=headers).get_json()["data"]
    assert data["total"] == 2
    # status 精确
    data = c.get(f"{base}&status=200", headers=headers).get_json()["data"]
    assert data["total"] == 1
    # method
    data = c.get(f"{base}&method=post", headers=headers).get_json()["data"]
    assert data["total"] == 1 and data["items"][0]["method"] == "POST"
    # 时间段：95 天前的被 start 过滤掉
    data = c.get(f"{base}&start=2026-10-01", headers=headers).get_json()["data"]
    assert data["total"] == 2
    # user_id
    data = c.get(f"{base}&user_id=1", headers=headers).get_json()["data"]
    assert data["total"] == 2


def test_access_logs_pagination(app):
    headers = _as_developer(app)
    for i in range(5):
        _seed_access(path=f"/biz/x/{i}")
    c = app.test_client()
    base = "/api/logs/access?path=/biz/&page_size=2"
    data = c.get(f"{base}&page=1", headers=headers).get_json()["data"]
    assert data["total"] == 5
    assert len(data["items"]) == 2
    data2 = c.get(f"{base}&page=3", headers=headers).get_json()["data"]
    assert len(data2["items"]) == 1


def test_middle_logs_list_and_filters(app):
    headers = _as_developer(app)
    _seed_middle(uuid="u-1", success=1, module="send_api")
    _seed_middle(uuid="u-2", success=0, module="messag_api", action="get_task",
                 error_msg="设备已离线", ret=500)

    c = app.test_client()
    data = c.get("/api/logs/middle", headers=headers).get_json()["data"]
    assert data["total"] == 2
    # uuid 精确（闭环追踪主入口）
    data = c.get("/api/logs/middle?uuid=u-2", headers=headers).get_json()["data"]
    assert data["total"] == 1 and data["items"][0]["ret"] == 500
    # success 过滤
    data = c.get("/api/logs/middle?success=0", headers=headers).get_json()["data"]
    assert data["total"] == 1 and data["items"][0]["uuid"] == "u-2"
    # module 过滤
    data = c.get("/api/logs/middle?module=send_api", headers=headers).get_json()["data"]
    assert data["total"] == 1 and data["items"][0]["module"] == "send_api"
    # openid 过滤
    data = c.get("/api/logs/middle?openid=dev01", headers=headers).get_json()["data"]
    assert data["total"] == 2
