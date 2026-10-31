"""一次性回填：把存量 msg_type=1 但 content 实为微信 XML 的消息重分类。

背景：2026-10-31 前收消息不解析 XML，图片/链接卡片/撤回通知都按文本入库，
前端显示成 XML 乱码。新消息已在 message_sync 入库前还原真实类型，
本脚本把存量数据一次性修正（幂等，可重复执行）。

用法：python -m backend.backfill_message_types
"""
from datetime import datetime

from backend.app import create_app
from backend.extensions import db
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.sync import msg_xml, revoke
from backend.sync.message_sync import _short_summary

_KIND = {
    msg_xml.IMAGE: Message.MSG_IMAGE,
    msg_xml.VIDEO: Message.MSG_VIDEO,
    msg_xml.VOICE: Message.MSG_VOICE,
    msg_xml.EMOJI: Message.MSG_EMOJI,
    msg_xml.FILE: Message.MSG_FILE,
    msg_xml.LINK: Message.MSG_LINK,
}

STAT_KEYS = ("image", "video", "voice", "emoji", "link", "file",
             "revoke", "skip")


def main():
    app = create_app()
    with app.app_context():
        rows = (
            Message.query.filter(
                Message.msg_type == Message.MSG_TEXT,
                Message.deleted_at.is_(None),
                Message.content.like("<%"),
            )
            .order_by(Message.id)
            .all()
        )
        stats = dict.fromkeys(STAT_KEYS, 0)
        for msg in rows:
            kind = msg_xml.classify(msg.content)
            if kind is None:
                stats["skip"] += 1  # 拍一拍/游戏中心等系统通知，前端按灰条兜底
                continue
            if kind == msg_xml.REVOKE:
                # 撤回通知行本身总是隐藏：命中由 apply_revoke 打标，未命中由它落兜底灰条
                revoke.apply_revoke(_openid_of(msg), _revoke_fields(msg), None)
                msg.deleted_at = datetime.now()
                stats["revoke"] += 1
                continue

            msg.msg_type = _KIND[kind]
            if kind in (msg_xml.LINK, msg_xml.FILE):
                payload = dict(msg.payload or {})
                payload["app"] = msg_xml.app_info(msg.content)
                msg.payload = payload
            stats[kind] += 1

        _refresh_xml_summaries()
        db.session.commit()
        print("回填完成：", stats)


def _revoke_fields(msg):
    """撤回通知行 → apply_revoke 需要的字段。"""
    conv = db.session.get(Conversation, msg.conversation_id)
    return {
        "revoke": msg_xml.revoke_info(msg.content),
        "peer_wxid": conv.wxid if conv else "",
        "chat_type": conv.chat_type if conv else 1,
        "middle_msg_id": msg.middle_msg_id,
        "new_msg_id": msg.new_msg_id,
        "create_time": msg.create_time,
    }


def _refresh_xml_summaries():
    """会话摘要残留 XML 的（撤回通知/表情等旧摘要），按最新可见消息重算。"""
    convs = Conversation.query.filter(
        Conversation.deleted_at.is_(None),
        Conversation.last_msg.like("<%"),
    ).all()
    for conv in convs:
        last = (
            Message.query.filter_by(conversation_id=conv.id)
            .filter(Message.deleted_at.is_(None))
            .order_by(Message.id.desc())
            .first()
        )
        if last is not None:
            conv.last_msg = _short_summary(last.msg_type, last.content)


def _openid_of(msg):
    conv = db.session.get(Conversation, msg.conversation_id)
    return (conv.openid if conv else "") or ""


if __name__ == "__main__":
    main()
