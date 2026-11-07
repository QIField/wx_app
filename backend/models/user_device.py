"""user_device 关联表：系统账号 ↔ 设备字典（多对多，可跨组织）。

同一台设备允许多个账号关联（互不影响，解除关联只动自己的行）；
绑定顺序 = id 顺序（先绑定的排前面）。openid/remark/online 是存量保留列，
仅作迁移数据源，新代码不再写：身份与显示名在 device 表，在线状态也在 device 表。
"""
from backend.extensions import db
from backend.models.base import BigIntPK, SoftDeleteMixin


class UserDevice(db.Model, SoftDeleteMixin):
    """关联关系：系统账号 ↔ 设备字典（消息/会话/通讯录按 device.openid 隔离）。"""

    __tablename__ = "user_device"

    id = db.Column(BigIntPK, primary_key=True, autoincrement=True)
    user_id = db.Column(BigIntPK, nullable=False, index=True, comment="所属系统账号")
    device_id = db.Column(BigIntPK, index=True,
                          comment="关联设备字典 id（存量迁移前可为空）")
    openid = db.Column(db.String(64),
                       comment="存量保留列：迁移数据源，新关联自 device 冗余不回写")
    remark = db.Column(db.String(64), comment="存量保留列：迁移数据源（已并入 device.name）")
    online = db.Column(db.SmallInteger, comment="存量保留列：在线状态已挪到 device 表")
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime, nullable=False, server_default=db.func.now(), onupdate=db.func.now()
    )

    def to_json(self):
        """绑定信息：显示名/在线状态取自设备字典；设备缺失（迁移遗留）回退存量列。"""
        device = self.device
        if device is not None:
            return {
                "openid": device.openid,
                "display_name": device.name or "",
                "online": device.online,
            }
        return {
            "openid": self.openid or "",
            "display_name": self.remark or "",
            "online": self.online if self.online is not None else -1,
        }

    @property
    def device(self):
        """关联的设备字典行；未回填/设备缺失时返回 None。"""
        if self.device_id is None:
            return None
        from backend.models.device import Device
        return db.session.get(Device, self.device_id)
