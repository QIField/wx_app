"""profile_sync 单测：群名/好友资料解析（mock 中间方，不真调接口）。"""
import json

import pytest

from backend.extensions import db
from backend.models.conversation import Conversation
from backend.sync import profile_sync


@pytest.fixture(autouse=True)
def clean_fail_counts():
    """每个用例前清空失败计数（模块级状态）。"""
    profile_sync._fail_counts.clear()
    yield
    profile_sync._fail_counts.clear()


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
    monkeypatch.setattr(profile_sync, "broadcast", lambda event, data: bucket.append((event, data)))


def test_group_name_synced(app, group_conv, monkeypatch):
    """群名+群头像解析成功（2026-10-30 实测结构）：写库 + 广播。"""
    bucket = []
    _patch_broadcast(monkeypatch, bucket)
    monkeypatch.setattr(profile_sync.client, "call", lambda *a, **k: {})
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
        profile_sync, "_query_record_once",
        lambda module, action, u: {"uuid": u, "processing_result": real_result},
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

    def fake_call(module, action, params=None, uuid=None):
        calls.append(action)
        return {}

    _patch_broadcast(monkeypatch, [])
    monkeypatch.setattr(profile_sync.client, "call", fake_call)
    monkeypatch.setattr(profile_sync, "_query_record_once", lambda module, action, u: None)
    monkeypatch.setattr(profile_sync, "_fetch_friend_wxids", lambda: [])

    for _ in range(8):
        profile_sync.sync_profiles(app)

    # 反复失败后被限流：下发总量不超过 MAX_FAIL_RETRY 次
    assert len(calls) <= profile_sync.MAX_FAIL_RETRY


def test_friend_profile_synced(app, single_conv, monkeypatch):
    """好友昵称+头像批量更新（brief_info 结构未知，靠 _pick 兜底）。"""
    bucket = []
    _patch_broadcast(monkeypatch, bucket)
    monkeypatch.setattr(profile_sync.client, "call", lambda *a, **k: {})
    monkeypatch.setattr(profile_sync, "_fetch_friend_wxids", lambda: ["wxid_friend"])
    monkeypatch.setattr(
        profile_sync, "_query_brief_infos",
        lambda wxids: {"wxid_friend": {"nickname": "张师傅", "head_img_url": "http://a/x.jpg"}},
    )

    profile_sync.sync_profiles(app)

    assert single_conv.name == "张师傅"
    assert single_conv.avatar == "http://a/x.jpg"
    assert ("conv_updated", {"conversation_id": single_conv.id}) in bucket


def test_friend_not_in_list_skipped(app, single_conv, monkeypatch):
    """好友列表里没有的会话不处理（不是好友的单聊不拉资料）。"""
    _patch_broadcast(monkeypatch, [])
    monkeypatch.setattr(profile_sync.client, "call", lambda *a, **k: {})
    monkeypatch.setattr(profile_sync, "_fetch_friend_wxids", lambda: ["wxid_other"])
    called = {"brief": False}

    def fake_brief(wxids):
        called["brief"] = True
        return {}

    monkeypatch.setattr(profile_sync, "_query_brief_infos", fake_brief)

    profile_sync.sync_profiles(app)

    assert not called["brief"]
    assert single_conv.name is None
