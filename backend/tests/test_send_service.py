"""发送编排单测：mock 中间方适配器，验证落库与状态机流转。"""
import pytest

from backend.extensions import db
from backend.models.message import Message
from backend.models.send_task import SendTask
from backend.sync import send_service
from backend.sync.send_service import SendDispatchError


def test_send_text_ok(app, conversation, monkeypatch):
    """发文本：参数拼对、uuid 一致、task=已下发、message=发送中。"""
    captured = {}

    def fake_post(to_wxid, content, ats="", uuid=None):
        captured.update(to_wxid=to_wxid, content=content, uuid=uuid)
        return {"code": 0, "msg": "success"}

    monkeypatch.setattr(send_service.middle_sender, "post_text", fake_post)

    msg = send_service.send_message(conversation.id, Message.MSG_TEXT, "好的马上安排", {})

    task = SendTask.query.one()
    assert captured["to_wxid"] == "wxid_customer"
    assert captured["content"] == "好的马上安排"
    assert captured["uuid"] == task.uuid
    assert task.message_id == msg.id
    assert task.status == SendTask.ST_DISPATCHED
    assert task.action == "post_text_message"
    assert task.request_payload["to_wxid"] == "wxid_customer"
    assert msg.status == Message.ST_SENDING
    assert msg.direction == Message.DIR_OUT


def test_send_link_ok(app, conversation, monkeypatch):
    """发链接卡片（报价链接走这里）：payload 字段透传。"""
    captured = {}

    def fake_post(to_wxid, title, desc, link_url, thumb_url="", uuid=None):
        captured.update(title=title, link_url=link_url, uuid=uuid)
        return {"code": 0, "msg": "success"}

    monkeypatch.setattr(send_service.middle_sender, "post_link", fake_post)
    payload = {"title": "宝马320报价", "desc": "今日特价", "link_url": "https://x.y/z"}

    msg = send_service.send_message(conversation.id, Message.MSG_LINK, "", payload)

    assert captured["title"] == "宝马320报价"
    assert captured["link_url"] == "https://x.y/z"
    assert msg.content == "宝马320报价"  # 摘要取 title


def test_send_dispatch_fail_marks_failed(app, conversation, monkeypatch):
    """下发失败：task=失败、message=失败，并抛 SendDispatchError。"""

    def boom(**kwargs):
        raise ConnectionError("网络断了")

    monkeypatch.setattr(send_service.middle_sender, "post_text", boom)

    with pytest.raises(SendDispatchError):
        send_service.send_message(conversation.id, Message.MSG_TEXT, "hi", {})

    task = SendTask.query.one()
    msg = Message.query.one()
    assert task.status == SendTask.ST_FAILED
    assert msg.status == Message.ST_FAILED


def test_send_unknown_type(app, conversation):
    """不支持的 msg_type 抛 400。"""
    from werkzeug.exceptions import BadRequest

    with pytest.raises(BadRequest):
        send_service.send_message(conversation.id, 99, "hi", {})


def test_send_conversation_not_found(app, conversation):
    """会话不存在抛 404；软删除的会话同样当不存在。"""
    from werkzeug.exceptions import NotFound

    with pytest.raises(NotFound):
        send_service.send_message(999, Message.MSG_TEXT, "hi", {})

    conversation.deleted_at = db.func.now()
    db.session.commit()
    with pytest.raises(NotFound):
        send_service.send_message(conversation.id, Message.MSG_TEXT, "hi", {})
