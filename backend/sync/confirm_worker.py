"""发送结果确认：定时轮询中间方 get_post_xxx，把已下发的任务收尾。

每轮：查出"已下发"的任务 → 逐个用 uuid 查结果 → 更新 task 和 message 状态。
查询本身失败不改结果，只累计 retry_count，超过 MAX_RETRY 兜底标失败。
"""
import json

from backend.adapter import sender as middle_sender
from backend.extensions import db
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.models.send_task import SendTask

MAX_RETRY = 10  # 查不到结果的兜底次数，超过按失败处理（联调后可调）
BATCH_LIMIT = 50  # 每轮最多确认的任务数


def confirm_once(app):
    """跑一轮确认。需要 app 上下文（由定时器或测试触发）。"""
    with app.app_context():
        tasks = (
            SendTask.query.filter(
                SendTask.status == SendTask.ST_DISPATCHED,
                SendTask.deleted_at.is_(None),
            )
            .order_by(SendTask.id)
            .limit(BATCH_LIMIT)
            .all()
        )
        for task in tasks:
            _confirm_one(task)
        db.session.commit()


def _confirm_one(task):
    """确认单个任务的结果。

    三态处理：True=成功 / False=失败 / None=结果还没出来（下轮再查）。
    查询要带设备 openid（经 message → conversation 找到会话所属设备）。
    """
    openid = _task_openid(task)
    try:
        body = middle_sender.get_result(task.action, task.uuid, openid=openid or "")
    except Exception:
        task.retry_count += 1
        if task.retry_count >= MAX_RETRY:
            _mark_failed(task)
        return

    verdict = _parse_verdict(body, task.uuid)
    if verdict is None:
        # 结果未生成：不算失败，累计重试，超过兜底次数才标失败
        task.retry_count += 1
        if task.retry_count >= MAX_RETRY:
            _mark_failed(task)
        return
    if verdict:
        task.status = SendTask.ST_SUCCESS
        _mark_message(task, Message.ST_SENT)
        _broadcast(task, Message.ST_SENT)
    else:
        _mark_failed(task)
        _broadcast(task, Message.ST_FAILED)


def _task_openid(task):
    """任务 → 设备 openid：经 message 找 conversation（查不到返回空串）。"""
    if task.message_id is None:
        return ""
    msg = db.session.get(Message, task.message_id)
    if msg is None:
        return ""
    conv = db.session.get(Conversation, msg.conversation_id)
    return (conv.openid or "") if conv else ""


def _broadcast(task, msg_status):
    """状态有变化就推给前端：气泡从"发送中"变成"已发送/失败"。"""
    if task.message_id is None:
        return
    msg = db.session.get(Message, task.message_id)
    if msg is None:
        return
    from backend.ws import hub
    hub.broadcast("send_result", {
        "message_id": msg.id,
        "conversation_id": msg.conversation_id,
        "status": msg_status,
    })


def _mark_failed(task):
    task.status = SendTask.ST_FAILED
    _mark_message(task, Message.ST_FAILED)


def _mark_message(task, status):
    msg = db.session.get(Message, task.message_id)
    if msg is not None:
        msg.status = status


def _parse_verdict(body, want_uuid):
    """按真实返回判定结果（2026-10-29 联调实测结构）。

    查询接口返回：{"code":0, "data":[{"uuid":"...", "processing_result":"{\"ret\":200,...}"}]}
    返回三态：True=设备处理成功 / False=处理失败 / None=还没出结果（data 里没有这条 uuid）。
    """
    if body.get("code") != 0:
        return False
    data = body.get("data") or []
    if isinstance(data, dict):
        data = [data]
    for rec in data:
        if rec.get("uuid") != want_uuid:
            continue
        result = rec.get("processing_result")
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except ValueError:
                return False
        if isinstance(result, dict):
            return result.get("ret") == 200
        return False
    return None
