"""发送结果确认：定时轮询中间方 get_post_xxx，把已下发的任务收尾。

每轮：查出"已下发"的任务 → 逐个用 uuid 查结果 → 更新 task 和 message 状态。
查询本身失败不改结果，只累计 retry_count，超过 MAX_RETRY 兜底标失败。
"""
from backend.adapter import sender as middle_sender
from backend.extensions import db
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
    """确认单个任务的结果。"""
    try:
        body = middle_sender.get_result(task.action, task.uuid)
    except Exception:
        task.retry_count += 1
        if task.retry_count >= MAX_RETRY:
            _mark_failed(task)
        return

    if _parse_success(body):
        task.status = SendTask.ST_SUCCESS
        _mark_message(task, Message.ST_SENT)
        _broadcast(task, Message.ST_SENT)
    else:
        _mark_failed(task)
        _broadcast(task, Message.ST_FAILED)


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


def _parse_success(body):
    """判断发送是否成功。

    中间方约定：code==0 表示请求成功，查询结果在 data 里。
    data.status 的实际取值以中间方返回为准，联调时在这里校准：
    - 有 status 字段：取 0/1 视为成功，其他视为失败
    - 无 status 字段：code==0 即视为成功
    """
    data = body.get("data") or {}
    status = data.get("status")
    if status is None:
        return body.get("code") == 0
    return status in (0, 1, "0", "1")
