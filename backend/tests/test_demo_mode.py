"""演示模式测试：未配置中间方地址时，发送闭环应完整走通。"""
from backend.extensions import db

from backend.adapter import client


def test_demo_mode_returns_success(monkeypatch):
    monkeypatch.setattr(client, "DEMO_MODE", True)
    body = client.call("send_api", "post_text_message")
    assert body["code"] == 0


def test_demo_mode_query_carries_data(monkeypatch):
    import json

    monkeypatch.setattr(client, "DEMO_MODE", True)
    body = client.call("send_api", "get_post_text_message", uuid="u-9")
    rec = body["data"][0]
    assert rec["uuid"] == "u-9"
    assert json.loads(rec["processing_result"])["ret"] == 200


def test_demo_send_flow_reaches_sent(app, monkeypatch, conversation):
    """演示模式：发送→确认轮询，气泡从发送中变为已发送。"""
    from backend.models import Message
    from backend.sync import confirm_worker
    from backend.sync import send_service

    monkeypatch.setattr(client, "DEMO_MODE", True)
    msg = send_service.send_message(conversation.id, 1, "demo 演示消息", {})
    assert msg.status == Message.ST_SENDING  # 已入库待确认

    confirm_worker.confirm_once(app)
    db.session.expire_all()  # confirm 在新 app context 的 session 里提交，强制重读
    assert msg.status == Message.ST_SENT  # demo 返回视为成功
