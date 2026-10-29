"""sync_cursor 轮询游标表模型。"""
from backend.extensions import db
from backend.models.base import BigIntPK, SoftDeleteMixin


class SyncCursor(db.Model, SoftDeleteMixin):
    """游标：每台设备每个游标类型一行，记"上次同步到的时间点"。

    收消息每轮只拉 last_sync_time 之后的增量，不重复不遗漏。
    """

    CURSOR_MSG = "msg"  # 收消息游标

    __tablename__ = "sync_cursor"

    id = db.Column(BigIntPK, primary_key=True, autoincrement=True)
    openid = db.Column(db.String(64), nullable=False, comment="中间方设备标识")
    cursor_type = db.Column(db.String(32), nullable=False, comment="游标类型：msg=收消息")
    last_sync_time = db.Column(db.DateTime, nullable=False, comment="上次同步到的时间点")
    updated_at = db.Column(
        db.DateTime, nullable=False, server_default=db.func.now(), onupdate=db.func.now()
    )

    __table_args__ = (
        db.UniqueConstraint("openid", "cursor_type", name="uk_openid_type"),
    )
