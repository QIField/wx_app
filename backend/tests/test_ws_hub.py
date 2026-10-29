"""WebSocket 广播单测：不真连浏览器，直接验证广播函数被正确调用。"""
from queue import Queue

from backend.extensions import db
from backend.models.message import Message
from backend.models.send_task import SendTask
from backend.sync import confirm_worker, message_sync
from backend.ws import hub

from backend.tests.test_message_sync import make_body, make_item, patch_pull


def test_broadcast_puts_json_into_every_queue():
    """广播：名单里的每条连接都收到同一条 JSON。"""
    q1, q2 = Queue(), Queue()
    hub._connects.extend([q1, q2])
    try:
        hub.broadcast("new_message", {"message_id": 1, "content": "你好"})
    finally:
        hub._connects.clear()

    for q in (q1, q2):
        text = q.get_nowait()
        assert '"event": "new_message"' in text or '"event":"new_message"' in text
        assert "你好" in text


def test_sync_broadcasts_new_message(app, monkeypatch):
    """收消息入库后广播 new_message（commit 之后）。"""
    events = []
    monkeypatch.setattr(hub, "broadcast", lambda e, d: events.append((e, d)))
    patch_pull(monkeypatch, make_body([make_item()]))

    message_sync.sync_once(app)

    assert len(events) == 1
    event, data = events[0]
    assert event == "new_message"
    assert data["content"] == "变速箱修好多钱"
    assert data["conversation_id"] > 0
    assert "create_time" in data


def test_sync_no_broadcast_when_dedup(app, monkeypatch):
    """重复消息不入库也不广播。"""
    events = []
    monkeypatch.setattr(hub, "broadcast", lambda e, d: events.append((e, d)))
    patch_pull(monkeypatch, make_body([make_item()]))
    message_sync.sync_once(app)

    message_sync.sync_once(app)

    assert len(events) == 1  # 只有第一轮推过


def test_confirm_broadcasts_send_result(app, conversation, monkeypatch):
    """发送确认后广播 send_result：成功与失败都推。"""
    events = []
    monkeypatch.setattr(hub, "broadcast", lambda e, d: events.append((e, d)))

    def ok(action, uuid):
        return {"code": 0, "data": [{"uuid": uuid, "processing_result": '{"ret": 200}'}]}

    monkeypatch.setattr(confirm_worker.middle_sender, "get_result", ok)
    msg = Message(conversation_id=conversation.id, msg_type=1, direction=2,
                  content="hi", status=Message.ST_SENDING)
    task = SendTask(uuid="u-ws", action="post_text_message",
                    status=SendTask.ST_DISPATCHED, message_id=None)
    db.session.add_all([msg, task])
    db.session.flush()
    task.message_id = msg.id
    db.session.commit()

    confirm_worker.confirm_once(app)

    assert len(events) == 1
    event, data = events[0]
    assert event == "send_result"
    assert data["message_id"] == msg.id
    assert data["conversation_id"] == conversation.id
    assert data["status"] == Message.ST_SENT
