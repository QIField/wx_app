"""收消息轮询：定时向中间方增量拉新消息并入库。

流程（已确认的《收消息轮询》流程图）：
读游标 → 调 get_message 拉增量 → 去重 → 入库 + 更新会话 → 推游标。

联调校准点（代码里已标 TODO）：
- get_message 返回的消息字段名（_normalize）
- 消息类型编码映射（_TYPE_MAP）
- start_create_time 的时间格式
"""
from datetime import datetime, timedelta

from backend.adapter import client as middle_client
from backend.config import MIDDLE_OPENID
from backend.extensions import db
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.models.sync_cursor import SyncCursor

PAGE_SIZE = 100        # 每轮拉一页；单轮增量超一页的情况极少，靠下一轮补
FIRST_HOURS = 1        # 首次运行没有游标时，从最近 1 小时开始拉

# 中间方消息类型编码 → 本系统类型（微信常见编码，联调时校准）
_TYPE_MAP = {
    1: Message.MSG_TEXT,
    3: Message.MSG_IMAGE,
    43: Message.MSG_VIDEO,
    49: Message.MSG_LINK,  # appmsg：链接/文件类，暂归链接
}


def sync_once(app):
    """跑一轮同步。由定时器或测试触发。"""
    with app.app_context():
        cursor = _get_cursor()
        params = {
            "start_create_time": cursor.last_sync_time.strftime("%Y-%m-%d %H:%M:%S"),
            "page": 1,
            "page_size": PAGE_SIZE,
        }
        try:
            body = middle_client.call("messag_api", "get_message", params)
        except Exception:
            db.session.rollback()  # 拉取失败：游标不动，下一轮重来
            return

        items = _extract_messages(body)
        latest = cursor.last_sync_time
        pushed = []  # 本轮新入库的消息，commit 后统一广播
        for item in items:
            saved = _save_message(item)
            if saved is None:
                continue
            pushed.append(saved)
            if saved["create_time"] > latest:
                latest = saved["create_time"]

        cursor.last_sync_time = latest
        db.session.commit()

        # commit 之后才广播：保证前端听到推送时库里一定能查到
        from backend.ws import hub
        for saved in pushed:
            hub.broadcast("new_message", {
                "message_id": saved["message_id"],
                "conversation_id": saved["conversation_id"],
                "direction": saved["direction"],
                "msg_type": saved["msg_type"],
                "content": saved["content"],
                "sender_name": saved["sender_name"],
                "create_time": saved["create_time"].strftime("%Y-%m-%d %H:%M:%S"),
            })


def _get_cursor():
    """拿收消息游标，没有就建一行（从最近 1 小时开始）。"""
    row = (
        SyncCursor.query.filter_by(
            openid=MIDDLE_OPENID, cursor_type=SyncCursor.CURSOR_MSG
        )
        .filter(SyncCursor.deleted_at.is_(None))
        .first()
    )
    if row is None:
        row = SyncCursor(
            openid=MIDDLE_OPENID,
            cursor_type=SyncCursor.CURSOR_MSG,
            last_sync_time=datetime.now() - timedelta(hours=FIRST_HOURS),
        )
        db.session.add(row)
        db.session.flush()
    return row


def _extract_messages(body):
    """从 get_message 返回里取消息列表（结构以实际返回为准，联调校准）。"""
    data = body.get("data")
    if isinstance(data, list):
        return data
    return (data or {}).get("list") or []


def _save_message(item):
    """单条消息入库：去重 → 转字段 → 建/找会话 → 写 message → 更新会话。

    返回推送信息字典（commit 后供广播用）；重复或坏数据返回 None。
    """
    fields = _normalize(item)
    if fields is None:
        return None

    # 去重：middle_msg_id 已存在就整条跳过
    if fields["middle_msg_id"]:
        exists = (
            Message.query.filter_by(middle_msg_id=fields["middle_msg_id"])
            .filter(Message.deleted_at.is_(None))
            .first()
        )
        if exists is not None:
            return None

    conv = _get_or_create_conversation(fields["peer_wxid"], fields["chat_type"])

    msg = Message(
        conversation_id=conv.id,
        msg_type=fields["msg_type"],
        direction=fields["direction"],
        sender_wxid=fields["sender_wxid"],
        sender_name=fields["sender_name"],
        content=fields["content"],
        payload=fields["payload"],
        middle_msg_id=fields["middle_msg_id"],
        new_msg_id=fields["new_msg_id"],
        create_time=fields["create_time"],
    )
    db.session.add(msg)

    # 维护会话：最后一条消息冗余；只有收到的才计未读
    if fields["direction"] == Message.DIR_IN:
        conv.unread_count = (conv.unread_count or 0) + 1
    conv.last_msg = _short_summary(fields["msg_type"], fields["content"])
    conv.last_msg_at = fields["create_time"]

    return {
        "message_id": msg.id,
        "conversation_id": conv.id,
        "direction": fields["direction"],
        "msg_type": fields["msg_type"],
        "content": fields["content"],
        "sender_name": fields["sender_name"],
        "create_time": fields["create_time"],
    }


def _normalize(item):
    """中间方一条消息 → 入库字段。字段名以实际返回为准，联调校准。

    方向规则：接口带 is_sender=1 视为自己发出的；默认按客户发来的处理。
    """
    try:
        from_wxid = item.get("from_wxid", "")
        to_wxid = item.get("to_wxid", "")
        is_self = bool(item.get("is_sender")) or item.get("direction") == 1
        direction = Message.DIR_OUT if is_self else Message.DIR_IN
        peer_wxid = to_wxid if is_self else from_wxid
        if not peer_wxid:
            return None

        raw_type = item.get("msg_type")
        msg_type = _TYPE_MAP.get(raw_type, Message.MSG_TEXT)

        create_time = _parse_time(item.get("create_time"))
        if create_time is None:
            return None

        return {
            "direction": direction,
            "peer_wxid": peer_wxid,
            "chat_type": (
                Conversation.CHAT_GROUP
                if "@chatroom" in peer_wxid
                else Conversation.CHAT_SINGLE
            ),
            "sender_wxid": from_wxid,
            "sender_name": item.get("sender_name") or from_wxid,
            "msg_type": msg_type,
            "content": item.get("content", ""),
            "payload": dict(item),  # 原文全量留底
            "middle_msg_id": str(item.get("msg_id") or ""),
            "new_msg_id": str(item.get("new_msg_id") or ""),
            "create_time": create_time,
        }
    except Exception:
        return None  # 单条坏数据不拖垮整轮


def _parse_time(value):
    """兼容字符串 'YYYY-MM-DD HH:MM:SS' 和秒级时间戳两种格式。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(value), fmt)
        except ValueError:
            continue
    return None


def _get_or_create_conversation(peer_wxid, chat_type):
    """按 openid+wxid 找会话，没有就建（软删除过滤）。"""
    conv = (
        Conversation.query.filter_by(openid=MIDDLE_OPENID, wxid=peer_wxid)
        .filter(Conversation.deleted_at.is_(None))
        .first()
    )
    if conv is None:
        conv = Conversation(
            openid=MIDDLE_OPENID, wxid=peer_wxid, chat_type=chat_type
        )
        db.session.add(conv)
        db.session.flush()
    return conv


def _short_summary(msg_type, content):
    """会话列表的摘要：文本截 50 字，其他类型显示标签。"""
    labels = {
        Message.MSG_IMAGE: "[图片]",
        Message.MSG_FILE: "[文件]",
        Message.MSG_VIDEO: "[视频]",
        Message.MSG_LINK: "[链接]",
    }
    text = labels.get(msg_type, content or "")
    return text[:50]
