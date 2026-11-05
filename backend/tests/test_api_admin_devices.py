"""管理后台设备字典接口单测：CRUD、openid 唯一、关联拦截删除、权限门控。

client 夹具登录的是 cs01（agent）；管理接口用 login_headers(dev/adm) 自带身份。
"""
from backend.extensions import db
from backend.models.audit_log import AuditLog
from backend.models.device import Device
from backend.models.org import Org
from backend.services.audit import AuditModule

from backend.tests.conftest import login_headers, make_user


def _dev():
    return make_user(username="dev", name="开发者", role="developer")


def _admin():
    return make_user(username="adm", name="管理员", role="admin")


def _org(name="佛山", status=1):
    row = Org(name=name, status=status)
    db.session.add(row)
    db.session.commit()
    return row


def test_list_devices_with_bound_users(app, client):
    """设备列表：附组织名与关联账号（多账号、跨组织都列出）。"""
    _dev()
    dev = make_user(username="dv2", name="二号开发", role="developer")
    org = _org("珠海")
    device = Device(openid="WX1", name="珠海一部-01", org_id=org.id)
    db.session.add(device)
    db.session.commit()
    make_user(username="csA", name="客服甲", role="agent", org_id=org.id, open_ids=["WX1"])
    cs_b = make_user(username="csB", name="客服乙", role="agent")
    from backend.tests.conftest import bind_device
    bind_device(cs_b, "WX1")  # 第二个账号关联同一台设备（多对多）

    data = client.get("/api/admin/devices", headers=login_headers(dev)).get_json()["data"]
    row = next(d for d in data if d["openid"] == "WX1")

    assert row["name"] == "珠海一部-01"
    assert row["org_name"] == "珠海"
    assert [u["username"] for u in row["bound_users"]] == ["csA", "csB"]


def test_create_device(app, client):
    """入库设备：openid 全局唯一；组织必填且启用。"""
    _dev()
    dev = make_user(username="dv2", name="二号开发", role="developer")
    org = _org("中山")

    resp = client.post("/api/admin/devices", headers=login_headers(dev),
                       json={"openid": "wxid_zs01", "name": "中山一部-01", "org_id": org.id})
    assert resp.status_code == 200
    row = Device.query.filter_by(openid="wxid_zs01").one()
    assert row.name == "中山一部-01"
    assert row.org_id == org.id
    assert row.online == -1
    log = AuditLog.query.filter_by(module=AuditModule.DEVICE, action="新增设备").one()
    assert log.result == "success"


def test_create_device_duplicate_openid_409(app, client):
    """openid 已存在：409 + fail 日志。"""
    _dev()
    dev = make_user(username="dv2", name="二号开发", role="developer")
    _org("佛山")
    client.post("/api/admin/devices", headers=login_headers(dev),
                json={"openid": "wxid_dup", "name": "一号", "org_id": 1})

    resp = client.post("/api/admin/devices", headers=login_headers(dev),
                       json={"openid": "wxid_dup", "name": "二号", "org_id": 1})

    assert resp.status_code == 409
    assert "已存在" in resp.get_json()["msg"]
    assert Device.query.filter_by(openid="wxid_dup").count() == 1


def test_create_device_validations(app, client):
    """缺设备 ID / 缺名称 / 缺组织 / 组织停用：都是 400。"""
    dev = make_user(username="dv2", name="二号开发", role="developer")
    org = _org("佛山")
    off = _org("中山", status=0)

    base = {"openid": "wxid_v", "name": "测试机", "org_id": org.id}
    assert client.post("/api/admin/devices", headers=login_headers(dev),
                       json={**base, "openid": ""}).status_code == 400
    assert client.post("/api/admin/devices", headers=login_headers(dev),
                       json={**base, "name": ""}).status_code == 400
    assert client.post("/api/admin/devices", headers=login_headers(dev),
                       json={**base, "org_id": None}).status_code == 400
    assert client.post("/api/admin/devices", headers=login_headers(dev),
                       json={**base, "org_id": off.id}).status_code == 400
    assert Device.query.filter_by(openid="wxid_v").count() == 0


def test_update_device_cannot_change_openid(app, client):
    """编辑设备：名称/组织可改；openid 录入后不可改（传入被忽略）。"""
    dev = make_user(username="dv2", name="二号开发", role="developer")
    org1, org2 = _org("佛山"), _org("珠海")
    device = Device(openid="WX9", name="旧名", org_id=org1.id)
    db.session.add(device)
    db.session.commit()

    resp = client.put(f"/api/admin/devices/{device.id}", headers=login_headers(dev),
                      json={"openid": "HACKED", "name": "新名", "org_id": org2.id})
    assert resp.status_code == 200
    row = Device.query.filter_by(id=device.id).one()
    assert row.openid == "WX9"
    assert row.name == "新名"
    assert row.org_id == org2.id


def test_update_device_not_found(app, client):
    """编辑/删除不存在的设备：404。"""
    dev = make_user(username="dv2", name="二号开发", role="developer")
    assert client.put("/api/admin/devices/999", headers=login_headers(dev),
                      json={"name": "x", "org_id": 1}).status_code == 404
    assert client.delete("/api/admin/devices/999", headers=login_headers(dev)).status_code == 404


def test_delete_device_blocked_when_bound(app, client):
    """仍被账号关联的设备不可删：409，需先解除关联。"""
    dev = make_user(username="dv2", name="二号开发", role="developer")
    _org("珠海")
    client.post("/api/admin/devices", headers=login_headers(dev),
                json={"openid": "WX2", "name": "珠海机", "org_id": 1})
    device = Device.query.filter_by(openid="WX2").one()
    make_user(username="cs20", name="客服二十", role="agent", open_ids=["WX2"])

    resp = client.delete(f"/api/admin/devices/{device.id}", headers=login_headers(dev))
    assert resp.status_code == 409
    assert "关联" in resp.get_json()["msg"]
    assert Device.query.filter_by(id=device.id).count() == 1
    fail_log = AuditLog.query.filter_by(module=AuditModule.DEVICE, action="删除设备",
                                        result="fail").one()
    assert "1 个账号" in fail_log.detail

    # 解除关联后可删
    from backend.models.user_device import UserDevice
    UserDevice.query.filter_by(device_id=device.id).delete()
    db.session.commit()
    assert client.delete(f"/api/admin/devices/{device.id}",
                         headers=login_headers(dev)).status_code == 200
    assert Device.query.filter_by(id=device.id).count() == 0


def test_admin_device_write_requires_developer(app, client):
    """设备写操作仅 developer：admin 403，客服 403，未登录 401；admin 可读列表。"""
    _dev()
    _admin()
    adm = make_user(username="adm2", name="二号管理", role="admin")
    org = _org("东莞百业")

    assert client.get("/api/admin/devices", headers=login_headers(adm)).status_code == 200
    assert client.post("/api/admin/devices", headers=login_headers(adm),
                       json={"openid": "X1", "name": "x", "org_id": org.id}).status_code == 403
    assert client.put("/api/admin/devices/1", headers=login_headers(adm),
                      json={"name": "x", "org_id": org.id}).status_code == 403
    assert client.delete("/api/admin/devices/1", headers=login_headers(adm)).status_code == 403
    # 无登录态的全新 client：401
    assert app.test_client().post(
        "/api/admin/devices", json={"openid": "X1", "name": "x", "org_id": org.id}
    ).status_code == 401
