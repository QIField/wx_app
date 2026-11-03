"""组织管理接口单测：权限门控、重名拒绝、软删除后下拉不可见、恢复。"""
from backend.extensions import db
from backend.models.audit_log import AuditLog
from backend.models.org import Org
from backend.models.user import ROLE_ADMIN, ROLE_DEVELOPER, STATUS_OFF, STATUS_ON, User
from backend.services.audit import AuditModule

from backend.tests.conftest import login_headers, make_user


def _admin():
    return make_user(username="adm", name="管理员", role=ROLE_ADMIN)


def _dev():
    return make_user(username="dev", name="开发者", role=ROLE_DEVELOPER)


def _org(name="佛山", status=STATUS_ON):
    row = Org(name=name, status=status)
    db.session.add(row)
    db.session.commit()
    return row


def _org_logs(action, result=None):
    q = AuditLog.query.filter_by(module=AuditModule.ORG, action=action)
    if result:
        q = q.filter_by(result=result)
    return q.count()


def test_orgs_all_includes_disabled(client, app):
    """管理表格数据源：全量返回，停用行也在。"""
    _admin()
    _org("佛山")
    _org("惠州", status=STATUS_OFF)

    adm = User.query.filter_by(username="adm").one()
    data = client.get("/api/orgs/all", headers=login_headers(adm)).get_json()["data"]

    assert [o["name"] for o in data] == ["佛山", "惠州"]
    assert data[1]["status"] == STATUS_OFF


def test_orgs_all_agent_forbidden(client, app):
    """客服无权访问组织接口：403（启用列表与全量列表一致）。"""
    _org("佛山")
    assert client.get("/api/orgs/all").status_code == 403
    assert client.post("/api/orgs", json={"name": "东莞"}).status_code == 403
    assert client.put("/api/orgs/1/status", json={"status": 0}).status_code == 403


def test_create_org_ok_and_logged(client, app):
    """新增组织：入库启用，记成功审计日志。"""
    _admin()
    adm = User.query.filter_by(username="adm").one()

    resp = client.post("/api/orgs", headers=login_headers(adm), json={"name": " 惠州 "})

    assert resp.status_code == 200
    org = Org.query.filter_by(name="惠州").one()  # 入库前已去空格
    assert org.status == STATUS_ON
    assert _org_logs("新增组织") == 1


def test_create_org_duplicate_rejected(client, app):
    """重名拒绝：启用中与已停用的都算存在；记 fail 日志。"""
    _admin()
    _org("佛山")
    _org("珠海", status=STATUS_OFF)
    adm = User.query.filter_by(username="adm").one()

    resp = client.post("/api/orgs", headers=login_headers(adm), json={"name": "佛山"})
    assert resp.status_code == 400
    assert "已存在" in resp.get_json()["msg"]

    resp2 = client.post("/api/orgs", headers=login_headers(adm), json={"name": "珠海"})
    assert resp2.status_code == 400

    assert _org_logs("新增组织", result=AuditLog.RESULT_FAIL) == 2


def test_create_org_invalid_name(client, app):
    """空名 / 超长名：400，不落库。"""
    _admin()
    adm = User.query.filter_by(username="adm").one()

    assert client.post("/api/orgs", headers=login_headers(adm),
                       json={"name": "   "}).status_code == 400
    assert client.post("/api/orgs", headers=login_headers(adm),
                       json={"name": "长" * 65}).status_code == 400
    assert Org.query.count() == 0


def test_soft_delete_org_hides_from_enabled_list(client, app):
    """软删除：status=0 后启用列表不再返回，全量列表仍在，行未删除。"""
    _admin()
    org = _org("佛山")
    adm = User.query.filter_by(username="adm").one()

    resp = client.put(f"/api/orgs/{org.id}/status", headers=login_headers(adm),
                      json={"status": STATUS_OFF})

    assert resp.status_code == 200
    assert Org.query.filter_by(name="佛山").first() is not None  # 行保留

    enabled = client.get("/api/orgs", headers=login_headers(adm)).get_json()["data"]
    assert [o["name"] for o in enabled] == []
    all_rows = client.get("/api/orgs/all", headers=login_headers(adm)).get_json()["data"]
    assert [o["name"] for o in all_rows] == ["佛山"]
    assert all_rows[0]["status"] == STATUS_OFF
    assert _org_logs("停用组织") == 1


def test_restore_org_back_to_enabled(client, app):
    """恢复：停用组织重新启用后回到下拉数据源。"""
    _admin()
    org = _org("中山", status=STATUS_OFF)
    adm = User.query.filter_by(username="adm").one()

    resp = client.put(f"/api/orgs/{org.id}/status", headers=login_headers(adm),
                      json={"status": STATUS_ON})

    assert resp.status_code == 200
    enabled = client.get("/api/orgs", headers=login_headers(adm)).get_json()["data"]
    assert [o["name"] for o in enabled] == ["中山"]
    assert _org_logs("启用组织") == 1


def test_toggle_org_status_guards(client, app):
    """状态接口防御：非法值 400；不存在 404；重复状态 400。"""
    _admin()
    org = _org("东莞合峰")
    adm = User.query.filter_by(username="adm").one()
    url = f"/api/orgs/{org.id}/status"

    assert client.put(url, headers=login_headers(adm), json={"status": 5}).status_code == 400
    assert client.put("/api/orgs/999/status", headers=login_headers(adm),
                      json={"status": STATUS_OFF}).status_code == 404
    assert client.put(url, headers=login_headers(adm),
                      json={"status": STATUS_ON}).status_code == 400
    assert _org_logs("停用组织") == 0


def test_org_fields_in_payload(client, app):
    """接口返回含创建时间，供管理表格展示。"""
    _admin()
    _org("佛山")
    adm = User.query.filter_by(username="adm").one()

    data = client.get("/api/orgs/all", headers=login_headers(adm)).get_json()["data"]
    assert data[0]["created_at"] is not None
    assert set(data[0].keys()) == {"id", "name", "status", "created_at"}


def test_developer_can_manage_orgs(client, app):
    """开发者与管理员同样可管理组织（与账号接口权限一致）。"""
    _dev()
    dev = User.query.filter_by(username="dev").one()

    assert client.post("/api/orgs", headers=login_headers(dev),
                       json={"name": "肇庆"}).status_code == 200
