"""发送 API 单测：参数校验 + 端到端走通闭环。"""
from backend.models.message import Message
from backend.models.send_task import SendTask
from backend.sync import send_service


def test_send_api_ok(client, conversation, monkeypatch):
    """正常发送：返回 message_id + 发送中状态。"""
    monkeypatch.setattr(
        send_service.middle_sender,
        "post_text",
        lambda **kwargs: {"code": 0, "msg": "success"},
    )

    resp = client.post(
        f"/api/conversations/{conversation.id}/messages",
        json={"msg_type": 1, "content": "好的马上安排"},
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["code"] == 0
    assert data["data"]["status"] == Message.ST_SENDING
    assert SendTask.query.one().status == SendTask.ST_DISPATCHED


def test_send_api_bad_type(client, conversation):
    """msg_type 不合法返回 400。"""
    resp = client.post(
        f"/api/conversations/{conversation.id}/messages",
        json={"msg_type": 9, "content": "hi"},
    )
    assert resp.status_code == 400
    assert resp.get_json()["code"] == 400


def test_send_api_bad_payload(client, conversation):
    """payload 不是对象返回 400。"""
    resp = client.post(
        f"/api/conversations/{conversation.id}/messages",
        json={"msg_type": 2, "payload": "not-a-dict"},
    )
    assert resp.status_code == 400


def test_send_api_conversation_not_found(client):
    """会话不存在返回 404，格式统一为 JSON。"""
    resp = client.post(
        "/api/conversations/999/messages",
        json={"msg_type": 1, "content": "hi"},
    )
    assert resp.status_code == 404
    assert resp.get_json()["code"] == 404


def test_send_api_dispatch_error(client, conversation, monkeypatch):
    """下发失败返回 502。"""

    def boom(**kwargs):
        raise ConnectionError("网络断了")

    monkeypatch.setattr(send_service.middle_sender, "post_text", boom)

    resp = client.post(
        f"/api/conversations/{conversation.id}/messages",
        json={"msg_type": 1, "content": "hi"},
    )
    assert resp.status_code == 502
    assert resp.get_json()["code"] == 502
