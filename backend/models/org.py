"""org 组织字典模型（方案 A：仅归属标记，业务数据不隔离）。

五条种子（佛山 / 珠海 / 中山 / 东莞百业 / 东莞合峰）仅作初始引导，
之后由管理者在后台增删：删除是软删除（status=0），行保留保证历史引用可解析。
"""
from backend.extensions import db
from backend.models.base import BigIntPK

ORG_NAMES = ("佛山", "珠海", "中山", "东莞百业", "东莞合峰")


class Org(db.Model):
    """组织字典：账号归属标记 + 日志检索维度。"""

    __tablename__ = "org"

    id = db.Column(BigIntPK, primary_key=True, autoincrement=True)
    name = db.Column(db.String(64), nullable=False, unique=True, comment="组织名")
    status = db.Column(db.SmallInteger, nullable=False, default=1, comment="1启用 0停用（软删除）")
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    def to_json(self):
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "created_at": (
                self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None
            ),
        }

    @classmethod
    def ensure_seed(cls):
        """幂等种子：缺哪个补哪个；返回本次补充条数。"""
        existing = {o.name for o in cls.query.all()}
        missing = [name for name in ORG_NAMES if name not in existing]
        for name in missing:
            db.session.add(cls(name=name))
        db.session.commit()
        return len(missing)
