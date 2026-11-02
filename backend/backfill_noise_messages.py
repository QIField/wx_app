"""一次性回填：清理存量系统噪音消息并补拍一拍/群事件灰条文案。

背景：2026-11-02 前收消息不识别系统类 XML，微信不渲染的协议事件
（raw_type=51 StatusNotify 已读指针、gamecenter、secmsg 等）按文本入库，
前端显示成 [系统消息]/XML 乱码；拍一拍与群事件（新人进群/转让群主等）
也未转成微信同款灰条。新消息已在 message_sync 入库前处理，本脚本把
存量数据一次性修正（幂等，可重复执行）：
- 拍一拍 / sysmsgtemplate / 自带文案的系统 XML → content 改写为可读灰条，
  打 system 标，方向置出方向并回退已计的未读；
- 其余解析不出的系统 XML → 软删（payload.noise=True），留底不展示；
- 受影响会话按最新可见消息重算 last_msg；清理后无任何可见消息的会话
  打印为候选清单（多为同步噪音造出的"自己跟自己"垃圾会话），由人工
  决定是否删除，本脚本不自动删。

用法：python -m backend.backfill_noise_messages
"""
from datetime import datetime

from backend.app import create_app
from backend.extensions import db
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.services import conversations as conversation_service
from backend.sync import sysmsg

STAT_KEYS = ("gray", "noise", "skip")


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
        conv_ids = set()
        for msg in rows:
            kind = msg_xml.classify(msg.content)
            if kind is not None:
                stats["skip"] += 1  # 撤回/媒体卡片归 backfill_message_types 管
                continue
            conv = db.session.get(Conversation, msg.conversation_id)
            gray = _gray_text(msg.content, (conv.openid if conv else "") or "")
            payload = dict(msg.payload or {})
            if gray is not None:
                _turn_into_graybar(msg, conv, gray)
                payload["system"] = True
                stats["gray"] += 1
            else:
                # 解析不出的协议噪音（51状态同步/gamecenter/secmsg等）：软删留底
                payload["noise"] = True
                msg.deleted_at = datetime.now()
                stats["noise"] += 1
            msg.payload = payload
            conv_ids.add(msg.conversation_id)

        _refresh_convs(conv_ids)
        db.session.commit()
        print("回填完成：", stats)
        _print_empty_conv_candidates()


def _gray_text(content, openid):
    """系统 XML → 可读灰条文案；解析不出返回 None（转噪音软删）。

    库里没存 raw_type，传 0：51 噪音的 content 是 <msg><op> XML，
    resolve 按解析失败同样落到噪音分支，判定一致。
    """
    gray, _noise = sysmsg.resolve(content, openid=openid)
    return gray


def _turn_into_graybar(msg, conv, gray):
    """改写为微信同款灰条：不占未读（原收方向已计的未读回退 1）。"""
    if (
        msg.direction == Message.DIR_IN
        and conv is not None
        and (conv.unread_count or 0) > 0
    ):
        conv.unread_count = conv.unread_count - 1
    msg.direction = Message.DIR_OUT
    msg.sender_name = "系统"
    msg.content = gray


def _refresh_convs(conv_ids):
    """受影响会话按最新可见消息重算 last_msg/last_msg_at。"""
    for conv in Conversation.query.filter(Conversation.id.in_(conv_ids)).all():
        last = (
            Message.query.filter_by(conversation_id=conv.id)
            .filter(Message.deleted_at.is_(None))
            .order_by(Message.id.desc())
            .first()
        )
        if last is not None:
            conv.last_msg = conversation_service.short_summary(
                last.msg_type, last.content
            )
            conv.last_msg_at = last.create_time
        else:
            conv.last_msg = ""  # 清理后已无可见消息：垃圾会话候选，见下


def _print_empty_conv_candidates():
    """打印已无任何可见消息的会话（垃圾会话候选，人工决定是否删除）。"""
    from sqlalchemy import or_

    convs = (
        Conversation.query.filter(
            Conversation.deleted_at.is_(None),
            or_(Conversation.last_msg == "", Conversation.last_msg.is_(None)),
        )
        .order_by(Conversation.id)
        .all()
    )
    candidates = []
    for conv in convs:
        visible = (
            Message.query.filter_by(conversation_id=conv.id)
            .filter(Message.deleted_at.is_(None))
            .first()
        )
        if visible is None:
            candidates.append(conv)
    if candidates:
        print(f"无可见消息的垃圾会话候选（{len(candidates)} 个，未自动删除）：")
        for conv in candidates:
            print(f"  conv={conv.id} openid={conv.openid} wxid={conv.wxid}")
    else:
        print("无垃圾会话候选。")


if __name__ == "__main__":
    main()
