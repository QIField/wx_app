"""账号管理接口单测：权限门控、设备绑定唯一性、审计日志接入、组织归属。"""
from backend.extensions import db
from backend.models.audit_log import AuditLog
from backend.models.org import Org
from backend.models.user import ROLE_ADMIN, ROLE_AGENT, ROLE_DEVELOPER, User
from backend.models.user_device import UserDevice
from backend.services.audit import AuditModule

from backend.tests.conftest import login_headers, make_user


def _devices_of(user_id):
    """某账号的绑定 openid 列表（按绑定顺序）。"""
    rows = UserDevice.query.filter_by(user_id=user_id).order_by(UserDevice.id).all()
    return [r.openid for r in rows]


def _dev():
    return make_user(username="dev", name="开发者", role=ROLE_DEVELOPER)


def _admin():
    return make_user(username="adm", name="管理员", role=ROLE_ADMIN)


def _org(name="佛山"):
    row = Org(name=name)
    db.session.add(row)
    db.session.commit()
    return row


def _count_logs(action):
    return AuditLog.query.filter_by(module=AuditModule.ACCOUNT, action=action).count()


def test_admin_can_list_accounts(client, app):
    """管理员可以看账号列表。"""
    _admin()
    user = User.query.filter_by(username="adm").one()
    resp = client.get("/api/accounts", headers=login_headers(user))

    assert resp.status_code == 200
    assert resp.get_json()["code"] == 0


def test_agent_cannot_access_accounts(client, app):
    """客服无权访问账号接口：403。"""
    resp = client.get("/api/accounts")
    assert resp.status_code == 403


def test_create_account_with_initial_password(client, app):
    """新增账号：初始密码 123456 可直接登录；操作记日志；组织入库。"""
    _dev()
    org = _org("珠海")
    user = User.query.filter_by(username="dev").one()

    resp = client.post("/api/accounts", headers=login_headers(user),
                       json={"username": "cs09", "name": "新客服", "role": ROLE_AGENT,
                             "org_id": org.id})

    assert resp.status_code == 200
    created = User.query.filter_by(username="cs09").one()
    assert created.name == "新客服"
    assert created.org_id == org.id

    from werkzeug.security import check_password_hash
    assert check_password_hash(created.password_hash, "123456")
    assert _count_logs("新增账号") == 1


def test_create_agent_requires_org(client, app):
    """新建客服/管理员必须选组织：400。"""
    _dev()
    user = User.query.filter_by(username="dev").one()

    resp = client.post("/api/accounts", headers=login_headers(user),
                       json={"username": "cs10", "name": "无组织", "role": ROLE_AGENT})

    assert resp.status_code == 400
    assert "组织" in resp.get_json()["msg"]
    assert User.query.filter_by(username="cs10").first() is None


def test_create_agent_unknown_org_rejected(client, app):
    """组织不存在或停用：400。"""
    _dev()
    org = _org("中山")
    org.status = 0
    db.session.commit()
    user = User.query.filter_by(username="dev").one()

    resp = client.post("/api/accounts", headers=login_headers(user),
                       json={"username": "cs11", "name": "停用组织", "role": ROLE_AGENT,
                             "org_id": org.id})

    assert resp.status_code == 400


def test_create_developer_without_org_ok(client, app):
    """developer 账号不绑组织（跨组织）：可直接创建。"""
    _dev()
    user = User.query.filter_by(username="dev").one()

    resp = client.post("/api/accounts", headers=login_headers(user),
                       json={"username": "dv2", "name": "二号开发", "role": ROLE_DEVELOPER})

    assert resp.status_code == 200
    assert User.query.filter_by(username="dv2").one().org_id is None


def test_update_org_changes_membership(client, app):
    """编辑可改组织：换组织生效并记入审计详情。"""
    _dev()
    org_a = _org("佛山")
    org_b = _org("东莞合峰")
    make_user(username="cs15", name="客服十五", role=ROLE_AGENT, org_id=org_a.id)
    user = User.query.filter_by(username="dev").one()
    target = User.query.filter_by(username="cs15").one()

    resp = client.put(f"/api/accounts/{target.id}", headers=login_headers(user),
                      json={"name": "客服十五", "org_id": org_b.id})

    assert resp.status_code == 200
    db.session.expire_all()
    assert User.query.filter_by(username="cs15").one().org_id == org_b.id
    log = AuditLog.query.filter_by(action="编辑账号").one()
    assert "组织" in log.detail


def test_orgs_list_admin_ok_agent_forbidden(client, app):
    """组织列表：developer/admin 可看，客服 403。"""
    from backend.models.user import STATUS_ON
    _admin()
    _org("佛山")
    _org("珠海")
    # 停用组织不返回
    off = _org("中山")
    off.status = 0
    db.session.commit()

    adm = User.query.filter_by(username="adm").one()
    data = client.get("/api/orgs", headers=login_headers(adm)).get_json()["data"]
    assert [o["name"] for o in data] == ["佛山", "珠海"]
    assert all(o["status"] == STATUS_ON for o in data)

    resp = client.get("/api/orgs")
    assert resp.status_code == 403


def test_create_duplicate_username_logged_as_fail(client, app):
    """新增重复账号：400，且记 fail 日志（失败也记）。"""
    _dev()
    make_user(username="taken", name="已有", role=ROLE_AGENT)
    user = User.query.filter_by(username="dev").one()

    resp = client.post("/api/accounts", headers=login_headers(user),
                       json={"username": "taken", "name": "再来", "role": ROLE_AGENT})

    assert resp.status_code == 400
    log = AuditLog.query.filter_by(module=AuditModule.ACCOUNT, action="新增账号",
                                   result="fail").one()
    assert "已存在" in log.detail


def test_admin_cannot_create_developer(client, app):
    """管理员不可创建开发者账号：403。"""
    _admin()
    user = User.query.filter_by(username="adm").one()

    resp = client.post("/api/accounts", headers=login_headers(user),
                       json={"username": "dv2", "name": "二号", "role": ROLE_DEVELOPER})

    assert resp.status_code == 403


def test_admin_cannot_operate_developer_row(client, app):
    """管理员不可操作开发者行：停用/重置/编辑都 403，并记 fail 日志。"""
    _dev()
    _admin()
    dev = User.query.filter_by(username="dev").one()
    adm = User.query.filter_by(username="adm").one()

    assert client.put(f"/api/accounts/{dev.id}/status", headers=login_headers(adm),
                      json={"status": 0}).status_code == 403
    assert client.put(f"/api/accounts/{dev.id}/password", headers=login_headers(adm)
                      ).status_code == 403
    assert client.put(f"/api/accounts/{dev.id}", headers=login_headers(adm),
                      json={"name": "改名"}).status_code == 403
    assert _count_logs("变更账号状态") == 1
    assert _count_logs("重置密码") == 1


def test_cannot_disable_self(client, app):
    """不能停用自己：400 + fail 日志。"""
    _admin()
    adm = User.query.filter_by(username="adm").one()

    resp = client.put(f"/api/accounts/{adm.id}/status", headers=login_headers(adm),
                      json={"status": 0})

    assert resp.status_code == 400
    log = AuditLog.query.filter_by(action="变更账号状态", result="fail").one()
    assert "不能停用" in log.detail


def test_reset_password(client, app):
    """重置密码后：旧密码失效、初始密码生效，记日志。"""
    _dev()
    make_user(username="cs05", name="吴桐", role=ROLE_AGENT)
    dev = User.query.filter_by(username="dev").one()
    target = User.query.filter_by(username="cs05").one()

    resp = client.put(f"/api/accounts/{target.id}/password", headers=login_headers(dev))

    assert resp.status_code == 200
    db.session.expire_all()
    target = User.query.filter_by(username="cs05").one()
    from werkzeug.security import check_password_hash
    assert check_password_hash(target.password_hash, "123456")
    assert _count_logs("重置密码") == 1


def test_bind_devices_developer_only(client, app):
    """绑定设备：developer 可以，admin 不可（服务端强校验）。"""
    _dev()
    _admin()
    make_user(username="cs03", name="客服三", role=ROLE_AGENT)
    dev = User.query.filter_by(username="dev").one()
    adm = User.query.filter_by(username="adm").one()
    target = User.query.filter_by(username="cs03").one()

    ok = client.put(f"/api/accounts/{target.id}", headers=login_headers(dev),
                    json={"name": "客服三", "devices": [{"openid": "ABC123", "remark": "一号机"}]})
    assert ok.status_code == 200
    db.session.expire_all()
    assert _devices_of(target.id) == ["ABC123"]

    target2 = make_user(username="cs04", name="客服四", role=ROLE_AGENT)
    denied = client.put(f"/api/accounts/{target2.id}", headers=login_headers(adm),
                        json={"name": "客服四", "devices": ["XYZ789"]})
    assert denied.status_code == 403
    db.session.expire_all()
    assert _devices_of(target2.id) == []
    log = AuditLog.query.filter_by(action="绑定微信设备", result="fail").one()
    assert "仅开发者" in log.detail


def test_bind_devices_multiple_in_order(client, app):
    """一台账号绑多台设备：按传入顺序追加；再传列表时已有绑定保持原顺序。"""
    _dev()
    make_user(username="cs14", name="客服十四", role=ROLE_AGENT)
    dev = User.query.filter_by(username="dev").one()
    target = User.query.filter_by(username="cs14").one()

    ok = client.put(f"/api/accounts/{target.id}", headers=login_headers(dev),
                    json={"name": "客服十四", "devices": ["D1", "D2", "D3"]})
    assert ok.status_code == 200
    db.session.expire_all()
    assert _devices_of(target.id) == ["D1", "D2", "D3"]

    # 去掉 D2：D1/D3 保持原绑定，D2 解除；新加 D4 排最后
    ok2 = client.put(f"/api/accounts/{target.id}", headers=login_headers(dev),
                     json={"name": "客服十四", "devices": ["D1", "D3", "D4"]})
    assert ok2.status_code == 200
    db.session.expire_all()
    assert _devices_of(target.id) == ["D1", "D3", "D4"]


def test_bind_devices_all_roles(client, app):
    """开发者/管理员账号也可绑定设备；角色间设备冲突同样拒绝。"""
    _dev()
    _admin()
    dev = User.query.filter_by(username="dev").one()
    adm = User.query.filter_by(username="adm").one()

    ok = client.put(f"/api/accounts/{adm.id}", headers=login_headers(dev),
                    json={"name": "管理员", "devices": ["ADM1"]})
    assert ok.status_code == 200
    db.session.expire_all()
    assert _devices_of(adm.id) == ["ADM1"]

    # 客服占用管理员已绑的设备：同样拒绝
    target = make_user(username="cs13", name="客服十三", role=ROLE_AGENT)
    resp = client.put(f"/api/accounts/{target.id}", headers=login_headers(dev),
                      json={"name": "客服十三", "devices": ["ADM1"]})
    assert resp.status_code == 400
    assert "已绑定" in resp.get_json()["msg"]

    # developer 传空列表 = 解除全部绑定
    clear = client.put(f"/api/accounts/{adm.id}", headers=login_headers(dev),
                       json={"name": "管理员", "devices": []})
    assert clear.status_code == 200
    db.session.expire_all()
    assert _devices_of(adm.id) == []


def test_bind_devices_duplicate_in_list(client, app):
    """同一次请求里重复的设备：400。"""
    _dev()
    make_user(username="cs15", name="客服十五", role=ROLE_AGENT)
    dev = User.query.filter_by(username="dev").one()
    target = User.query.filter_by(username="cs15").one()

    resp = client.put(f"/api/accounts/{target.id}", headers=login_headers(dev),
                      json={"name": "客服十五", "devices": ["D1", "D1"]})
    assert resp.status_code == 400
    assert _devices_of(target.id) == []


def test_bind_devices_unique(client, app):
    """一台设备只能绑一个账号：冲突 400 + fail 日志。"""
    _dev()
    make_user(username="cs11", name="客服十一", role=ROLE_AGENT, open_ids=["DEV1"])
    dev = User.query.filter_by(username="dev").one()
    other = make_user(username="cs12", name="客服十二", role=ROLE_AGENT)

    resp = client.put(f"/api/accounts/{other.id}", headers=login_headers(dev),
                      json={"name": "客服十二", "devices": ["DEV1"]})

    assert resp.status_code == 400
    assert "已绑定" in resp.get_json()["msg"]
    log = AuditLog.query.filter_by(action="绑定微信设备", result="fail").one()
    assert "客服十一" in log.detail


def test_admin_edit_name_with_existing_devices_ok(client, app):
    """管理员编辑姓名时原样带回已有绑定（未变化）：放行，不算越权。"""
    _admin()
    make_user(username="cs06", name="旧名", role=ROLE_AGENT, open_ids=["DEV2"])
    adm = User.query.filter_by(username="adm").one()
    target = User.query.filter_by(username="cs06").one()

    resp = client.put(f"/api/accounts/{target.id}", headers=login_headers(adm),
                      json={"name": "新名", "devices": [{"openid": "DEV2"}]})

    assert resp.status_code == 200
    db.session.expire_all()
    assert User.query.filter_by(username="cs06").one().name == "新名"
    assert _devices_of(target.id) == ["DEV2"]


def test_audit_logs_developer_only(client, app):
    """日志接口仅开发者：admin 是 403，未登录是 401。"""
    _dev()
    _admin()
    dev = User.query.filter_by(username="dev").one()
    adm = User.query.filter_by(username="adm").one()

    assert client.get("/api/audit-logs", headers=login_headers(dev)).status_code == 200
    assert client.get("/api/audit-logs", headers=login_headers(adm)).status_code == 403
    assert app.test_client().get("/api/audit-logs").status_code == 401


def test_audit_logs_keyword_search(client, app):
    """关键词搜索：命中 操作人/动作/对象。"""
    _dev()
    dev = User.query.filter_by(username="dev").one()
    make_user(username="cs07", name="王五", role=ROLE_AGENT)
    target = User.query.filter_by(username="cs07").one()
    client.put(f"/api/accounts/{target.id}", headers=login_headers(dev),
               json={"name": "王五九"})

    hit = client.get("/api/audit-logs?keyword=王五", headers=login_headers(dev))
    assert any("王五" in item["target"] for item in hit.get_json()["data"]["list"])

    miss = client.get("/api/audit-logs?keyword=不存在的关键词", headers=login_headers(dev))
    assert miss.get_json()["data"]["list"] == []


def test_workbench_filtered_by_openid(client, app):
    """工作台会话按登录人设备过滤：另一台设备的会话看不到。"""
    from backend.models.conversation import Conversation
    from backend.services import anonymize

    db.session.add(Conversation(openid="other-device", wxid="wxid_x", chat_type=1))
    db.session.add(Conversation(openid="dev01", wxid="wxid_mine", chat_type=1))
    db.session.commit()

    resp = client.get("/api/conversations")
    names = [c["alias"] for c in resp.get_json()["data"]]  # 出参无 wxid，用 alias 判别

    assert names == [anonymize.alias_of("wxid_mine")]
