"""message 消息表模型。"""
from datetime import datetime

from backend.extensions import db
from backend.models.base import BigIntPK, SoftDeleteMixin


class Message(db.Model, SoftDeleteMixin):
    """消息：收到的和发出的都存这里。

    中间方接口收发共 7 种消息类型（语音/表情只收不发）；发出的消息状态只有三种（没有已读回执）。
    """

    MSG_TEXT = 1
    MSG_IMAGE = 2
    MSG_FILE = 3
    MSG_VIDEO = 4
    MSG_LINK = 5
    MSG_VOICE = 6   # 只收不发（无对应发送接口）
    MSG_EMOJI = 7   # 只收不发

    DIR_IN = 1   # 收到
    DIR_OUT = 2  # 发出

    ST_SENDING = 0  # 发送中
    ST_SENT = 1     # 已发送
    ST_FAILED = 2   # 失败

    __tablename__ = "message"

    id = db.Column(BigIntPK, primary_key=True, autoincrement=True)
    conversation_id = db.Column(db.BigInteger, nullable=False, comment="所属会话")
    msg_type = db.Column(db.SmallInteger, nullable=False, comment="1文本 2图片 3文件 4视频 5链接卡片 6语音 7表情")
    direction = db.Column(db.SmallInteger, nullable=False, comment="1收到 2发出")
    sender_wxid = db.Column(db.String(64), comment="发送者wxid（群聊里是群成员）")
    sender_name = db.Column(db.String(128), comment="发送者昵称")
    content = db.Column(db.Text, comment="文本内容/文件名等摘要")
    payload = db.Column(db.JSON, comment="其他字段原文（图片url、视频时长等）")
    middle_msg_id = db.Column(db.String(64), comment="中间方消息id（撤回要用）")
    new_msg_id = db.Column(db.String(64), comment="中间方new_msg_id（撤回要用）")
    create_time = db.Column(db.DateTime, nullable=False, default=datetime.now, comment="消息时间")
    status = db.Column(db.SmallInteger, nullable=False, default=ST_SENDING, comment="0发送中 1已发送 2失败")
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    __table_args__ = (
        db.Index("idx_conv_time", "conversation_id", "create_time"),
        db.Index("idx_middle_msg", "middle_msg_id"),
    )
