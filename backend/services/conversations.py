"""会话通用服务：按设备+wxid 取或建会话、会话列表摘要文案。

收消息入库（message_sync）与主动发起会话（api/conversations）共用，
避免两处各写一份"找不到就建"的逻辑。
"""
from backend.extensions import db
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.sync import msg_xml


def get_or_create(openid, wxid, chat_type, create=True):
    """按 openid+wxid 找会话，没有就建（create=False 时只找不建）。

    噪音消息（message_sync）用只找不建模式：同步噪音不得凭空造出会话。
    """
    conv = (
        Conversation.query.filter_by(openid=openid, wxid=wxid)
        .filter(Conversation.deleted_at.is_(None))
        .first()
    )
    if conv is None and create:
        conv = Conversation(openid=openid, wxid=wxid, chat_type=chat_type)
        db.session.add(conv)
        db.session.flush()
    return conv


def short_summary(msg_type, content):
    """会话列表的摘要：文本截 50 字，XML 卡片取标题，其他类型显示标签。"""
    labels = {
        Message.MSG_IMAGE: "[图片]",
        Message.MSG_FILE: "[文件]",
        Message.MSG_VIDEO: "[视频]",
        Message.MSG_LINK: "[链接]",
        Message.MSG_VOICE: "[语音]",
        Message.MSG_EMOJI: "[表情]",
    }
    text = labels.get(msg_type)
    if text is None:
        text = content or ""
        if text.lstrip().startswith("<"):
            text = "[系统消息]"  # 拍一拍/游戏中心等无法识别的系统 XML
    if msg_type in (Message.MSG_LINK, Message.MSG_FILE):
        title = msg_xml.app_info(content).get("title")
        if title:
            text = f"{text} {title}"
    return text[:50]
