"""forward_snapshot 合并转发快照表模型。

合并转发卡片（message.msg_type=9）的正文快照：服务端在转发时把每条原消息的
「发送者 + 内容」复制进来，之后原消息即使软删除也不影响回看（微信同款行为）。
嵌套深度限 1：快照行不再携带更深层卡片，避免无限递归展开。
"""
from datetime import datetime

from backend.extensions import db
from backend.models.base import BigIntPK, SoftDeleteMixin


class ForwardSnapshot(db.Model, SoftDeleteMixin):
    __tablename__ = "forward_snapshot"

    id = db.Column(BigIntPK, primary_key=True, autoincrement=True)
    forward_msg_id = db.Column(db.BigInteger, nullable=False, comment="所属转发卡片消息 id")
    seq = db.Column(db.Integer, nullable=False, comment="卡片内展示顺序（从 1 起）")
    sender_name = db.Column(db.String(128), comment="原消息发送者显示名（转发时经名册解析冻结）")
    sender_avatar = db.Column(db.String(512), comment="原消息发送者头像URL（转发时冻结）")
    content = db.Column(db.Text, comment="原消息内容快照（文本原文/类型占位标签）")
    create_time = db.Column(db.DateTime, nullable=False, default=datetime.now, comment="原消息时间")

    __table_args__ = (
        db.Index("idx_fwd_msg_seq", "forward_msg_id", "seq"),
    )
