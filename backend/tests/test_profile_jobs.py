"""资料同步任务队列单测：去重、冷却、任务路由、单设备全量补缺。"""
import pytest

from backend.extensions import db
from backend.models.contact import Contact
from backend.models.conversation import Conversation
from backend.sync import (
    contact_sync,
    friend_profile,
    group_member,
    group_profile,
    profile_jobs,
    profile_sync,
)


@pytest.fixture(autouse=True)
def reset_jobs():
    """每个用例前后清理队列/去重/冷却/群流水线状态（测试环境不启动 worker）。"""
    profile_jobs._reset_for_tests()
    group_profile._pending.clear()
    group_profile._pending_fails.clear()
    group_profile._fail_counts.clear()
    yield
    profile_jobs._reset_for_tests()
    group_profile._pending.clear()
    group_profile._pending_fails.clear()
    group_profile._fail_counts.clear()


def test_enqueue_sweep_dedup(app):
    """兜底轮在队列/执行中时，重复投递被丢弃。"""
    assert profile_jobs.enqueue_sweep(app) is True
    assert profile_jobs.enqueue_sweep(app) is False


def test_enqueue_device_dedup(app):
    """同一设备排队中只保留一个任务，不同设备各自入队。"""
    assert profile_jobs.enqueue_device(app, "o1", reason="login") is True
    assert profile_jobs.enqueue_device(app, "o1", reason="login") is False
    assert profile_jobs.enqueue_device(app, "o2", reason="login") is True


def test_login_cooldown_after_job_done(app):
    """任务执行完后，同一设备在冷却期内不再触发。"""
    assert profile_jobs.enqueue_device(app, "o1", reason="login") is True
    job = profile_jobs._job_queue.get_nowait()  # 模拟 worker 取出并执行完
    profile_jobs._release(job)

    assert profile_jobs.enqueue_device(app, "o1", reason="login") is False


def test_enqueue_login_sync_checks_binding(app):
    """未绑定设备或账号停用：登录触发起不到作用。"""
    from backend.tests.conftest import make_user

    bound = make_user(username="cs21", name="客服21", open_ids=["o1"])
    unbound = make_user(username="cs22", name="客服22")
    disabled = make_user(username="cs23", name="客服23", open_ids=["o2"], status=0)

    assert profile_jobs.enqueue_login_sync(app, bound) is True
    assert profile_jobs.enqueue_login_sync(app, unbound) is False
    assert profile_jobs.enqueue_login_sync(app, disabled) is False


def test_execute_routes_job_type(app, monkeypatch):
    """worker 按任务类型分流：sweep → 全量兜底，device → 单设备全量。"""
    calls = []
    monkeypatch.setattr(profile_sync, "sync_profiles", lambda a: calls.append("sweep"))
    monkeypatch.setattr(profile_sync, "sync_device_full", lambda o: calls.append(o))

    profile_jobs._execute({"type": "sweep"}, app)
    profile_jobs._execute({"type": "device", "openid": "o1"}, app)

    assert calls == ["sweep", "o1"]


def test_login_api_enqueues_bound_device(app, client, monkeypatch):
    """登录成功且已绑定设备时触发一次入队（接口本身不阻塞）。"""
    calls = []
    monkeypatch.setattr(profile_jobs, "enqueue_login_sync",
                        lambda flask_app, user: calls.append(user.username))

    resp = client.post("/api/auth/login", json={"username": "cs01", "password": "123456"})

    assert resp.status_code == 200
    assert calls == ["cs01"]


def test_sync_device_full_routes_four_steps(app, monkeypatch):
    """登录全量：通讯录 → 群收割/补发 → 好友资料 → 群成员头像，全部只作用于该设备。"""
    calls = []
    monkeypatch.setattr(contact_sync, "sync_contacts_of_device",
                        lambda o: calls.append(("contacts", o)))
    monkeypatch.setattr(group_profile, "collect_group_results",
                        lambda openid=None: calls.append(("collect", openid)))
    monkeypatch.setattr(group_profile, "dispatch_group_tasks",
                        lambda openid=None: calls.append(("dispatch", openid)))
    monkeypatch.setattr(friend_profile, "sync_friend_profiles_of_device",
                        lambda o: calls.append(("friend", o)))
    monkeypatch.setattr(group_member, "refresh_avatars_of_device",
                        lambda o: calls.append(("avatars", o)) or False)

    profile_sync.sync_device_full("o1")

    assert calls == [
        ("contacts", "o1"),
        ("collect", "o1"),
        ("dispatch", "o1"),
        ("friend", "o1"),
        ("avatars", "o1"),
    ]


def test_sync_device_full_fills_missing_contact(app, monkeypatch):
    """通讯录全量路径：拉取 wxid 清单后补齐已存在联系人的缺失资料。"""
    contact = Contact(openid="o1", wxid="wxid_c", type=Contact.TYPE_FRIEND)
    db.session.add(contact)
    db.session.commit()
    monkeypatch.setattr(contact_sync, "fetch_contact_wxids",
                        lambda o: {"friends": ["wxid_c"], "chatrooms": []})
    monkeypatch.setattr(friend_profile, "query_brief_infos",
                        lambda wxids, openid="": {"wxid_c": {
                            "nickname": "通讯录好友", "head_img_url": "http://a/c.jpg"}})
    monkeypatch.setattr(friend_profile, "sync_friend_profiles_of_device", lambda o: None)
    monkeypatch.setattr(group_profile, "collect_group_results", lambda openid=None: None)
    monkeypatch.setattr(group_profile, "dispatch_group_tasks", lambda openid=None: None)
    monkeypatch.setattr(group_member, "refresh_avatars_of_device", lambda o: False)

    profile_sync.sync_device_full("o1")

    db.session.expire_all()
    assert contact.name == "通讯录好友"
    assert contact.avatar == "http://a/c.jpg"


def test_sync_device_full_fills_missing_single(app, monkeypatch):
    """好友全量路径：拉好友列表后补齐缺资料的单聊昵称/头像。"""
    conv = Conversation(openid="o1", wxid="wxid_a", chat_type=1)
    db.session.add(conv)
    db.session.commit()
    monkeypatch.setattr(contact_sync, "sync_contacts_of_device", lambda o: None)
    monkeypatch.setattr(group_profile, "collect_group_results", lambda openid=None: None)
    monkeypatch.setattr(group_profile, "dispatch_group_tasks", lambda openid=None: None)
    monkeypatch.setattr(friend_profile, "fetch_friend_wxids", lambda o: ["wxid_a"])
    monkeypatch.setattr(friend_profile, "query_brief_infos",
                        lambda wxids, openid="": {"wxid_a": {
                            "nickname": "李师傅", "head_img_url": "http://a/1.jpg"}})
    monkeypatch.setattr(group_member, "refresh_avatars_of_device", lambda o: False)

    profile_sync.sync_device_full("o1")

    db.session.expire_all()
    assert conv.name == "李师傅"
    assert conv.avatar == "http://a/1.jpg"


def test_sync_device_full_dispatches_missing_group(app, monkeypatch):
    """群资料全量路径：缺失群下发 chatroom_info，只涉及该设备。"""
    conv = Conversation(openid="o1", wxid="g@chatroom", chat_type=2)
    db.session.add(conv)
    db.session.commit()
    monkeypatch.setattr(contact_sync, "sync_contacts_of_device", lambda o: None)
    monkeypatch.setattr(friend_profile, "sync_friend_profiles_of_device", lambda o: None)
    monkeypatch.setattr(group_member, "refresh_avatars_of_device", lambda o: False)
    calls = []
    monkeypatch.setattr(group_profile.client, "call",
                        lambda *a, **k: calls.append(a) or {})

    profile_sync.sync_device_full("o1")

    assert [a[1] for a in calls] == ["chatroom_info"]
    assert len(group_profile._pending) == 1
