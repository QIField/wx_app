"""会话列表与聊天记录接口单测。"""
from datetime import datetime

from backend.extensions import db
from backend.models.contact import Contact
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


# ---------- 主动发起会话（POST /api/conversations） ----------


def test_open_conversation_creates(client):
    """通讯录里有的联系人：建新会话并返回。"""
    db.session.add(Contact(openid="dev01", wxid="wxid_new", type=Contact.TYPE_FRIEND))
    db.session.commit()

    resp = client.post("/api/conversations", json={"wxid": "wxid_new", "chat_type": 1})
    body = resp.get_json()

    assert resp.status_code == 200
    assert body["code"] == 0
    assert body["data"]["wxid"] == "wxid_new"
    conv = Conversation.query.filter_by(openid="dev01", wxid="wxid_new").one()
    assert conv.chat_type == Conversation.CHAT_SINGLE


def test_open_conversation_returns_existing(client):
    """已有会话：直接返回既有会话，不重复建。"""
    conv = make_conv(wxid="wxid_x")
    db.session.add(Contact(openid="dev01", wxid="wxid_x", type=Contact.TYPE_FRIEND))
    db.session.commit()

    data = client.post("/api/conversations", json={"wxid": "wxid_x", "chat_type": 1}).get_json()["data"]

    assert data["id"] == conv.id
    assert Conversation.query.count() == 1


def test_open_conversation_group(client):
    """群聊发起：chat_type=2 匹配群联系人。"""
    db.session.add(Contact(openid="dev01", wxid="9@chatroom", type=Contact.TYPE_GROUP))
    db.session.commit()

    data = client.post("/api/conversations", json={"wxid": "9@chatroom", "chat_type": 2}).get_json()["data"]

    assert data["chat_type"] == 2


def test_open_conversation_requires_roster(client):
    """通讯录里没有的 wxid：404 拒绝，防乱造会话。"""
    resp = client.post("/api/conversations", json={"wxid": "wxid_ghost", "chat_type": 1})

    assert resp.status_code == 404
    assert Conversation.query.count() == 0


def test_open_conversation_type_mismatch(client):
    """类型不匹配：群 id 按 chat_type=1 发起 → 通讯录查无此类型 → 404。"""
    db.session.add(Contact(openid="dev01", wxid="9@chatroom", type=Contact.TYPE_GROUP))
    db.session.commit()

    resp = client.post("/api/conversations", json={"wxid": "9@chatroom", "chat_type": 1})

    assert resp.status_code == 404


def test_open_conversation_validates_params(client):
    """参数缺失/非法：400。"""
    r1 = client.post("/api/conversations", json={"chat_type": 1})
    r2 = client.post("/api/conversations", json={"wxid": "a", "chat_type": 9})
    r3 = client.post("/api/conversations", json={"wxid": "a", "chat_type": "abc"})

    assert r1.status_code == 400
    assert r2.status_code == 400
    assert r3.status_code == 400


# ---------- 会话操作（PATCH /api/conversations/{id}） ----------


def test_patch_marks_read(client):
    """read=true：未读数落库清零（否则重拉列表会把红点带回来）。"""
    conv = make_conv(wxid="wxid_read", unread_count=5)

    resp = client.patch(f"/api/conversations/{conv.id}", json={"read": True})
    body = resp.get_json()

    assert resp.status_code == 200
    assert body["data"]["unread_count"] == 0
    assert Conversation.query.filter_by(id=conv.id).one().unread_count == 0


def test_patch_pins_and_read(client):
    """置顶与清未读可以同时提交。"""
    conv = make_conv(wxid="wxid_pin", unread_count=2)

    data = client.patch(
        f"/api/conversations/{conv.id}", json={"pinned": 1, "read": True}
    ).get_json()["data"]

    assert data["pinned"] == 1
    assert Conversation.query.filter_by(id=conv.id).one().unread_count == 0


def test_patch_conv_not_found(client):
    """会话不存在/跨设备：404。"""
    resp = client.patch("/api/conversations/999", json={"read": True})

    assert resp.status_code == 404


def test_patch_validates_params(client):
    """空 body、非法 pinned、非法 read：400。"""
    conv = make_conv(wxid="wxid_v", unread_count=1)

    r1 = client.patch(f"/api/conversations/{conv.id}", json={})
    r2 = client.patch(f"/api/conversations/{conv.id}", json={"pinned": 2})
    r3 = client.patch(f"/api/conversations/{conv.id}", json={"read": "yes"})

    assert r1.status_code == 400
    assert r2.status_code == 400
    assert r3.status_code == 400
