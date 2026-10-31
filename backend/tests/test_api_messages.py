"""发送 API 单测：参数校验 + 端到端走通闭环 + 撤回。"""
from datetime import datetime, timedelta

from backend.extensions import db
from backend.models.message import Message
from backend.models.send_task import SendTask
from backend.sync import send_service


def test_send_api_ok(client, conversation, monkeypatch):
    """正常发送：返回 message_id + 发送中状态。"""
    monkeypatch.setattr("backend.api.messages.SEND_ENABLED", True)
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


def test_send_disabled_by_default(client, conversation, monkeypatch):
    """SEND_ENABLED=false 时发送接口直接 403，不落库不建任务（显式关开关，不依赖本地 .env）。"""
    monkeypatch.setattr("backend.api.messages.SEND_ENABLED", False)
    resp = client.post(
        f"/api/conversations/{conversation.id}/messages",
        json={"msg_type": 1, "content": "不该发出去"},
    )

    assert resp.status_code == 403
    assert resp.get_json()["code"] == 403
    assert SendTask.query.count() == 0


def test_send_api_bad_type(client, conversation, monkeypatch):
    """msg_type 不合法返回 400。"""
    monkeypatch.setattr("backend.api.messages.SEND_ENABLED", True)
    resp = client.post(
        f"/api/conversations/{conversation.id}/messages",
        json={"msg_type": 9, "content": "hi"},
    )
    assert resp.status_code == 400
    assert resp.get_json()["code"] == 400


def test_send_api_bad_payload(client, conversation, monkeypatch):
    """payload 不是对象返回 400。"""
    monkeypatch.setattr("backend.api.messages.SEND_ENABLED", True)
    resp = client.post(
        f"/api/conversations/{conversation.id}/messages",
        json={"msg_type": 2, "payload": "not-a-dict"},
    )
    assert resp.status_code == 400


def test_send_api_conversation_not_found(client, monkeypatch):
    """会话不存在返回 404，格式统一为 JSON。"""
    monkeypatch.setattr("backend.api.messages.SEND_ENABLED", True)
    resp = client.post(
        "/api/conversations/999/messages",
        json={"msg_type": 1, "content": "hi"},
    )
    assert resp.status_code == 404
    assert resp.get_json()["code"] == 404


def test_send_api_dispatch_error(client, conversation, monkeypatch):
    """下发失败返回 502。"""
    monkeypatch.setattr("backend.api.messages.SEND_ENABLED", True)

    def boom(**kwargs):
        raise ConnectionError("网络断了")

    monkeypatch.setattr(send_service.middle_sender, "post_text", boom)

    resp = client.post(
        f"/api/conversations/{conversation.id}/messages",
        json={"msg_type": 1, "content": "hi"},
    )
    assert resp.status_code == 502
    assert resp.get_json()["code"] == 502


# ---------- 撤回 ----------

def make_out_message(conv, **over):
    """造一条自己发的、已回填撤回要素的消息。"""
    fields = dict(
        conversation_id=conv.id,
        msg_type=Message.MSG_TEXT,
        direction=Message.DIR_OUT,
        content="撤回我",
        status=Message.ST_SENT,
        new_msg_id="8170781315632489325",
    )
    fields.update(over)
    msg = Message(**fields)
    db.session.add(msg)
    db.session.commit()
    return msg


def mock_revoke_ok(monkeypatch):
    """撤回下发+查询都成功（query_record 不真等重试）。"""
    from backend.api import messages as messages_api

    captured = {}
    monkeypatch.setattr(
        messages_api.middle_sender, "revoke",
        lambda **kwargs: captured.update(kwargs) or {"code": 0},
    )
    monkeypatch.setattr(
        messages_api.task_query, "query_record",
        lambda *a, **k: {"uuid": k.get("task_uuid"), "processing_result": '{"ret": 200, "msg": "操作成功"}'},
    )
    return captured


def test_revoke_ok(client, conversation, monkeypatch):
    """撤回成功：参数用回填的 new_msg_id、msg_id 兜底 "0"，消息打 revoked 标记。"""
    msg = make_out_message(conversation)
    captured = mock_revoke_ok(monkeypatch)

    resp = client.post(f"/api/messages/{msg.id}/revoke")

    assert resp.status_code == 200
    assert resp.get_json()["code"] == 0
    assert captured["to_wxid"] == "wxid_customer"
    assert captured["new_msg_id"] == "8170781315632489325"
    assert captured["msg_id"] == "0"  # 文字消息 msgId=0，兜底 "0"（实测）
    assert captured["create_time"].isdigit()
    db.session.expire_all()
    assert msg.payload["revoked"] is True


def test_revoke_incoming_rejected(client, conversation, monkeypatch):
    """只能撤回自己发的消息。"""
    msg = make_out_message(conversation, direction=Message.DIR_IN)
    resp = client.post(f"/api/messages/{msg.id}/revoke")
    assert resp.status_code == 400
    assert resp.get_json()["code"] == 400


def test_revoke_missing_new_msg_id(client, conversation, monkeypatch):
    """发送结果还没回填（无 new_msg_id）：400。"""
    msg = make_out_message(conversation, new_msg_id="")
    resp = client.post(f"/api/messages/{msg.id}/revoke")
    assert resp.status_code == 400


def test_revoke_over_two_minutes(client, conversation, monkeypatch):
    """超过 2 分钟：400。"""
    msg = make_out_message(conversation, create_time=datetime.now() - timedelta(minutes=3))
    resp = client.post(f"/api/messages/{msg.id}/revoke")
    assert resp.status_code == 400


def test_revoke_middle_fail(client, conversation, monkeypatch):
    """中间方 ret!=200：502 带原因。"""
    from backend.api import messages as messages_api

    msg = make_out_message(conversation)
    monkeypatch.setattr(messages_api.middle_sender, "revoke", lambda **k: {"code": 0})
    monkeypatch.setattr(
        messages_api.task_query, "query_record",
        lambda *a, **k: {"uuid": "u", "processing_result": '{"ret": -1, "msg": "请求超时"}'},
    )

    resp = client.post(f"/api/messages/{msg.id}/revoke")

    assert resp.status_code == 502
    assert "请求超时" in resp.get_json()["msg"]
