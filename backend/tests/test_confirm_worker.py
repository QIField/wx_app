"""发送结果确认单测：mock get_result，验证任务收尾。"""
import json

from backend.extensions import db
from backend.models.message import Message
from backend.models.send_task import SendTask
from backend.sync import confirm_worker


def make_task(app, conversation, task_status, msg_status):
    """造一对 task + message，模拟已下发的状态。"""
    msg = Message(
        conversation_id=conversation.id,
        msg_type=Message.MSG_TEXT,
        direction=Message.DIR_OUT,
        content="hi",
        status=msg_status,
    )
    task = SendTask(
        uuid="u-1", action="post_text_message", status=task_status, message_id=None
    )
    db.session.add_all([msg, task])
    db.session.flush()
    task.message_id = msg.id
    db.session.commit()
    return task, msg


def test_confirm_success(app, conversation, monkeypatch):
    """结果成功（processing_result ret=200）：task=成功、message=已发送。"""

    def fake_get_result(action, uuid, openid=""):
        return {
            "code": 0,
            "msg": "success",
            "data": [{"uuid": "u-1", "processing_result": '{"ret": 200, "msg": "操作成功"}'}],
        }

    monkeypatch.setattr(confirm_worker.middle_sender, "get_result", fake_get_result)
    task, msg = make_task(app, conversation, SendTask.ST_DISPATCHED, Message.ST_SENDING)

    confirm_worker.confirm_once(app)

    db.session.expire_all()
    assert task.status == SendTask.ST_SUCCESS
    assert msg.status == Message.ST_SENT


def test_confirm_failed(app, conversation, monkeypatch):
    """结果失败（processing_result ret!=200）：task=失败、message=失败。"""

    def fake_get_result(action, uuid, openid=""):
        return {
            "code": 0,
            "msg": "success",
            "data": [{"uuid": "u-1", "processing_result": '{"ret": 500, "msg": "发送失败"}'}],
        }

    monkeypatch.setattr(confirm_worker.middle_sender, "get_result", fake_get_result)
    task, msg = make_task(app, conversation, SendTask.ST_DISPATCHED, Message.ST_SENDING)

    confirm_worker.confirm_once(app)

    db.session.expire_all()
    assert task.status == SendTask.ST_FAILED
    assert msg.status == Message.ST_FAILED


def test_confirm_backfills_revoke_fields(app, conversation, monkeypatch):
    """实测回填：成功结果 data 里的 newMsgId/msgId（驼峰）回填消息表。

    文字消息 msgId=0 不是真实 id，不回填（2026-10-31 实测）。
    """
    data = {"toWxid": "wxid_customer", "createTime": 1793414601,
            "msgId": 0, "newMsgId": 8170781315632489325, "type": 1}

    def fake_get_result(action, uuid, openid=""):
        return {
            "code": 0,
            "data": [{"uuid": "u-1", "processing_result":
                      json.dumps({"ret": 200, "msg": "操作成功", "data": data}, ensure_ascii=False)}],
        }

    monkeypatch.setattr(confirm_worker.middle_sender, "get_result", fake_get_result)
    task, msg = make_task(app, conversation, SendTask.ST_DISPATCHED, Message.ST_SENDING)

    confirm_worker.confirm_once(app)

    db.session.expire_all()
    assert msg.status == Message.ST_SENT
    assert msg.new_msg_id == "8170781315632489325"
    assert not msg.middle_msg_id  # msgId=0 不回填


def test_confirm_backfills_real_msg_id(app, conversation, monkeypatch):
    """链接/图片等消息 msgId 是真实值，正常回填 middle_msg_id。"""
    data = {"toWxid": "wxid_customer", "createTime": 1793414603,
            "msgId": 824402483, "newMsgId": 7740053374785325585, "type": 5}

    def fake_get_result(action, uuid, openid=""):
        return {
            "code": 0,
            "data": [{"uuid": "u-1", "processing_result":
                      json.dumps({"ret": 200, "msg": "操作成功", "data": data}, ensure_ascii=False)}],
        }

    monkeypatch.setattr(confirm_worker.middle_sender, "get_result", fake_get_result)
    task, msg = make_task(app, conversation, SendTask.ST_DISPATCHED, Message.ST_SENDING)

    confirm_worker.confirm_once(app)

    db.session.expire_all()
    assert msg.middle_msg_id == "824402483"
    assert msg.new_msg_id == "7740053374785325585"


def test_confirm_result_not_ready_keeps_retrying(app, conversation, monkeypatch):
    """结果还没生成（data 里没有这条 uuid）：不算失败，重试+1。"""

    def fake_get_result(action, uuid, openid=""):
        return {"code": 0, "msg": "success", "data": []}

    monkeypatch.setattr(confirm_worker.middle_sender, "get_result", fake_get_result)
    task, msg = make_task(app, conversation, SendTask.ST_DISPATCHED, Message.ST_SENDING)

    confirm_worker.confirm_once(app)

    db.session.expire_all()
    assert task.status == SendTask.ST_DISPATCHED
    assert task.retry_count == 1
    assert msg.status == Message.ST_SENDING


def test_confirm_query_error_keeps_retrying(app, conversation, monkeypatch):
    """查询本身失败：状态不变、重试次数+1，不到兜底次数不标失败。"""

    def boom(action, uuid, openid=""):
        raise ConnectionError("超时")

    monkeypatch.setattr(confirm_worker.middle_sender, "get_result", boom)
    task, msg = make_task(app, conversation, SendTask.ST_DISPATCHED, Message.ST_SENDING)

    confirm_worker.confirm_once(app)

    db.session.expire_all()
    assert task.status == SendTask.ST_DISPATCHED
    assert task.retry_count == 1
    assert msg.status == Message.ST_SENDING


def test_confirm_gives_up_after_max_retry(app, conversation, monkeypatch):
    """重试到兜底次数：按失败收尾。"""

    def boom(action, uuid, openid=""):
        raise ConnectionError("超时")

    monkeypatch.setattr(confirm_worker.middle_sender, "get_result", boom)
    task, msg = make_task(app, conversation, SendTask.ST_DISPATCHED, Message.ST_SENDING)
    task.retry_count = confirm_worker.MAX_RETRY - 1
    db.session.commit()

    confirm_worker.confirm_once(app)

    db.session.expire_all()
    assert task.status == SendTask.ST_FAILED
    assert msg.status == Message.ST_FAILED


def test_confirm_row_before_result_keeps_retrying(app, conversation, monkeypatch):
    """同款竞态（2026-10-31）：记录行先于 processing_result 填充出现。

    旧行为空字符串 json.loads 抛 ValueError 被当成"发送失败"提前定格；
    修正后视为未出结果，保持已下发并重试。
    """

    def fake_get_result(action, uuid, openid=""):
        return {"code": 0, "msg": "success",
                "data": [{"uuid": "u-1", "processing_result": ""}]}

    monkeypatch.setattr(confirm_worker.middle_sender, "get_result", fake_get_result)
    task, msg = make_task(app, conversation, SendTask.ST_DISPATCHED, Message.ST_SENDING)

    confirm_worker.confirm_once(app)

    db.session.expire_all()
    assert task.status == SendTask.ST_DISPATCHED
    assert task.retry_count == 1
    assert msg.status == Message.ST_SENDING


def test_confirm_query_code_error_keeps_retrying(app, conversation, monkeypatch):
    """查询层异常（code != 0）不是发送结果：不算失败，重试+1。"""

    def fake_get_result(action, uuid, openid=""):
        return {"code": 500, "msg": "内部错误", "data": []}

    monkeypatch.setattr(confirm_worker.middle_sender, "get_result", fake_get_result)
    task, msg = make_task(app, conversation, SendTask.ST_DISPATCHED, Message.ST_SENDING)

    confirm_worker.confirm_once(app)

    db.session.expire_all()
    assert task.status == SendTask.ST_DISPATCHED
    assert task.retry_count == 1
    assert msg.status == Message.ST_SENDING


def test_confirm_skips_non_dispatched(app, conversation, monkeypatch):
    """非"已下发"状态的任务不参与确认。"""
    called = []

    def fake_get_result(action, uuid, openid=""):
        called.append(uuid)
        return {"code": 0, "data": {}}

    monkeypatch.setattr(confirm_worker.middle_sender, "get_result", fake_get_result)
    make_task(app, conversation, SendTask.ST_PENDING, Message.ST_SENDING)

    confirm_worker.confirm_once(app)

    assert called == []


def test_confirm_skips_offline_device(app, conversation, monkeypatch):
    """已判定离线设备（online=0）的任务不查询结果：不白烧重试次数，保持已下发。"""
    from backend.models.user_device import UserDevice

    from backend.tests.conftest import make_user

    called = []

    def fake_get_result(action, uuid, openid=""):
        called.append(uuid)
        return {"code": 0, "data": {}}

    monkeypatch.setattr(confirm_worker.middle_sender, "get_result", fake_get_result)
    make_user(open_ids=["dev01"])
    task, _ = make_task(app, conversation, SendTask.ST_DISPATCHED, Message.ST_SENDING)
    UserDevice.query.filter_by(openid="dev01").update({"online": 0})
    db.session.commit()

    confirm_worker.confirm_once(app)

    assert called == []
    db.session.expire_all()
    assert task.status == SendTask.ST_DISPATCHED
    assert task.retry_count == 0
