"""报价发送编排（阶段 5 自动 / 阶段 6 人工）：图前文后发出 → 置已报价。

发送通道用自家发消息编排（sync/send_service.send_message，自动=operator None 系统代发，
人工=登录人快照）：
- 产品图在前（msg_type=2，payload.img_url=产品图公网 URL，中间方按 URL 拉取），
  话术在后（msg_type=1）——发送决议「分开发、图片在前、只发产品图、默认发」；
- 自动：quote_mode（仅 global 行）= auto 才发，preview 留给人工（阶段 6 前端预览）；
  发送前守门：仍 pending + 有产品 + 有话术；SEND_ENABLED=false（只收不发阶段）整体跳过；
- 人工（send_manual，阶段 6 预览流动作）：话术可经改价重建（quote_pricing.rebuild_quote_text），
  产品图仍带上；
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
    _notify_status(rows)
    return sent


def _notify_status(rows):
    """批量发送后的询价状态广播（sent/review 变更 → 拓展栏 feed 静默刷新）。"""
    from backend.services.quote_dispatch import notify_inquiry

    notify_inquiry([r for r in rows if r.status != QuoteInquiry.ST_PENDING])


def _send_one(row):
    """单条自动发送：守门（有产品+有话术）后走统一下发。返回是否发出。"""
    r = row.price_json or {}
    product = r.get("product") or {}
    text = ((r.get("pricing") or {}).get("text") or "").strip()
    image = (product.get("image") or "").strip()
    if not product or not text:
        return False  # 无产品/无话术：没有可发内容，保持 pending 等人工
    return _dispatch_and_mark(row, text, image)


def send_manual(row, text, operator):
    """人工发送（阶段 6 预览流动作）：话术可经改价重建，产品图仍带上（图前文后）。

    成功置已报价；下发失败转 review（与自动发送同一出口）。返回是否发出。
    """
    image = (((row.price_json or {}).get("product") or {}).get("image") or "").strip()
    ok = _dispatch_and_mark(row, (text or "").strip(), image,
                            operator=operator, fail_label="发送失败")
    if ok:
        log.info("人工报价已发送 inquiry=%s conv=%s operator=%s",
                 row.id, row.conversation_id, operator.name)
    return ok


def _dispatch_and_mark(row, text, image, operator=None, fail_label="自动发送失败"):
    """图前文后下发并按结果置状态：成功置已报价+广播；话术下发失败转 review 记原因。

    operator=None 系统代发（自动报价）；人工传登录人（消息快照记操作人）。

    产品图为可选项：开思 CDN 偶发下载超时时静默跳过继续发话术——报价话术才是
    核心交付物，图片失败不应让整单进人工。
    """
    r = row.price_json or {}
    pushed, conv, failed = [], None, None
    conv = db.session.get(Conversation, row.conversation_id)

    # 图片可选：失败仅记 warning，不阻塞话术
    if image:
        img_msg = _dispatch_image(row.conversation_id, image, operator)
        if img_msg is not None:
            pushed.append(_pushed(img_msg, conv))

    # 话术必须：失败进 review
    try:
        pushed.append(_pushed(
            send_service.send_message(
                row.conversation_id, Message.MSG_TEXT, text, {}, operator=operator,
            ),
            conv,
        ))
    except SendDispatchError as exc:
        failed = str(exc)

    if failed is not None:
        row.status = QuoteInquiry.ST_REVIEW
        row.price_json = {**r, "error": f"{fail_label}：{failed}"}
        return False

    row.status = QuoteInquiry.ST_SENT
    row.sent_at = datetime.now()
    _broadcast(pushed, conv)
    log.info("报价已发送 inquiry=%s conv=%s 带图=%s 系统代发=%s",
             row.id, row.conversation_id, bool(image), operator is None)
    return True


def _dispatch_image(conv_id, image_url, operator):
    """尝试发报价产品图。成功返回 Message，失败返回 None 并记 warning。

    产品图为开思 CDN URL，中间方需下载后转发——偶发 30-50s 超时是预期内风险，
    调用方不应因图片失败而阻塞话术下发。
    """
    try:
        return send_service.send_message(
            conv_id, Message.MSG_IMAGE, "",
            {"img_url": image_url}, operator=operator,
        )
    except SendDispatchError as exc:
        log.warning("报价产品图下发失败，降级继续发话术 conv=%s err=%s",
                    conv_id, str(exc))
        return None


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
        "operator_name": msg.operator_name or "自动报价",
        "create_time": msg.create_time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def _broadcast(pushed, conv):
    """已打开的页面即时上屏：复用 ws hub，按 message_id 幂等。"""
    if not pushed:
        return
    from backend.ws import hub

    for item in pushed:
        hub.broadcast("new_message", item)
