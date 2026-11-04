"""多账号绑定核心单测：设备卡片、openid 越权拦截、操作人快照、在线解析。

client 夹具登录的是 cs01（绑定 dev01）；需要第二台设备时用 bind_device 追加。
"""
from backend.extensions import db
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.services.devices import check_device_online
from backend.tests.conftest import bind_device, login_headers, make_user


def _bind_second():
    """给 client 夹具的 cs01 追加第二台绑定设备，返回该用户。"""
    from backend.models.user import User

    me = User.query.filter_by(username="cs01").one()
    bind_device(me, "dev02")
    return me


def test_devices_cards_with_unread(app, client):
    """设备卡片：绑定顺序返回，未读数按设备聚合。"""
    me = _bind_second()
    db.session.add_all([
        Conversation(openid="dev01", wxid="w1", chat_type=1, name="甲", unread_count=2),
        Conversation(openid="dev01", wxid="w2", chat_type=1, name="乙", unread_count=3),
        Conversation(openid="dev02", wxid="w3", chat_type=1, name="丙", unread_count=7),
        Conversation(openid="dev03", wxid="w4", chat_type=1, name="别人的"),  # 非绑定设备不计
    ])
    db.session.commit()

    resp = client.get("/api/devices", headers=login_headers(me))

    data = resp.get_json()["data"]
    assert [d["openid"] for d in data] == ["dev01", "dev02"]  # 绑定顺序
    assert data[0]["unread"] == 5
    assert data[1]["unread"] == 7
    assert set(data[0]) >= {"openid", "remark", "display_name", "online", "unread"}


def test_devices_display_name_fallback(app, client):
    """脱敏契约：无备注的设备按绑定顺序回退「设备N」，不回退 openid。"""
    from backend.models.user import User

    me = User.query.filter_by(username="cs01").one()
    bind_device(me, "dev02", remark="售前小号")  # dev01 无备注、dev02 有备注

    data = client.get("/api/devices", headers=login_headers(me)).get_json()["data"]

    assert data[0]["display_name"] == "设备1"
    assert data[1]["display_name"] == "售前小号"


def test_devices_requires_login(app):
    """未登录拿设备卡片：401。"""
    assert app.test_client().get("/api/devices").status_code == 401


def test_conversations_default_first_device(app, client):
    """不带 ?openid=：会话列表默认返回第一个绑定设备的。"""
    _bind_second()
    db.session.add_all([
        Conversation(openid="dev01", wxid="w1", chat_type=1, name="一号机会话"),
        Conversation(openid="dev02", wxid="w2", chat_type=1, name="二号机会话"),
    ])
    db.session.commit()

    resp = client.get("/api/conversations")
    names = [c["name"] for c in resp.get_json()["data"]]

    assert names == ["一号机会话"]


def test_conversations_pick_device_by_param(app, client):
    """?openid=dev02：看第二个绑定设备的会话；越权 openid 被拒。"""
    _bind_second()
    other = make_user(username="cs02", name="客服02", open_ids=["dev03"])
    db.session.add_all([
        Conversation(openid="dev02", wxid="w2", chat_type=1, name="二号机会话"),
        Conversation(openid="dev03", wxid="w3", chat_type=1, name="别人账号的会话"),
    ])
    db.session.commit()

    resp = client.get("/api/conversations?openid=dev02")
    assert [c["name"] for c in resp.get_json()["data"]] == ["二号机会话"]

    # 不是我的绑定设备：403；该设备所属账号自己看则正常
    assert client.get("/api/conversations?openid=dev03").status_code == 403
    assert client.get("/api/conversations?openid=dev03",
                      headers=login_headers(other)).status_code == 200


def test_messages_scoped_to_my_devices(app, client):
    """归属校验按全部绑定设备：第二个设备的会话也能读；别人的不能。"""
    _bind_second()
    conv1 = Conversation(openid="dev01", wxid="w1", chat_type=1, name="甲")
    conv2 = Conversation(openid="dev02", wxid="w2", chat_type=1, name="乙")
    conv_other = Conversation(openid="dev09", wxid="w9", chat_type=1, name="别人的")
    db.session.add_all([conv1, conv2, conv_other])
    db.session.commit()

    assert client.get(f"/api/conversations/{conv1.id}/messages").status_code == 200
    assert client.get(f"/api/conversations/{conv2.id}/messages").status_code == 200
    assert client.get(f"/api/conversations/{conv_other.id}/messages").status_code == 404


def test_send_message_records_operator_snapshot(app, client, monkeypatch):
    """操作人快照：发出的消息落 operator_id/operator_name，可溯源。"""
    from backend.adapter import sender as middle_sender

    monkeypatch.setattr("backend.api.messages.SEND_ENABLED", True)
    me = _bind_second()
    conv = Conversation(openid="dev01", wxid="w1", chat_type=1, name="甲")
    db.session.add(conv)
    db.session.commit()

    captured = {}
    monkeypatch.setattr(middle_sender, "post_text",
                        lambda **kw: captured.update(kw))

    resp = client.post(f"/api/conversations/{conv.id}/messages",
                       json={"msg_type": 1, "content": "在吗"})
    assert resp.status_code == 200

    msg = Message.query.one()
    assert msg.direction == Message.DIR_OUT
    assert msg.operator_id == me.id
    assert msg.operator_name == me.name

    # 聊天记录接口带出操作人
    data = client.get(f"/api/conversations/{conv.id}/messages").get_json()["data"]
    assert data["messages"][0]["operator_name"] == me.name


def test_send_message_requires_bound_device(app, monkeypatch):
    """未绑定设备的账号不能发消息（会话当不存在）。"""
    from backend.adapter import sender as middle_sender

    monkeypatch.setattr("backend.api.messages.SEND_ENABLED", True)
    nobody = make_user(username="cs09", name="无设备")  # 不绑设备
    conv = Conversation(openid="dev01", wxid="w1", chat_type=1, name="甲")
    db.session.add(conv)
    db.session.commit()
    monkeypatch.setattr(middle_sender, "post_text", lambda **kw: None)

    resp = app.test_client().post(
        f"/api/conversations/{conv.id}/messages",
        headers=login_headers(nobody), json={"msg_type": 1, "content": "hi"})
    assert resp.status_code == 404


def test_check_device_online_parses_result(app, monkeypatch):
    """在线解析：两步式（先 check_online 下发，同 uuid 查结果）。
    processing_result.data true→1 / false→0；下发或查询异常→离线。
    """
    from backend.adapter import client as middle

    calls = []

    def fake_call(module, action, params=None, uuid=None, openid=""):
        calls.append((openid, action, uuid))
        if openid == "err":
            raise RuntimeError("boom")
        if action == "check_online":  # 下发：只回 code/msg
            return {"code": 0, "msg": "success"}
        payload = "true" if openid == "ok" else "false"
        return {"code": 0, "data": [
            {"uuid": uuid, "processing_result": f'{{"ret":200,"data":{payload}}}'}]}

    monkeypatch.setattr(middle, "call", fake_call)
    monkeypatch.setattr("backend.services.devices.time.sleep", lambda s: None)

    assert check_device_online("ok") == 1
    assert check_device_online("off") == 0
    assert check_device_online("err") == 0
    # 同一次检测内下发和查询用同一 uuid；查询先于下发后发生
    ok_calls = [(a, u) for o, a, u in calls if o == "ok"]
    assert ok_calls[0][0] == "check_online" and ok_calls[1][0] == "get_check_online"
    assert ok_calls[0][1] == ok_calls[1][1]


def test_online_check_endpoint(app, client, monkeypatch):
    """点击卡片即时检测：调 check_online 回写库并返回最新状态。"""
    from backend.models.user_device import UserDevice

    monkeypatch.setattr(
        "backend.api.devices.check_device_online", lambda openid: 1)

    resp = client.post("/api/devices/dev01/online-check")
    assert resp.status_code == 200
    assert resp.get_json()["data"] == {"openid": "dev01", "online": 1}
    assert UserDevice.query.filter_by(openid="dev01").one().online == 1


def test_online_check_rejects_foreign_device(app, client, monkeypatch):
    """别人的绑定设备不能借自己的登录态检测：403，且不写库。"""
    from backend.models.user import User
    from backend.models.user_device import UserDevice
    from backend.tests.conftest import make_user

    monkeypatch.setattr(
        "backend.api.devices.check_device_online", lambda openid: 1)
    make_user(username="cs08", name="别家客服", open_ids=["dev_other"])

    assert client.post("/api/devices/dev_other/online-check").status_code == 403
    assert UserDevice.query.filter_by(openid="dev_other").one().online == -1


def test_unbound_account_sees_empty_lists(app):
    """未绑定设备：会话/通讯录/设备卡片都返回空，不报错。"""
    nobody = make_user(username="cs10", name="无设备")
    c = app.test_client()
    headers = login_headers(nobody)

    assert c.get("/api/conversations", headers=headers).get_json()["data"] == []
    assert c.get("/api/devices", headers=headers).get_json()["data"] == []
    assert c.get("/api/contacts?type=friends",
                 headers=headers).get_json()["data"]["list"] == []


def test_bind_second_device_extends_order(app, client):
    """运行中追加绑定：新设备排到最后，原设备会话不受影响。"""
    db.session.add(Conversation(openid="dev01", wxid="w1", chat_type=1, name="旧会话"))
    db.session.commit()
    _bind_second()

    assert [d["openid"] for d in client.get("/api/devices").get_json()["data"]] == [
        "dev01", "dev02"]
    assert client.get("/api/conversations?openid=dev02").get_json()["data"] == []
    assert client.get("/api/conversations").get_json()["data"][0]["name"] == "旧会话"
