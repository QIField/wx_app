"""contact_sync 单测：通讯录全量入库 + 缺资料补齐（mock 中间方）。"""
import json

import pytest

from backend.extensions import db
from backend.models.contact import Contact
from backend.sync import contact_sync, friend_profile, group_profile, profile_sync

from backend.tests.conftest import make_user


@pytest.fixture(autouse=True)
def device(app):
    """通讯录同步按设备遍历：造一台 o1 设备的启用账号。"""
    return make_user(open_ids=["o1"])


def _patch_catalog(monkeypatch, friends, chatrooms, ghs=None):
    """mock fetch_contacts_list_cache：返回实测结构（纯字符串数组）。"""
    record = {"uuid": "u", "processing_result": json.dumps(
        {"ret": 200, "msg": "操作成功",
         "data": {"friends": friends, "chatrooms": chatrooms, "ghs": ghs or []}})}
    monkeypatch.setattr(contact_sync.client, "call", lambda *a, **k: {})
    monkeypatch.setattr(contact_sync, "query_record",
                        lambda module, action, u, openid="": record)


def test_roster_missing_contact_marked_deleted_then_restored(app, monkeypatch):
    """好友从名册消失 → deleted_at；重新出现 → 复活同一行（不新增）。"""
    _patch_catalog(monkeypatch, ["wxid_a", "wxid_b"], [])
    contact_sync.sync_contacts()

    _patch_catalog(monkeypatch, ["wxid_a"], [])
    contact_sync.sync_contacts()
    db.session.expire_all()
    gone = Contact.query.filter_by(openid="o1", wxid="wxid_b").one()
    assert gone.deleted_at is not None
    assert Contact.query.filter_by(openid="o1").count() == 2  # 行仍在

    _patch_catalog(monkeypatch, ["wxid_a", "wxid_b"], [])
    contact_sync.sync_contacts()
    db.session.expire_all()
    back = Contact.query.filter_by(openid="o1", wxid="wxid_b").one()
    assert back.deleted_at is None
    assert back.id == gone.id


def test_roster_empty_catalog_does_not_mass_delete(app, monkeypatch):
    """中间方偶发返回空清单时，不能把整份通讯录标记为已删除。"""
    _patch_catalog(monkeypatch, ["wxid_a", "wxid_b"], [])
    contact_sync.sync_contacts()

    _patch_catalog(monkeypatch, [], [])
    contact_sync.sync_contacts()
    db.session.expire_all()
    assert all(c.deleted_at is None for c in Contact.query.filter_by(openid="o1").all())


def test_roster_upsert_friends_and_groups(app, monkeypatch):
    """好友+群 wxid 入库；ghs 公众号按要求不入通讯录。"""
    _patch_catalog(monkeypatch, ["wxid_a", "wxid_b"], ["1@chatroom"], ghs=["gh_official"])

    contact_sync.sync_contacts()

    by_wxid = {c.wxid: c for c in Contact.query.all()}
    assert set(by_wxid) == {"wxid_a", "wxid_b", "1@chatroom"}
    assert by_wxid["wxid_a"].type == Contact.TYPE_FRIEND
    assert by_wxid["1@chatroom"].type == Contact.TYPE_GROUP


def test_roster_no_duplicates_on_rerun(app, monkeypatch):
    """重复同步不产生重复行（openid+wxid 唯一约束 + upsert 先查后插）。"""
    _patch_catalog(monkeypatch, ["wxid_a"], ["1@chatroom"])

    contact_sync.sync_contacts()
    contact_sync.sync_contacts()

    assert Contact.query.count() == 2


def test_fetch_failure_is_silent(app, monkeypatch):
    """拉取失败（无记录/ret!=200）返回空，不建任何行。"""
    monkeypatch.setattr(contact_sync.client, "call", lambda *a, **k: {})
    monkeypatch.setattr(contact_sync, "query_record",
                        lambda module, action, u, openid="": None)

    contact_sync.sync_contacts()

    assert Contact.query.count() == 0


def test_fill_friend_profiles(app, monkeypatch):
    """缺资料好友批量补昵称头像。"""
    _patch_catalog(monkeypatch, ["wxid_a"], [])
    contact_sync.sync_contacts()
    monkeypatch.setattr(
        friend_profile, "query_brief_infos",
        lambda wxids, openid="": {"wxid_a": {"nickname": "张三", "head_img_url": "http://a/1.jpg"}},
    )

    contact_sync.fill_missing_profiles("o1")

    db.session.expire_all()
    c = Contact.query.filter_by(wxid="wxid_a").one()
    assert c.name == "张三"
    assert c.avatar == "http://a/1.jpg"


def test_fill_friends_batch_cap(app, monkeypatch):
    """每轮最多 FRIEND_PROFILE_BATCHES 批，每批 ≤ FRIEND_BATCH 个，剩余下轮。"""
    _patch_catalog(monkeypatch, [f"wxid_{i:03d}" for i in range(250)], [])
    contact_sync.sync_contacts()

    calls = []

    def fake_brief(wxids, openid=""):
        calls.append(list(wxids))
        return {w: {"nickname": f"名{i}", "head_img_url": "http://a/x.jpg"}
                for i, w in enumerate(wxids)}

    monkeypatch.setattr(friend_profile, "query_brief_infos", fake_brief)

    contact_sync.fill_missing_profiles("o1")

    assert len(calls) == contact_sync.FRIEND_PROFILE_BATCHES
    assert all(len(b) <= friend_profile.FRIEND_BATCH for b in calls)
    assert sum(len(b) for b in calls) == contact_sync.FRIEND_PROFILE_BATCHES * friend_profile.FRIEND_BATCH
    # 剩余没补到的留给下一轮
    assert Contact.query.filter(Contact.avatar.is_(None)).count() == 50


def test_fill_friends_gives_up_on_empty_batch(app, monkeypatch):
    """整批拿不到资料（如中间方失败）：不再空转烧完批数。"""
    _patch_catalog(monkeypatch, ["wxid_a", "wxid_b"], [])
    contact_sync.sync_contacts()

    calls = []
    monkeypatch.setattr(
        friend_profile, "query_brief_infos",
        lambda wxids, openid="": calls.append(list(wxids)) or {},
    )

    contact_sync.fill_missing_profiles("o1")

    assert len(calls) == 1


def test_fill_groups(app, monkeypatch):
    """缺资料群逐个补群名/群头像。"""
    _patch_catalog(monkeypatch, [], ["1@chatroom"])
    contact_sync.sync_contacts()
    monkeypatch.setattr(
        group_profile, "query_chatroom_info",
        lambda chatroom_id, openid="": {"nickname": "报价群", "avatar": "http://a/g.jpg"},
    )

    contact_sync.fill_missing_profiles("o1")

    db.session.expire_all()
    c = Contact.query.filter_by(wxid="1@chatroom").one()
    assert c.name == "报价群"
    assert c.avatar == "http://a/g.jpg"


def test_sync_profiles_runs_contact_sync(app, monkeypatch):
    """sync_profiles 兜底轮编排包含通讯录同步。"""
    called = {"n": 0}
    monkeypatch.setattr(contact_sync, "sync_contacts",
                        lambda: called.__setitem__("n", called["n"] + 1))
    monkeypatch.setattr(group_profile, "sync_group_names", lambda: None)
    monkeypatch.setattr(friend_profile, "sync_friend_profiles", lambda: None)

    profile_sync.sync_profiles(app)

    assert called["n"] == 1
