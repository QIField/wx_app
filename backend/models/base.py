"""模型公共基类：软删除约定。"""
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
