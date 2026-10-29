"""收消息轮询单测：mock 中间方 get_message，验证入库与游标。"""
from datetime import datetime, timedelta

from backend.extensions import db
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.models.sync_cursor import SyncCursor
from backend.sync import message_sync


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

    def fake_call(action, params=None, uuid=None):
        captured["action"] = action
        captured["params"] = params
        return body

    monkeypatch.setattr(message_sync.middle_client, "call", fake_call)
    return captured


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

    def boom(action, params=None, uuid=None):
        raise MiddleApiError("设备离线")

    monkeypatch.setattr(message_sync.middle_client, "call", boom)

    message_sync.sync_once(app)  # 不应抛异常

    assert Message.query.count() == 0
    assert SyncCursor.query.count() == 0  # 游标行都没建，等下一轮


def test_sync_pull_params(app, monkeypatch):
    """拉取参数：带 start_create_time 和分页。"""
    captured = patch_pull(monkeypatch, make_body([]))

    message_sync.sync_once(app)

    assert captured["action"] == "get_message"
    assert "start_create_time" in captured["params"]
    assert captured["params"]["page_size"] == 100
