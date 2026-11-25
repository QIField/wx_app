"""user_device 关联表：系统账号 ↔ 设备字典（多对多，可跨组织）。

同一台设备允许多个账号关联（互不影响，解除关联只动自己的行）；
绑定顺序 = id 顺序（先绑定的排前面）。

openid / remark / online 是存量保留列——身份与显示名在 device 表，
在线状态也在 device 表。但新建行仍需把这三列从 device 字典冗余一份：
  - openid   是存量列，NOT NULL（MySQL 历史包袱），不冗余会触发 IntegrityError
  - remark   可空，新关联统一留 NULL
  - online   NOT NULL（MySQL 历史包袱），默认 ONLINE_UNKNOWN(-1)

构造 UserDevice 的推荐方式：
    UserDevice(user_id=..., device_id=...)
只传这两个，openid / online 自动从 device 字典冗余，online 默认 -1。
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
                       comment="存量保留列：迁移数据源 + 新关联冗余自 device.openid")
    remark = db.Column(db.String(64), comment="存量保留列：迁移数据源（已并入 device.name）")
    online = db.Column(db.SmallInteger, nullable=False, default=-1, server_default="-1",
                       comment="存量保留列：在线状态事实源已挪到 device 表；新关联默认 -1(未知)")
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime, nullable=False, server_default=db.func.now(), onupdate=db.func.now()
    )

    def __init__(self, **kwargs):
        """构造：新代码推荐只传 user_id + device_id。

        openid 自动从 device 字典冗余（传了则覆盖）；
        online 默认 -1（Device.ONLINE_UNKNOWN）；remark 默认 NULL。
        显式传参优先级更高。
        """
        from backend.models.device import Device

        # openid：device 字典能查到就冗余，否则用显式传入（存量迁移老行缺 device_id）
        if "openid" not in kwargs and kwargs.get("device_id") is not None:
            device = db.session.get(Device, kwargs["device_id"])
            if device is not None:
                kwargs["openid"] = device.openid

        # online：显式传入 > 默认 -1（NOT NULL，MySQL 存量库历史包袱要求）
        if "online" not in kwargs:
            kwargs["online"] = Device.ONLINE_UNKNOWN

        super().__init__(**kwargs)

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
