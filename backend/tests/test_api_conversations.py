"""会话列表与聊天记录接口单测。"""
from datetime import datetime

from backend.extensions import db
from backend.models.conversation import Conversation
from backend.models.message import Message


def make_conv(**over):
    fields = {"chat_type": 1}
    fields.update(over)
    conv = Conversation(openid="dev01", **fields)
    db.session.add(conv)
    db.session.commit()
    return conv


def make_msg(conv_id, **over):
    fields = {
        "msg_type": Message.MSG_TEXT,
        "direction": Message.DIR_IN,
        "content": "hello",
    }
    fields.update(over)
    msg = Message(conversation_id=conv_id, **fields)
    db.session.add(msg)
    db.session.commit()
    return msg


def test_list_conversations_order(client):
    """置顶优先，其余按最后消息时间倒序。"""
    a = make_conv(wxid="wxid_a", last_msg="早", last_msg_at=datetime(2026, 10, 29, 9, 0, 0))
    b = make_conv(wxid="wxid_b", last_msg="晚", last_msg_at=datetime(2026, 10, 29, 11, 0, 0))
    make_conv(wxid="wxid_c", last_msg="置顶", last_msg_at=datetime(2026, 10, 29, 8, 0, 0), pinned=1)

    resp = client.get("/api/conversations")
    body = resp.get_json()

    assert resp.status_code == 200
    assert body["code"] == 0
    order = [c["wxid"] for c in body["data"]]
    assert order == ["wxid_c", "wxid_b", "wxid_a"]
    assert a.id and b.id


def test_list_excludes_deleted(client):
    """软删除的会话不出现在列表里。"""
    conv = make_conv(wxid="wxid_dead")
    conv.deleted_at = db.func.now()
    db.session.commit()

    resp = client.get("/api/conversations")

    assert [c["wxid"] for c in resp.get_json()["data"]] == []


def test_list_fields(client):
    """列表字段齐全：未读、摘要、类型。"""
    make_conv(
        wxid="wxid_c",
        name="群名",
        chat_type=2,
        unread_count=3,
        last_msg="[图片]",
        last_msg_at=datetime(2026, 10, 29, 11, 0, 0),
    )

    data = client.get("/api/conversations").get_json()["data"][0]

    assert data["name"] == "群名"
    assert data["chat_type"] == 2
    assert data["unread_count"] == 3
    assert data["last_msg"] == "[图片]"
    assert data["last_msg_at"] == "2026-10-29 11:00:00"


def test_messages_pagination(client):
    """分页：倒序取一页再正序返回，next_before_id 指向更早一页。"""
    conv = make_conv(wxid="wxid_p")
    ids = [make_msg(conv.id).id for _ in range(3)]  # id 1,2,3

    resp = client.get(f"/api/conversations/{conv.id}/messages?page_size=2")
    body = resp.get_json()["data"]

    assert [m["id"] for m in body["messages"]] == [ids[1], ids[2]]  # 最新2条，正序
    assert body["next_before_id"] == ids[1]

    resp2 = client.get(f"/api/conversations/{conv.id}/messages?page_size=2&before_id={ids[1]}")
    body2 = resp2.get_json()["data"]

    assert [m["id"] for m in body2["messages"]] == [ids[0]]
    assert body2["next_before_id"] is None  # 没有更早的了


def test_messages_conv_not_found(client):
    """会话不存在：404。"""
    resp = client.get("/api/conversations/999/messages")
    assert resp.status_code == 404


def test_messages_fields(client):
    """消息字段齐全：方向、状态、payload。"""
    conv = make_conv(wxid="wxid_f")
    make_msg(
        conv.id,
        direction=Message.DIR_OUT,
        status=Message.ST_SENT,
        sender_name="客服",
        payload={"img_url": "http://x"},
    )

    m = client.get(f"/api/conversations/{conv.id}/messages").get_json()["data"]["messages"][0]

    assert m["direction"] == 2
    assert m["status"] == 1
    assert m["sender_name"] == "客服"
    assert m["payload"] == {"img_url": "http://x"}


def test_messages_empty_conversation(client):
    """空会话：返回空数组而不是报错。"""
    conv = make_conv(wxid="wxid_empty")

    data = client.get(f"/api/conversations/{conv.id}/messages").get_json()["data"]

    assert data["messages"] == []
    assert data["next_before_id"] is None
