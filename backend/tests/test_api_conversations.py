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
    c = make_conv(wxid="wxid_c", last_msg="置顶", last_msg_at=datetime(2026, 10, 29, 8, 0, 0), pinned=1)

    resp = client.get("/api/conversations")
    body = resp.get_json()

    assert resp.status_code == 200
    assert body["code"] == 0
    order = [c["id"] for c in body["data"]]
    assert order == [c.id, b.id, a.id]
    assert a.id and b.id


def test_list_excludes_deleted(client):
    """软删除的会话不出现在列表里。"""
    conv = make_conv(wxid="wxid_dead")
    conv.deleted_at = db.func.now()
    db.session.commit()

    resp = client.get("/api/conversations")

    assert resp.get_json()["data"] == []


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


def test_list_masks_wxid(client):
    """脱敏契约：会话出参不含 wxid；未解析名称 → name=None + alias，头像一并匿名。"""
    named = make_conv(wxid="wxid_named", name="客户甲", avatar="http://a.jpg")
    unnamed = make_conv(wxid="wxid_anon_99")

    data = client.get("/api/conversations").get_json()["data"]
    by_id = {c["id"]: c for c in data}
    n, u = by_id[named.id], by_id[unnamed.id]

    # 已解析：名称/头像正常下发，附匿名标识
    assert n["name"] == "客户甲"
    assert n["avatar"] == "http://a.jpg"
    assert "wxid" not in n
    assert n["alias"]

    # 未解析：名称与头像均为空，仅匿名标识可辨
    assert u["name"] is None
    assert u["avatar"] is None
    assert "wxid" not in u
    assert u["alias"]


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


def test_messages_masks_wxid(client):
    """脱敏契约：消息出参不含 sender_wxid；无昵称发言人 → 匿名编码，头像随之匿名。"""
    conv = make_conv(wxid="wxid_anon_m")
    # 生产入库口径：单聊收到的消息 sender_name 快照存的就是 wxid 原文
    make_msg(conv.id, direction=Message.DIR_IN,
             sender_wxid="wxid_anon_m", sender_name="wxid_anon_m")

    m = client.get(f"/api/conversations/{conv.id}/messages").get_json()["data"]["messages"][0]

    assert "sender_wxid" not in m
    assert m["sender_name"].startswith("匿名 ")
    assert m["sender_avatar"] is None
    assert m["sender_alias"]


def test_messages_empty_conversation(client):
    """空会话：返回空数组而不是报错。"""
    conv = make_conv(wxid="wxid_empty")

    data = client.get(f"/api/conversations/{conv.id}/messages").get_json()["data"]

    assert data["messages"] == []
    assert data["next_before_id"] is None


# ---------- 主动发起会话（POST /api/conversations，按 contact_id） ----------


def test_open_conversation_creates(client):
    """通讯录里有的联系人：按 contact_id 建新会话并返回。"""
    c = Contact(openid="dev01", wxid="wxid_new", type=Contact.TYPE_FRIEND)
    db.session.add(c)
    db.session.commit()

    resp = client.post("/api/conversations", json={"contact_id": c.id, "chat_type": 1})
    body = resp.get_json()

    assert resp.status_code == 200
    assert body["code"] == 0
    assert "wxid" not in body["data"]  # 出参不带 wxid
    conv = Conversation.query.filter_by(openid="dev01", wxid="wxid_new").one()
    assert conv.chat_type == Conversation.CHAT_SINGLE


def test_open_conversation_returns_existing(client):
    """已有会话：直接返回既有会话，不重复建。"""
    conv = make_conv(wxid="wxid_x")
    c = Contact(openid="dev01", wxid="wxid_x", type=Contact.TYPE_FRIEND)
    db.session.add(c)
    db.session.commit()

    data = client.post(
        "/api/conversations", json={"contact_id": c.id, "chat_type": 1}
    ).get_json()["data"]

    assert data["id"] == conv.id
    assert Conversation.query.count() == 1


def test_open_conversation_group(client):
    """群聊发起：chat_type=2 匹配群联系人。"""
    c = Contact(openid="dev01", wxid="9@chatroom", type=Contact.TYPE_GROUP)
    db.session.add(c)
    db.session.commit()

    data = client.post(
        "/api/conversations", json={"contact_id": c.id, "chat_type": 2}
    ).get_json()["data"]

    assert data["chat_type"] == 2


def test_open_conversation_fallback_conversation_row(client):
    """补集回退：通讯录未同步的老会话，contact_id 可按会话行号反查发起。"""
    conv = make_conv(wxid="wxid_legacy", chat_type=Conversation.CHAT_SINGLE)

    resp = client.post("/api/conversations", json={"contact_id": conv.id, "chat_type": 1})

    assert resp.status_code == 200
    assert resp.get_json()["data"]["id"] == conv.id


def test_open_conversation_negative_extra_id(client):
    """通讯录补集条目出参 id 为负（-conv.id）：发起会话按 -id 反查会话行。"""
    conv = make_conv(wxid="wxid_legacy2", chat_type=Conversation.CHAT_SINGLE)

    resp = client.post("/api/conversations", json={"contact_id": -conv.id, "chat_type": 1})

    assert resp.status_code == 200
    assert resp.get_json()["data"]["id"] == conv.id


def test_open_conversation_requires_roster(client):
    """contact_id 无对应联系人/会话：404 拒绝，防乱造会话。"""
    resp = client.post("/api/conversations", json={"contact_id": 99999, "chat_type": 1})

    assert resp.status_code == 404
    assert Conversation.query.count() == 0


def test_open_conversation_type_mismatch(client):
    """类型不匹配：群 id 按 chat_type=1 发起 → 通讯录查无此类型 → 404。"""
    c = Contact(openid="dev01", wxid="9@chatroom", type=Contact.TYPE_GROUP)
    db.session.add(c)
    db.session.commit()

    resp = client.post("/api/conversations", json={"contact_id": c.id, "chat_type": 1})

    assert resp.status_code == 404


def test_open_conversation_validates_params(client):
    """参数缺失/非法：400。"""
    r1 = client.post("/api/conversations", json={"chat_type": 1})
    r2 = client.post("/api/conversations", json={"contact_id": 1, "chat_type": 9})
    r3 = client.post("/api/conversations", json={"contact_id": 1, "chat_type": "abc"})

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


def test_patch_marks_unread(client):
    """read=false 标为未读：未读数落库记 1（微信同款）。"""
    conv = make_conv(wxid="wxid_unread", unread_count=0)

    resp = client.patch(f"/api/conversations/{conv.id}", json={"read": False})

    body = resp.get_json()
    assert resp.status_code == 200
    assert body["data"]["unread_count"] == 1
    assert Conversation.query.filter_by(id=conv.id).one().unread_count == 1


def test_patch_mute(client):
    """muted 开关：0/1 落库并在返回值里带回。"""
    conv = make_conv(wxid="wxid_mute")

    r1 = client.patch(f"/api/conversations/{conv.id}", json={"muted": 1})
    assert r1.get_json()["data"]["muted"] == 1
    assert Conversation.query.filter_by(id=conv.id).one().muted == 1

    r2 = client.patch(f"/api/conversations/{conv.id}", json={"muted": 0})
    assert r2.get_json()["data"]["muted"] == 0
    assert Conversation.query.filter_by(id=conv.id).one().muted == 0


def test_patch_conv_not_found(client):
    """会话不存在/跨设备：404。"""
    resp = client.patch("/api/conversations/999", json={"read": True})

    assert resp.status_code == 404


def test_patch_validates_params(client):
    """空 body、非法 pinned、非法 read、非法 muted：400。"""
    conv = make_conv(wxid="wxid_v", unread_count=1)

    r1 = client.patch(f"/api/conversations/{conv.id}", json={})
    r2 = client.patch(f"/api/conversations/{conv.id}", json={"pinned": 2})
    r3 = client.patch(f"/api/conversations/{conv.id}", json={"read": "yes"})
    r4 = client.patch(f"/api/conversations/{conv.id}", json={"muted": 2})

    assert r1.status_code == 400
    assert r2.status_code == 400
    assert r3.status_code == 400
    assert r4.status_code == 400
