"""conversation 会话表模型。"""
from backend.extensions import db
from backend.models.base import BigIntPK, SoftDeleteMixin


class Conversation(db.Model, SoftDeleteMixin):
    """会话：一个设备对一个联系人/群只有一行（openid+wxid 唯一）。"""

    CHAT_SINGLE = 1  # 单聊
    CHAT_GROUP = 2   # 群聊

    __tablename__ = "conversation"

    id = db.Column(BigIntPK, primary_key=True, autoincrement=True)
    openid = db.Column(db.String(64), nullable=False, comment="中间方设备标识")
    wxid = db.Column(db.String(64), nullable=False, comment="对方微信ID（个人或群ID）")
    chat_type = db.Column(db.SmallInteger, nullable=False, default=CHAT_SINGLE, comment="1单聊 2群聊")
    name = db.Column(db.String(128), comment="对方昵称/群名")
    unread_count = db.Column(db.Integer, nullable=False, default=0, comment="未读数")
    pinned = db.Column(db.SmallInteger, nullable=False, default=0, comment="是否置顶 0否 1是")
    last_msg = db.Column(db.Text, comment="最后一条消息摘要（冗余）")
    last_msg_at = db.Column(db.DateTime, comment="最后一条消息时间")
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime, nullable=False, server_default=db.func.now(), onupdate=db.func.now()
    )

    __table_args__ = (
        db.UniqueConstraint("openid", "wxid", name="uk_openid_wxid"),
        db.Index("idx_last_msg_at", "last_msg_at"),
    )
