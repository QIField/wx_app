"""撤回通知落库处理：定位原消息打 revoked 标记，或落系统灰条兜底。

中间方推来的 <sysmsg type="revokemsg"> 通知本身不入库（会显示成 XML 乱码）：
按 newmsgid/msgid 找到同会话的原消息，把 payload.revoked 置真并广播
message_revoked，前端把气泡换成微信样式灰条"你撤回了一条消息 重新编辑"。
原消息不在库里（如手机上发的历史）时，存一条系统灰条让撤回可见。
"""
from backend.extensions import db
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.services import anonymize, conversations as conversation_service


def _revoke_text(fields):
    """撤回灰条文案。

    中间方的 replacemsg 按微信设备主人视角生成（实测 2026-10-31：客户撤回
    也写"你撤回了"），单聊不能照抄，按方向重新生成；群聊通知自带发言人
    昵称（"xxx 撤回了一条消息"），直接引用，缺失时用匿名编码兜底（脱敏契约，
    不把 wxid 原文写进展示文案）。
    """
    if fields["direction"] == Message.DIR_OUT:
        return "你撤回了一条消息"
    if fields["chat_type"] == Conversation.CHAT_GROUP:
        repl = (fields["revoke"].get("replacemsg") or "").strip()
        if repl and not repl.startswith("你"):
            return repl
        who = anonymize.resolved_name(fields.get("sender_name"), fields.get("sender_wxid"))
        who = who or anonymize.anon_label(fields.get("sender_wxid"))
        return f"「{who}」撤回了一条消息"
    return "对方撤回了一条消息"


def apply_revoke(openid, fields, revokes):
    """处理一条撤回通知（fields 来自 message_sync._normalize）。

    命中原消息：打标记、挂撤回事件，返回 None；
    未命中：存一条 payload.system 灰条消息，返回其 new_message 推送字典。
    """
    info = fields["revoke"]
    conv = conversation_service.get_or_create(openid, fields["peer_wxid"], fields["chat_type"])

    original = _find_original(conv.id, info)

    if original is not None:
        payload = dict(original.payload or {})
        payload["revoked"] = True
        original.payload = payload
        conv.last_msg = _revoke_text(fields)
        conv.last_msg_at = fields["create_time"]
        if revokes is not None:
            revokes.append({
                "message_id": original.id,
                "conversation_id": conv.id,
            })
        return None

    # 兜底灰条按通知的 msg_id 去重（通知重推时不重复落行）
    if fields["middle_msg_id"]:
        exists = (
            Message.query.filter_by(
                conversation_id=conv.id, middle_msg_id=fields["middle_msg_id"])
            .filter(Message.deleted_at.is_(None))
            .first()
        )
        if exists is not None:
            return None

    notice = Message(
        conversation_id=conv.id,
        msg_type=Message.MSG_TEXT,
        direction=Message.DIR_IN,
        sender_name="系统",
        content=_revoke_text(fields),
        payload={"system": True},
        middle_msg_id=fields["middle_msg_id"],
        new_msg_id=fields["new_msg_id"],
        create_time=fields["create_time"],
    )
    db.session.add(notice)
    conv.last_msg = notice.content
    conv.last_msg_at = fields["create_time"]
    return {
        "message_id": notice.id,
        "conversation_id": conv.id,
        "direction": Message.DIR_IN,
        "msg_type": Message.MSG_TEXT,
        "content": notice.content,
        "payload": {"system": True},  # 广播给前端：按微信样式灰条渲染
        "summary": notice.content,  # 会话摘要同步带上（与 message_sync 推送契约一致）
        "sender_wxid": "",
        "sender_name": "系统",
        "create_time": fields["create_time"],
    }


def _find_original(conversation_id, info):
    """按 newmsgid → msgid 顺序定位被撤回的原消息（同会话内）。"""
    for key, column in (("newmsgid", Message.new_msg_id), ("msgid", Message.middle_msg_id)):
        value = (info.get(key) or "").strip()
        if not value or value == "0":  # 文字消息 msg_id 恒为 0，不能当定位键
            continue
        found = (
            Message.query.filter_by(conversation_id=conversation_id)
            .filter(column == value, Message.deleted_at.is_(None))
            .first()
        )
        if found is not None:
            return found
    return None
