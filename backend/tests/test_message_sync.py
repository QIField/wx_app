"""收消息轮询单测：mock 中间方 get_message，验证入库与游标。"""
from datetime import datetime, timedelta

import json
import pytest

from backend.extensions import db
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.models.sync_cursor import SyncCursor
from backend.sync import message_sync

from backend.tests.conftest import make_user


@pytest.fixture(autouse=True)
def device(app):
    """多设备后：同步以绑定 open_id 的启用账号为准，造一台 dev01 设备。"""
    return make_user(open_id="dev01")


def make_item(**over):
    """造一条"刚发生"的消息：时间晚于初始游标（首次从最近1小时拉）。"""
    item = {
        "msg_id": "m1001",
        "new_msg_id": "n1001",
        "from_wxid": "wxid_customer",
        "to_wxid": "wxid_me",
        "msg_type": 1,
        "content": "变速箱修好多钱",
        "create_time": (datetime.now() + timedelta(minutes=1)).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    }
    item.update(over)
    return item


def make_body(items):
    return {"code": 0, "msg": "success", "data": {"list": items}}


def patch_pull(monkeypatch, body):
    """替换中间方调用，并记录收到的查询参数。"""
    captured = {}

    def fake_call(module, action, params=None, uuid=None, openid=""):
        captured["module"] = module
        captured["action"] = action
        captured["params"] = params
        captured["openid"] = openid
        return body

    monkeypatch.setattr(message_sync.middle_client, "call", fake_call)
    return captured


def make_real_item(**over):
    """按 2026-10-29 联调实测结构造一条群消息（RFC 1123 时间、字符串类型）。"""
    raw_json = json.dumps({
        "TypeName": "AddMsg",
        "Data": {"MsgId": 1622189713, "NewMsgId": 1920921937912189642,
                 "FromUserName": {"string": "38854524004@chatroom"},
                 "ToUserName": {"string": "wxid_yfm4es06qpzt22"},
                 "CreateTime": 1793268964},
        "Wxid": "wxid_me",
    }, ensure_ascii=False)
    item = {
        "id": 10524,
        "msg_id": "1622189713",
        "from_wxid": "38854524004@chatroom",
        "to_wxid": "wxid_me",
        "msg_type": "1",
        "content": "wxid_iobwbybwbmp622:\n11537649409=盖茨80，原厂220",
        "create_time": "Thu, 29 Oct 2026 18:16:04 GMT",
        "raw_json": raw_json,
    }
    item.update(over)
    return item


def test_sync_saves_real_structure(app, monkeypatch):
    """实测真实结构：群消息拆发言人、RFC1123 时间、字符串类型、raw_json 取 NewMsgId。"""
    patch_pull(monkeypatch, make_body([make_real_item()]))

    message_sync.sync_once(app)

    msg = Message.query.one()
    assert msg.middle_msg_id == "1622189713"
    assert msg.new_msg_id == "1920921937912189642"
    assert msg.msg_type == Message.MSG_TEXT
    assert msg.sender_wxid == "wxid_iobwbybwbmp622"  # 从 content 拆出的发言人
    assert msg.content == "11537649409=盖茨80，原厂220"
    assert msg.direction == Message.DIR_IN
    assert msg.create_time.strftime("%Y-%m-%d %H:%M:%S") == "2026-10-29 18:16:04"


def test_sync_saves_new_message(app, monkeypatch):
    """拉到 1 条新消息：入库 + 建会话 + 未读 1 + 游标推进到消息时间。"""
    patch_pull(monkeypatch, make_body([make_item()]))

    message_sync.sync_once(app)

    msg = Message.query.one()
    assert msg.content == "变速箱修好多钱"
    assert msg.direction == Message.DIR_IN
    assert msg.middle_msg_id == "m1001"

    conv = Conversation.query.one()
    assert conv.wxid == "wxid_customer"
    assert conv.chat_type == Conversation.CHAT_SINGLE
    assert conv.unread_count == 1
    assert conv.last_msg == "变速箱修好多钱"
    assert conv.last_msg_at == msg.create_time

    cursor = SyncCursor.query.one()
    assert cursor.last_sync_time == msg.create_time
    assert cursor.cursor_type == "msg"


def test_sync_dedup_skips_existing(app, monkeypatch):
    """同一 middle_msg_id 再拉到：不重复入库，未读不涨。"""
    patch_pull(monkeypatch, make_body([make_item()]))
    message_sync.sync_once(app)

    message_sync.sync_once(app)

    assert Message.query.count() == 1
    conv = Conversation.query.one()
    assert conv.unread_count == 1


def test_sync_empty_round(app, monkeypatch):
    """空轮：不入库，游标保持初始值（1 小时前）不动。"""
    patch_pull(monkeypatch, make_body([]))

    message_sync.sync_once(app)

    assert Message.query.count() == 0
    assert Conversation.query.count() == 0
    cursor = SyncCursor.query.one()
    assert cursor.last_sync_time <= datetime.now() - timedelta(minutes=30)


def test_sync_out_direction_no_unread(app, monkeypatch):
    """自己发出的消息（is_sender=1）：对方是 to_wxid，未读不涨。"""
    item = make_item(is_sender=1, from_wxid="wxid_me", to_wxid="wxid_customer")
    patch_pull(monkeypatch, make_body([item]))

    message_sync.sync_once(app)

    msg = Message.query.one()
    assert msg.direction == Message.DIR_OUT
    conv = Conversation.query.one()
    assert conv.wxid == "wxid_customer"
    assert conv.unread_count == 0


def test_sync_group_message(app, monkeypatch):
    """群消息（@chatroom 结尾）：会话类型为群聊。"""
    item = make_item(from_wxid="88888888@chatroom")
    patch_pull(monkeypatch, make_body([item]))

    message_sync.sync_once(app)

    conv = Conversation.query.one()
    assert conv.wxid == "88888888@chatroom"
    assert conv.chat_type == Conversation.CHAT_GROUP


def test_sync_pull_error_silent(app, monkeypatch):
    """拉取失败：不崩、游标不动，下一轮重来。"""
    from backend.adapter.client import MiddleApiError

    def boom(action, params=None, uuid=None, openid=""):
        raise MiddleApiError("设备离线")

    monkeypatch.setattr(message_sync.middle_client, "call", boom)

    message_sync.sync_once(app)  # 不应抛异常

    assert Message.query.count() == 0
    assert SyncCursor.query.count() == 0  # 游标行都没建，等下一轮


def test_sync_pull_params(app, monkeypatch):
    """拉取参数：带 start_create_time 和分页，且带设备 openid。"""
    captured = patch_pull(monkeypatch, make_body([]))

    message_sync.sync_once(app)

    assert captured["module"] == "messag_api"
    assert captured["action"] == "get_message"
    assert "start_create_time" in captured["params"]
    assert captured["params"]["page_size"] == 100
    assert captured["openid"] == "dev01"


def test_sync_multi_device_isolated(app, monkeypatch):
    """多设备：两台设备各拉各的游标，会话互不串。"""
    make_user(username="cs02", name="客服02", open_id="dev02")
    bodies = {"dev01": make_body([make_item(msg_id="m1")]),
              "dev02": make_body([make_item(msg_id="m2", from_wxid="wxid_02")])}
    calls = []

    def fake_call(module, action, params=None, uuid=None, openid=""):
        calls.append(openid)
        return bodies[openid]

    monkeypatch.setattr(message_sync.middle_client, "call", fake_call)

    message_sync.sync_once(app)

    assert sorted(calls) == ["dev01", "dev02"]
    assert Conversation.query.filter_by(openid="dev01", wxid="wxid_customer").count() == 1
    assert Conversation.query.filter_by(openid="dev02", wxid="wxid_02").count() == 1
    assert SyncCursor.query.count() == 2  # 两台设备各一条游标


def test_sync_triggers_profile_refresh(app, monkeypatch):
    """新消息入库后触发资料补拉：带本轮会话 id（覆盖 conftest 的全局 mock）。"""
    from backend.sync import profile_sync

    got = []
    monkeypatch.setattr(profile_sync, "refresh_missing_profiles",
                        lambda openid, ids: got.append((openid, list(ids))))
    patch_pull(monkeypatch, make_body([make_item()]))

    message_sync.sync_once(app)

    assert len(got) == 1
    openid, ids = got[0]
    assert openid == "dev01"
    assert ids == [Conversation.query.one().id]


def test_sync_disabled_user_not_polled(app, device, monkeypatch):
    """停用账号或未绑定设备的账号不参与同步。"""
    device.status = 0
    db.session.commit()
    calls = []

    def fake_call(module, action, params=None, uuid=None, openid=""):
        calls.append(openid)
        return make_body([])

    monkeypatch.setattr(message_sync.middle_client, "call", fake_call)

    message_sync.sync_once(app)

    assert calls == []
