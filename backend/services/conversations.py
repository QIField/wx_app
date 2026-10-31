"""会话通用服务：按设备+wxid 取或建会话。

收消息入库（message_sync）与主动发起会话（api/conversations）共用，
避免两处各写一份"找不到就建"的逻辑。
"""
from backend.extensions import db
from backend.models.conversation import Conversation


def get_or_create(openid, wxid, chat_type):
    """按 openid+wxid 找会话，没有就建（软删除过滤）。"""
    conv = (
        Conversation.query.filter_by(openid=openid, wxid=wxid)
        .filter(Conversation.deleted_at.is_(None))
        .first()
    )
    if conv is None:
        conv = Conversation(openid=openid, wxid=wxid, chat_type=chat_type)
        db.session.add(conv)
        db.session.flush()
    return conv
