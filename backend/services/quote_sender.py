"""自动报价发送（阶段 5）：算价完成的 pending 询价 → 自动发产品图 + 话术 → 置已报价。

发送通道用自家发消息编排（sync/send_service.send_message，operator=None 系统代发）：
- 产品图在前（msg_type=2，payload.img_url=产品图公网 URL，中间方按 URL 拉取），
  话术在后（msg_type=1）——发送决议「分开发、图片在前、只发产品图、默认发」；
- 报价模式 quote_mode（仅 global 行）= auto 才自动发，preview 留给人工（阶段 6 前端预览）；
- 发送前守门：仍 pending + 有产品 + 有话术；SEND_ENABLED=false（只收不发阶段）整体跳过；
- 成功置已报价（sent_at=now）；下发失败转 review（契约 B「发送失败」出口），error 记原因。

下发成功时消息保持「发送中」，由 task_query 轮询确认（与人工发送同一条链路）；
本服务只广播 new_message 让已打开的页面即时上屏（形态对齐 services/forward.py）。
"""
import logging
from datetime import datetime

from backend.api.quote_config import merged_config
from backend.config import SEND_ENABLED
from backend.extensions import db
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.models.quote_inquiry import QuoteInquiry
from backend.sync import send_service
from backend.sync.send_service import SendDispatchError

log = logging.getLogger(__name__)


def auto_send_pending(rows):
    """批量自动发送（算价后调用）：逐条尝试，单条异常不影响其余；返回发出条数。

    SEND_ENABLED 关闭或 quote_mode=preview（人工预览）时整体跳过。
    """
    if not rows or not SEND_ENABLED or merged_config(0)["quote_mode"] != "auto":
        return 0
    sent = 0
    for row in rows:
        try:
            if _send_one(row):
                sent += 1
        except Exception:  # noqa: BLE001 单条异常不拖垮批量
            log.exception("自动报价发送异常 inquiry=%s", row.id)
    db.session.commit()
    return sent


def _send_one(row):
    """单条发送：图前文后。成功置已报价，下发失败转 review。返回是否发出。"""
    r = row.price_json or {}
    product = r.get("product") or {}
    text = ((r.get("pricing") or {}).get("text") or "").strip()
    image = (product.get("image") or "").strip()
    if not product or not text:
        return False  # 无产品/无话术：没有可发内容，保持 pending 等人工

    pushed, conv, failed = [], None, None
    try:
        conv = db.session.get(Conversation, row.conversation_id)
        if image:
            pushed.append(_pushed(
                send_service.send_message(
                    row.conversation_id, Message.MSG_IMAGE, "", {"img_url": image}
                ),
                conv,
            ))
        pushed.append(_pushed(
            send_service.send_message(row.conversation_id, Message.MSG_TEXT, text, {}),
            conv,
        ))
    except SendDispatchError as exc:
        failed = str(exc)

    if failed is not None:
        row.status = QuoteInquiry.ST_REVIEW  # 契约 B：发送失败 → 人工处理
        row.price_json = {**r, "error": f"自动发送失败：{failed}"}
        return False

    row.status = QuoteInquiry.ST_SENT
    row.sent_at = datetime.now()
    _broadcast(pushed, conv)
    log.info("自动报价已发送 inquiry=%s conv=%s 带图=%s", row.id, row.conversation_id, bool(image))
    return True


def _pushed(msg, conv):
    """发送成功的 message → 广播字典（发出消息形态对齐 forward.broadcast_cards）。"""
    return {
        "message_id": msg.id,
        "conversation_id": msg.conversation_id,
        "openid": (conv.openid or "") if conv else "",
        "direction": Message.DIR_OUT,
        "msg_type": msg.msg_type,
        "content": msg.content,
        "payload": msg.payload,
        "summary": msg.content,
        "operator_name": "自动报价",
        "create_time": msg.create_time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def _broadcast(pushed, conv):
    """已打开的页面即时上屏：复用 ws hub，按 message_id 幂等。"""
    if not pushed:
        return
    from backend.ws import hub

    for item in pushed:
        hub.broadcast("new_message", item)
