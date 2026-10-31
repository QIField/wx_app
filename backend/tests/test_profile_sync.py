"""profile_sync 单测：群名/好友资料解析（mock 中间方，不真调接口）。

重构说明：实现拆到 group_profile / friend_profile，门面 profile_sync 只编排，
patch 目标相应指向实现模块。
"""
import json

import pytest

from backend.extensions import db
from backend.models.conversation import Conversation
from backend.sync import friend_profile, group_profile, profile_sync, task_query

from backend.tests.conftest import make_user


@pytest.fixture(autouse=True)
def clean_fail_counts():
    """每个用例前清空失败计数（模块级状态）。"""
    group_profile._fail_counts.clear()
    yield
    group_profile._fail_counts.clear()


@pytest.fixture(autouse=True)
def device(app):
    """好友资料解析按设备遍历：造一台 o1 设备的启用账号。"""
    return make_user(open_id="o1")


@pytest.fixture
def group_conv(app):
    # 不再嵌套 with app.app_context()：复用 app fixture 的上下文，
    # 保证和被测代码同一 session（Flask-SQLAlchemy 3 按 app context 分 session）。
    conv = Conversation(openid="o1", wxid="123@chatroom", chat_type=2)
    db.session.add(conv)
    db.session.commit()
    yield conv
    db.session.expire_all()


@pytest.fixture
def single_conv(app):
    conv = Conversation(openid="o1", wxid="wxid_friend", chat_type=1)
    db.session.add(conv)
    db.session.commit()
    yield conv
    db.session.expire_all()


def _patch_broadcast(monkeypatch, bucket):
    fn = lambda event, data: bucket.append((event, data))  # noqa: E731
    monkeypatch.setattr(group_profile, "broadcast", fn)
    monkeypatch.setattr(friend_profile, "broadcast", fn)


def test_group_name_synced(app, group_conv, monkeypatch):
    """群名+群头像解析成功（2026-10-30 实测结构）：写库 + 广播。"""
    bucket = []
    _patch_broadcast(monkeypatch, bucket)
    monkeypatch.setattr(group_profile.client, "call", lambda *a, **k: {})
    real_result = json.dumps({
        "ret": 200, "msg": "操作成功",
        "data": {
            "chatroomId": group_conv.wxid,
            "nickName": "佛山万拓&巴博瑞报价群",
            "smallHeadImgUrl": "https://wx.qlogo.cn/mmcrhead/xx/0",
            "memberList": [{"wxid": "wxid_a", "nickName": "成员甲"}],
        },
    })
    monkeypatch.setattr(
        group_profile, "query_record_once",
        lambda module, action, u, openid="": {"uuid": u, "processing_result": real_result},
    )

    profile_sync.sync_profiles(app)  # 第 1 轮：下发
    profile_sync.sync_profiles(app)  # 第 2 轮：收割

    db.session.expire_all()  # 强制重新加载，读到 sync_profiles 提交的最新值

    assert group_conv.name == "佛山万拓&巴博瑞报价群"
    assert group_conv.avatar == "https://wx.qlogo.cn/mmcrhead/xx/0"
    assert ("conv_updated", {"conversation_id": group_conv.id}) in bucket


def test_group_fail_retry_cap(app, group_conv, monkeypatch):
    """失败 3 次后放弃：不再下发请求。"""
    calls = []

    def fake_call(module, action, params=None, uuid=None, openid=""):
        calls.append(action)
        return {}

    _patch_broadcast(monkeypatch, [])
    monkeypatch.setattr(group_profile.client, "call", fake_call)
    monkeypatch.setattr(group_profile, "query_record_once",
                        lambda module, action, u, openid="": None)
    monkeypatch.setattr(friend_profile, "fetch_friend_wxids", lambda openid: [])

    for _ in range(8):
        profile_sync.sync_profiles(app)

    # 反复失败后被限流：下发总量不超过 MAX_FAIL_RETRY 次
    assert len(calls) <= group_profile.MAX_FAIL_RETRY


def test_friend_profile_synced(app, single_conv, monkeypatch):
    """好友昵称+头像批量更新（brief_info 结构未知，靠 pick 兜底）。"""
    bucket = []
    _patch_broadcast(monkeypatch, bucket)
    monkeypatch.setattr(friend_profile.client, "call", lambda *a, **k: {})
    monkeypatch.setattr(friend_profile, "fetch_friend_wxids", lambda openid: ["wxid_friend"])
    monkeypatch.setattr(
        friend_profile, "query_brief_infos",
        lambda wxids, openid="": {"wxid_friend": {"nickname": "张师傅", "head_img_url": "http://a/x.jpg"}},
    )

    profile_sync.sync_profiles(app)

    assert single_conv.name == "张师傅"
    assert single_conv.avatar == "http://a/x.jpg"
    assert ("conv_updated", {"conversation_id": single_conv.id}) in bucket


def test_friend_not_in_list_skipped(app, single_conv, monkeypatch):
    """好友列表里没有的会话不处理（不是好友的单聊不拉资料）。"""
    _patch_broadcast(monkeypatch, [])
    monkeypatch.setattr(friend_profile.client, "call", lambda *a, **k: {})
    monkeypatch.setattr(friend_profile, "fetch_friend_wxids", lambda openid: ["wxid_other"])
    called = {"brief": False}

    def fake_brief(wxids, openid=""):
        called["brief"] = True
        return {}

    monkeypatch.setattr(friend_profile, "query_brief_infos", fake_brief)

    profile_sync.sync_profiles(app)

    assert not called["brief"]
    assert single_conv.name is None


# ---------- 消息触发的立即补拉 ----------

# conftest 的 autouse 夹具全局 mock 了 refresh_missing_profiles（收消息链路防休眠）；
# 采集期先存住真实函数，专项用例用它恢复。
_REAL_REFRESH = profile_sync.refresh_missing_profiles


@pytest.fixture
def real_refresh(monkeypatch):
    """覆盖全局 mock，恢复真实的立即补拉函数。"""
    monkeypatch.setattr(profile_sync, "refresh_missing_profiles", _REAL_REFRESH)


def test_refresh_single_on_message(app, single_conv, monkeypatch, real_refresh):
    """消息触发补拉：缺资料的单聊立即批量查询并更新 + 广播。"""
    bucket = []
    _patch_broadcast(monkeypatch, bucket)
    monkeypatch.setattr(friend_profile.client, "call", lambda *a, **k: {})
    monkeypatch.setattr(
        friend_profile, "query_brief_infos",
        lambda wxids, openid="": {"wxid_friend": {"nickname": "李师傅", "head_img_url": "http://a/1.jpg"}},
    )

    profile_sync.refresh_missing_profiles("o1", [single_conv.id])

    db.session.expire_all()
    assert single_conv.name == "李师傅"
    assert single_conv.avatar == "http://a/1.jpg"
    assert ("conv_updated", {"conversation_id": single_conv.id}) in bucket


def test_refresh_skips_complete_profile(app, monkeypatch, real_refresh):
    """资料齐全的会话不发起任何请求。"""
    conv = Conversation(openid="o1", wxid="w1", chat_type=1,
                        name="老王", avatar="http://a/x.jpg")
    db.session.add(conv)
    db.session.commit()

    def boom(*a, **k):
        raise AssertionError("资料齐全不应发起请求")

    monkeypatch.setattr(group_profile.client, "call", boom)
    monkeypatch.setattr(friend_profile.client, "call", boom)

    profile_sync.refresh_missing_profiles("o1", [conv.id])


def test_refresh_group_limit_three(app, monkeypatch, real_refresh):
    """群资料立即补拉每轮最多 GROUP_NOW_LIMIT 个，其余留给兜底轮。"""
    convs = [Conversation(openid="o1", wxid=f"{i}@chatroom", chat_type=2) for i in range(5)]
    db.session.add_all(convs)
    db.session.commit()
    dispatched = []
    _patch_broadcast(monkeypatch, [])

    def fake_call(module, action, params=None, uuid=None, openid=""):
        if action == "chatroom_info":
            dispatched.append(params["chatroom_id"])
        return {}

    monkeypatch.setattr(group_profile.client, "call", fake_call)
    monkeypatch.setattr(group_profile, "query_record",
                        lambda module, action, u, openid="", retries=None: None)

    profile_sync.refresh_missing_profiles("o1", [c.id for c in convs])

    assert len(dispatched) == group_profile.GROUP_NOW_LIMIT


def test_refresh_skip_failed_and_pending(app, group_conv, monkeypatch, real_refresh):
    """失败满 5 次或已在下发流水线中的群：跳过不重复请求。"""
    conv2 = Conversation(openid="o1", wxid="2@chatroom", chat_type=2)
    db.session.add(conv2)
    db.session.commit()
    group_profile._fail_counts[(group_conv.openid, group_conv.wxid)] = group_profile.MAX_FAIL_RETRY
    group_profile._pending["u1"] = (conv2.id, conv2.wxid, conv2.openid)
    dispatched = []
    _patch_broadcast(monkeypatch, [])

    def fake_call(module, action, params=None, uuid=None, openid=""):
        if action == "chatroom_info":
            dispatched.append(params["chatroom_id"])
        return {}

    monkeypatch.setattr(group_profile.client, "call", fake_call)

    profile_sync.refresh_missing_profiles("o1", [group_conv.id, conv2.id])

    assert dispatched == []


def test_refresh_dedup_same_conversation(app, single_conv, monkeypatch, real_refresh):
    """同一会话多条消息只补拉一次（conv_id 去重）。"""
    _patch_broadcast(monkeypatch, [])
    monkeypatch.setattr(friend_profile.client, "call", lambda *a, **k: {})
    brief_calls = []

    def fake_brief(wxids, openid=""):
        brief_calls.append(list(wxids))
        return {}

    monkeypatch.setattr(friend_profile, "query_brief_infos", fake_brief)

    profile_sync.refresh_missing_profiles("o1", [single_conv.id, single_conv.id])

    assert brief_calls == [["wxid_friend"]]


def test_query_brief_infos_parses_real_structure(app, monkeypatch):
    """query_brief_infos 按实测驼峰结构解析（userName/nickName/smallHeadImgUrl）。

    2026-10-30 排查：行标识此前只认 wxid/username，漏了真实返回的 userName，
    导致好友资料永远解析为空、会话一直没头像。
    """
    real_row = {
        "userName": "wxid_1815ubzp53ft12",
        "nickName": "法国红酒",
        "smallHeadImgUrl": "https://wx.qlogo.cn/mmhead/x/0",
    }
    record = {"uuid": "u1", "processing_result": json.dumps(
        {"ret": 200, "msg": "获取联系人信息成功", "data": [real_row]})}
    monkeypatch.setattr(friend_profile.client, "call", lambda *a, **k: {})
    monkeypatch.setattr(friend_profile, "query_record",
                        lambda module, action, u, openid="": record)

    infos = friend_profile.query_brief_infos(["wxid_1815ubzp53ft12"], "o1")

    assert infos == {"wxid_1815ubzp53ft12": {
        "nickname": "法国红酒",
        "head_img_url": "https://wx.qlogo.cn/mmhead/x/0",
    }}


def test_query_record_once_skips_unfinished_task(app, monkeypatch):
    """任务记录存在但 processing_result 未生成：视为未完成返回 None。

    2026-10-30 实测竞态：任务记录下发后立即出现，结果要晚几秒填充；
    旧逻辑行存在即返回，导致立即补拉拿到空结果静默跳过、群一直没头像。
    """
    rows = {
        "u_empty": {"uuid": "u_empty", "processing_result": ""},
        "u_fail": {"uuid": "u_fail", "processing_result": json.dumps({"ret": 500, "msg": "失败"})},
        "u_done": {"uuid": "u_done", "processing_result": json.dumps({"ret": 200, "msg": "操作成功", "data": {}})},
    }

    def fake_call(module, action, params=None, uuid=None, openid=""):
        return {"code": 0, "data": {"list": [rows[uuid]]}}

    monkeypatch.setattr(task_query.client, "call", fake_call)

    assert task_query.query_record_once("group_api", "get_chatroom_info", "u_empty") is None
    assert task_query.query_record_once("group_api", "get_chatroom_info", "u_fail") is rows["u_fail"]
    assert task_query.query_record_once("group_api", "get_chatroom_info", "u_done") is rows["u_done"]
