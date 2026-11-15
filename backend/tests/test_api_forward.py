"""转发 API 单测：合并卡片+快照、逐条真实下发、参数校验、回看与最近转发。"""
import pytest

from backend.extensions import db
from backend.models.conversation import Conversation
from backend.models.forward_snapshot import ForwardSnapshot
from backend.models.message import Message
from backend.sync import send_service


def make_msg(conv, **over):
    """测试消息工厂：默认一条客户发来的文本。"""
    fields = dict(
        conversation_id=conv.id,
        msg_type=Message.MSG_TEXT,
        direction=Message.DIR_IN,
        sender_wxid="wxid_customer",
        sender_name="张师傅",
        content="变速箱修好多钱",
        status=Message.ST_SENT,
    )
    fields.update(over)
    msg = Message(**fields)
    db.session.add(msg)
    db.session.commit()
    return msg


def make_target_conv():
    """第二个会话：转发目标（同设备 dev01，否则归属校验不通过）。"""
    conv = Conversation(openid="dev01", wxid="wxid_other", chat_type=1, name="李厂长")
    db.session.add(conv)
    db.session.commit()
    return conv


def forward_body(conv, msg_ids, target_ids, mode):
    return {"conv_id": conv.id, "msg_ids": msg_ids, "target_ids": target_ids, "mode": mode}


# ---------- 合并转发 ----------

def test_merge_forward_creates_cards_and_snapshots(client, conversation):
    """合并转发：每个目标一张 msg_type=9 卡片 + 一组快照；源消息不受影响。"""
    target = make_target_conv()
    m1 = make_msg(conversation)
    m2 = make_msg(conversation, content="大概800", direction=Message.DIR_OUT, sender_name=None, operator_name="客服01")

    resp = client.post("/api/messages/forward", json=forward_body(conversation, [m1.id, m2.id], [target.id], "merge"))

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["sent"] == 1

    cards = Message.query.filter_by(conversation_id=target.id, msg_type=Message.MSG_FORWARD).all()
    assert len(cards) == 1
    card = cards[0]
    assert card.direction == Message.DIR_OUT
    assert card.status == Message.ST_SENT  # 本地落库即送达
    assert card.payload["count"] == 2
    assert "张师傅" in card.payload["preview"][0]

    snaps = ForwardSnapshot.query.filter_by(forward_msg_id=card.id).order_by(ForwardSnapshot.seq).all()
    assert [s.content for s in snaps] == ["变速箱修好多钱", "大概800"]

    # 目标会话摘要换聊天记录文案；源消息原样保留
    assert db.session.get(Conversation, target.id).last_msg == "[聊天记录] 2条消息"
    assert db.session.get(Message, m1.id).payload is None


def test_merge_forward_snapshot_api(client, conversation):
    """快照回看接口：按 seq 返回发送者与内容。"""
    target = make_target_conv()
    m1 = make_msg(conversation)
    client.post("/api/messages/forward", json=forward_body(conversation, [m1.id], [target.id], "merge"))
    card = Message.query.filter_by(msg_type=Message.MSG_FORWARD).one()

    resp = client.get(f"/api/messages/{card.id}/forward-snapshot")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["count"] == 1
    assert data["items"][0]["sender_name"] == "张师傅"
    assert data["items"][0]["content"] == "变速箱修好多钱"


def test_snapshot_rejects_non_forward_message(client, conversation):
    """普通消息调回看接口返回 400。"""
    m = make_msg(conversation)
    resp = client.get(f"/api/messages/{m.id}/forward-snapshot")
    assert resp.status_code == 400


def test_forwards_recent_api(client, conversation):
    """最近转发：返回当前操作人发出卡片的去重目标会话。"""
    target = make_target_conv()
    m = make_msg(conversation)
    client.post("/api/messages/forward", json=forward_body(conversation, [m.id], [target.id], "merge"))

    resp = client.get("/api/forwards/recent")
    assert resp.status_code == 200
    items = resp.get_json()["data"]["items"]
    assert [i["conversation_id"] for i in items] == [target.id]
    assert items[0]["name"] == "李厂长"


# ---------- 逐条转发 ----------

def test_single_forward_reposts_plain_text(client, conversation, monkeypatch):
    """逐条转发：按原文下发不带前缀（产品定稿，出处由合并卡片承担）。"""
    monkeypatch.setattr("backend.api.messages.SEND_ENABLED", True)
    captured = []
    monkeypatch.setattr(
        send_service.middle_sender, "post_text",
        lambda **kwargs: captured.append(kwargs["content"]) or {"code": 0},
    )
    target = make_target_conv()
    m1 = make_msg(conversation)  # 客户发的
    m2 = make_msg(conversation, content="马上安排", direction=Message.DIR_OUT, sender_name=None)  # 自己发的

    resp = client.post("/api/messages/forward", json=forward_body(conversation, [m1.id, m2.id], [target.id], "single"))

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data == {"sent": 2, "failed": 0, "skipped": 0}
    assert captured == ["变速箱修好多钱", "马上安排"]
    # 走发送编排：落了发送任务，消息状态发送中
    assert Message.query.filter_by(conversation_id=target.id).count() == 2


def test_single_forward_skips_unsupported_types(client, conversation, monkeypatch):
    """语音等无发送通道的类型跳过不报错，计数进 skipped。"""
    monkeypatch.setattr("backend.api.messages.SEND_ENABLED", True)
    monkeypatch.setattr(send_service.middle_sender, "post_text", lambda **kwargs: {"code": 0})
    target = make_target_conv()
    m_voice = make_msg(conversation, msg_type=Message.MSG_VOICE, content="")

    resp = client.post("/api/messages/forward", json=forward_body(conversation, [m_voice.id], [target.id], "single"))
    assert resp.get_json()["data"] == {"sent": 0, "failed": 0, "skipped": 1}


def test_single_forward_image_rehost_fallback(client, conversation, monkeypatch):
    """收到的图片无 img_url：媒体取回失败时跳过（不中断整单）。"""
    monkeypatch.setattr("backend.api.messages.SEND_ENABLED", True)
    monkeypatch.setattr(send_service.middle_sender, "post_image", lambda **kwargs: {"code": 0})

    from backend.services import media_fetch

    def boom(_msg):
        raise ConnectionError("中间方下载失败")

    monkeypatch.setattr(media_fetch, "fetch_and_cache", boom)
    target = make_target_conv()
    m_img = make_msg(conversation, msg_type=Message.MSG_IMAGE, content="")

    resp = client.post("/api/messages/forward", json=forward_body(conversation, [m_img.id], [target.id], "single"))
    assert resp.get_json()["data"] == {"sent": 0, "failed": 0, "skipped": 1}


def test_single_forward_image_with_url(client, conversation, monkeypatch):
    """payload 带 img_url 的图片：直接按图片类型重发，不走取回。"""
    monkeypatch.setattr("backend.api.messages.SEND_ENABLED", True)
    captured = {}
    monkeypatch.setattr(
        send_service.middle_sender, "post_image",
        lambda **kwargs: captured.update(kwargs) or {"code": 0},
    )
    target = make_target_conv()
    m_img = make_msg(conversation, msg_type=Message.MSG_IMAGE, content="", payload={"img_url": "http://x/a.jpg"})

    resp = client.post("/api/messages/forward", json=forward_body(conversation, [m_img.id], [target.id], "single"))
    assert resp.get_json()["data"] == {"sent": 1, "failed": 0, "skipped": 0}
    assert captured["img_url"] == "http://x/a.jpg"


def test_single_forward_requires_send_enabled(client, conversation, monkeypatch):
    """SEND_ENABLED=false 时逐条转发 403（与发消息同一开关）。"""
    monkeypatch.setattr("backend.api.messages.SEND_ENABLED", False)
    target = make_target_conv()
    m = make_msg(conversation)
    resp = client.post("/api/messages/forward", json=forward_body(conversation, [m.id], [target.id], "single"))
    assert resp.status_code == 403


# ---------- 参数校验与归属 ----------

def test_forward_bad_mode(client, conversation):
    m = make_msg(conversation)
    resp = client.post("/api/messages/forward", json=forward_body(conversation, [m.id], [conversation.id], "batch"))
    assert resp.status_code == 400


def test_forward_target_of_other_device_404(client, conversation):
    """目标会话属于别的设备（dev02）时 404：跨账号不可转发。"""
    other = Conversation(openid="dev02", wxid="wxid_x", chat_type=1, name="别家客户")
    db.session.add(other)
    db.session.commit()
    m = make_msg(conversation)
    resp = client.post("/api/messages/forward", json=forward_body(conversation, [m.id], [other.id], "merge"))
    assert resp.status_code == 404


def test_forward_msg_of_other_conversation_404(client, conversation):
    """msg_ids 里混入别的会话的消息：整单拒绝。"""
    target = make_target_conv()
    foreign = make_msg(target)  # 属于目标会话的消息冒充源消息
    resp = client.post("/api/messages/forward", json=forward_body(conversation, [foreign.id], [target.id], "merge"))
    assert resp.status_code == 404


def test_forward_bad_msg_ids(client, conversation):
    resp = client.post("/api/messages/forward", json=forward_body(conversation, ["abc"], [conversation.id], "merge"))
    assert resp.status_code == 400
