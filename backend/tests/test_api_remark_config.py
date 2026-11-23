"""统一备注配置接口单测：用户级全局一致 / 群成员入口 / 校验 / 软删除恢复 / 存量搬迁 / 审计。"""
from sqlalchemy import text

from backend.db_migrate import _archive_contact_profile, _backfill_remark_config
from backend.extensions import db
from backend.models.audit_log import AuditLog
from backend.models.contact import Contact
from backend.models.contact_remark_config import ContactRemarkConfig
from backend.models.conversation import Conversation
from backend.models.group_member import GroupMember
from backend.services import anonymize


def make_conv(wxid, chat_type=1):
    conv = Conversation(openid="dev01", wxid=wxid, chat_type=chat_type, name=wxid)
    db.session.add(conv)
    db.session.commit()
    return conv


def make_roster(wxid, **over):
    fields = {"type": Contact.TYPE_FRIEND}
    fields.update(over)
    c = Contact(openid="dev01", wxid=wxid, **fields)
    db.session.add(c)
    db.session.commit()
    return c


def make_member(chatroom_wxid, wxid, nickname="陈采购"):
    m = GroupMember(openid="dev01", chatroom_wxid=chatroom_wxid, wxid=wxid, nickname=nickname)
    db.session.add(m)
    db.session.commit()
    return m


def test_get_default_empty(client):
    """无记录返回空配置，scope 按条目类型自动判定（会话条目用负数 id）。"""
    conv = make_conv("wxid_u")
    data = client.get(f"/api/contacts/-{conv.id}/remark-config").get_json()["data"]
    assert data == {
        "scope_type": "user", "remark_name": "", "auto_quote_enabled": False,
        "level": "normal", "tags": [], "oe_detail_enabled": False,
    }


def test_level_roundtrip_and_incremental(client):
    """客户等级：显式传才覆盖（增量语义），非法值 400，不带该字段不重置。"""
    conv = make_conv("wxid_u")
    url = f"/api/contacts/-{conv.id}/remark-config"

    resp = client.put(url, json={"remark_name": "张老板", "level": "vip_a"})
    assert resp.get_json()["code"] == 0
    assert client.get(url).get_json()["data"]["level"] == "vip_a"

    # 不带 level 的保存（旧调用方）不应重置等级
    client.put(url, json={"remark_name": "张老板2", "tags": ["月结"]})
    assert client.get(url).get_json()["data"]["level"] == "vip_a"

    bad = client.put(url, json={"remark_name": "x", "level": "diamond"})
    assert bad.get_json()["code"] == 400


def test_put_get_roundtrip_and_audit(client):
    """保存后可读回；写操作落审计日志（含变更明细）。"""
    conv = make_conv("wxid_u")
    url = f"/api/contacts/-{conv.id}/remark-config"
    resp = client.put(url, json={
        "remark_name": "张老板", "auto_quote_enabled": True, "tags": ["大客户", "月结"],
    })
    assert resp.get_json()["code"] == 0
    data = client.get(url).get_json()["data"]
    assert data["remark_name"] == "张老板"
    assert data["auto_quote_enabled"] is True
    assert data["tags"] == ["大客户", "月结"]

    logs = AuditLog.query.filter_by(action="保存备注设置").all()
    assert len(logs) == 1
    assert "自动报价关→开" in logs[0].detail


def test_member_entry_writes_user_row(client):
    """群成员入口保存的是用户级配置：私聊入口读到同一行（全场景一致）。"""
    pv = make_conv("wxid_u")
    grp = make_conv("1@chatroom", chat_type=2)
    make_member("1@chatroom", "wxid_u")

    member_url = f"/api/groups/-{grp.id}/members/{anonymize.alias_of('wxid_u')}/remark-config"
    client.put(member_url, json={"remark_name": "陈采购(建材)", "auto_quote_enabled": True})

    data = client.get(f"/api/contacts/-{pv.id}/remark-config").get_json()["data"]
    assert data["scope_type"] == "user"
    assert data["remark_name"] == "陈采购(建材)"
    assert data["auto_quote_enabled"] is True


def test_member_alias_unknown_404(client):
    """alias 匹配不上名册成员 → 404（GET/PUT 一致）。"""
    grp = make_conv("1@chatroom", chat_type=2)
    make_member("1@chatroom", "wxid_u")
    url = f"/api/groups/-{grp.id}/members/{anonymize.alias_of('wxid_ghost')}/remark-config"
    assert client.get(url).status_code == 404
    assert client.put(url, json={"remark_name": "x"}).status_code == 404


def test_group_entry_uses_group_scope(client):
    """群条目保存的是群级配置（仅该群），与成员的用户级互不影响。"""
    grp = make_conv("1@chatroom", chat_type=2)
    url = f"/api/contacts/-{grp.id}/remark-config"
    client.put(url, json={"remark_name": "建材报价一群"})
    data = client.get(url).get_json()["data"]
    assert data["scope_type"] == "group"
    assert data["remark_name"] == "建材报价一群"


def test_positive_roster_id_roundtrip(client):
    """正数 contact 条目 id（通讯录入口）同样可用。"""
    c = make_roster("wxid_u", name="张三")
    url = f"/api/contacts/{c.id}/remark-config"
    client.put(url, json={"remark_name": "张老板", "auto_quote_enabled": True})
    data = client.get(url).get_json()["data"]
    assert data["remark_name"] == "张老板"
    assert data["auto_quote_enabled"] is True


def test_remark_too_long_400(client):
    conv = make_conv("wxid_u")
    url = f"/api/contacts/-{conv.id}/remark-config"
    resp = client.put(url, json={"remark_name": "字" * 101})
    assert resp.status_code == 400
    assert "100" in resp.get_json()["msg"]


def test_tags_limit_400(client):
    conv = make_conv("wxid_u")
    url = f"/api/contacts/-{conv.id}/remark-config"
    assert client.put(url, json={"tags": [f"t{i}" for i in range(11)]}).status_code == 400
    assert client.put(url, json={"tags": ["标" * 13]}).status_code == 400


def test_tags_dedupe_trim_and_remark_alias(client):
    """标签自动去空白、去重、去空项；remark 旧字段名兼容 remark_name。"""
    conv = make_conv("wxid_u")
    url = f"/api/contacts/-{conv.id}/remark-config"
    resp = client.put(url, json={"remark": "旧字段备注", "tags": [" 月结 ", "月结", "", "奔驰"]})

    assert resp.get_json()["code"] == 0
    data = client.get(url).get_json()["data"]
    assert data["remark_name"] == "旧字段备注"
    assert data["tags"] == ["月结", "奔驰"]


def test_backfill_and_archive_legacy_profile(client):
    """存量搬迁：旧表备注按作用域搬入新表（群 ID→group），随后旧表改名归档；全程幂等。"""
    db.session.execute(text(
        "CREATE TABLE contact_profile ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "wxid VARCHAR(64), remark VARCHAR(100), tags JSON, deleted_at DATETIME NULL)"
    ))
    db.session.execute(text(
        "INSERT INTO contact_profile (wxid, remark, tags) VALUES "
        "('wxid_u', '旧备注', '[\"旧标签\"]'), "
        "('1@chatroom', '群旧备注', '[]')"
    ))
    db.session.commit()

    _backfill_remark_config()
    _archive_contact_profile()

    u = ContactRemarkConfig.query.filter_by(target_wxid="wxid_u").one()
    assert u.scope_type == "user"
    assert u.remark_name == "旧备注"
    assert u.tags == ["旧标签"]
    g1 = ContactRemarkConfig.query.filter_by(target_wxid="1@chatroom").one()
    assert g1.scope_type == "group"
    assert g1.remark_name == "群旧备注"

    tables = db.session.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%contact_profile%'"
    )).scalars().all()
    assert "_archived_contact_profile_20261116" in tables
    assert "contact_profile" not in tables

    # 幂等：迁移重复执行无副作用（旧表已归档，两函数直接跳过）
    _backfill_remark_config()
    _archive_contact_profile()
    assert ContactRemarkConfig.query.count() == 2


def test_backfill_skips_existing_config_rows(client):
    """新表同键行已存在时跳过搬迁——不覆盖用户已保存的新值。"""
    db.session.execute(text(
        "CREATE TABLE contact_profile ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "wxid VARCHAR(64), remark VARCHAR(100), tags JSON, deleted_at DATETIME NULL)"
    ))
    db.session.execute(text("INSERT INTO contact_profile (wxid, remark) VALUES ('wxid_u', '旧备注')"))
    db.session.add(ContactRemarkConfig(scope_type="user", target_wxid="wxid_u", remark_name="新备注"))
    db.session.commit()

    _backfill_remark_config()

    rows = ContactRemarkConfig.query.filter_by(target_wxid="wxid_u").all()
    assert len(rows) == 1
    assert rows[0].remark_name == "新备注"


def test_soft_delete_restore(client):
    """配置行被软删除后再保存：复活旧行（同 id），不撞唯一键。"""
    conv = make_conv("wxid_u")
    url = f"/api/contacts/-{conv.id}/remark-config"
    client.put(url, json={"remark_name": "第一次"})
    row = ContactRemarkConfig.query.filter_by(target_wxid="wxid_u").one()
    row.soft_delete()
    db.session.commit()

    resp = client.put(url, json={"remark_name": "第二次"})
    assert resp.get_json()["code"] == 0
    rows = ContactRemarkConfig.query.filter_by(target_wxid="wxid_u").all()
    assert len(rows) == 1
    assert rows[0].id == row.id
    assert rows[0].deleted_at is None
    assert rows[0].remark_name == "第二次"
