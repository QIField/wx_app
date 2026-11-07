"""device 设备字典：设备先入库，再由账号关联（多对多，可跨组织）。

一台设备可被多个账号关联、可关联到不同组织的账号；
openid 全局唯一是设备的真实身份，入库后不可改。
online 由在线检测轮询回写，是全系统唯一的在线状态事实源。
"""
from backend.extensions import db
from backend.models.base import BigIntPK, SoftDeleteMixin


class Device(db.Model, SoftDeleteMixin):
    """设备字典：openid（设备 ID）+ 名称 + 所属组织 + 在线状态。"""

    ONLINE_UNKNOWN = -1  # 尚未轮询到
    ONLINE_OFF = 0
    ONLINE_ON = 1

    __tablename__ = "device"

    id = db.Column(BigIntPK, primary_key=True, autoincrement=True)
    openid = db.Column(db.String(64), nullable=False, unique=True,
                       comment="中间方设备标识，全局唯一，录入后不可改")
    name = db.Column(db.String(64),
                     comment="设备名称（后台维护；存量迁移未命名的为空，待补选）")
    org_id = db.Column(BigIntPK, comment="所属组织 id（迁移遗留可空，后台创建时必填）")
    online = db.Column(db.SmallInteger, nullable=False, default=ONLINE_UNKNOWN,
                       comment="-1未知 0离线 1在线（check_online 定时轮询回写）")
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    @property
    def org_name(self):
        """组织名快照：按 id 查字典；未分配返回空串。"""
        if self.org_id is None:
            return ""
        from backend.models.org import Org
        org = db.session.get(Org, self.org_id)
        return org.name if org is not None else ""

    def to_json(self):
        """设备字典信息；openid 仅后台管理使用，不出现在客服工作台。"""
        return {
            "id": self.id,
            "openid": self.openid,
            "name": self.name or "",
            "org_id": self.org_id,
            "org_name": self.org_name,
            "online": self.online,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "deleted_at": self.deleted_at.strftime("%Y-%m-%d %H:%M:%S") if self.deleted_at else None,
        }
