"""模型公共基类：软删除约定。"""
from datetime import datetime

from backend.extensions import db

# 主键统一用 BigInteger（MySQL）；sqlite 测试库用 Integer 兼容自增
BigIntPK = db.BigInteger().with_variant(db.Integer, "sqlite")


class SoftDeleteMixin:
    """软删除：删除只填 deleted_at 时间，永不执行 DELETE。

    查询默认要加 WHERE deleted_at IS NULL。
    """

    deleted_at = db.Column(
        db.DateTime, nullable=True, comment="软删除：NULL=正常，非NULL=删除时间"
    )

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def soft_delete(self):
        """打删除标记（可恢复）；调用方负责 commit。"""
        self.deleted_at = datetime.now()

    def restore(self):
        """撤销删除标记，原 id 与关联不变；调用方负责 commit。"""
        self.deleted_at = None
