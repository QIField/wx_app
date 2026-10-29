"""send_task 发送任务表模型。"""
from backend.extensions import db
from backend.models.base import BigIntPK, SoftDeleteMixin


class SendTask(db.Model, SoftDeleteMixin):
    """发送任务：每条发出的消息对应一行，uuid 串起下发和确认。

    状态流转：0待下发 → 1已下发 → 2成功 / 3失败。
    """

    ST_PENDING = 0     # 待下发
    ST_DISPATCHED = 1  # 已下发（等中间方确认结果）
    ST_SUCCESS = 2     # 成功
    ST_FAILED = 3      # 失败

    __tablename__ = "send_task"

    id = db.Column(BigIntPK, primary_key=True, autoincrement=True)
    uuid = db.Column(db.String(64), nullable=False, comment="本次发送唯一标识（我们自己生成）")
    message_id = db.Column(db.BigInteger, comment="对应 message 表 id")
    action = db.Column(db.String(32), nullable=False, comment="中间方接口动作，如 post_text_message")
    request_payload = db.Column(db.JSON, comment="发出去的完整参数（留底排查）")
    status = db.Column(db.SmallInteger, nullable=False, default=ST_PENDING, comment="0待下发 1已下发 2成功 3失败")
    retry_count = db.Column(db.Integer, nullable=False, default=0, comment="确认重试次数")
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime, nullable=False, server_default=db.func.now(), onupdate=db.func.now()
    )

    __table_args__ = (
        db.UniqueConstraint("uuid", name="uk_uuid"),
        db.Index("idx_status", "status"),
    )
