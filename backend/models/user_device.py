"""user_device 绑定表：一个系统账号绑多台微信设备（一对多）。

绑定顺序 = id 顺序（先绑定的排前面）；openid 全局唯一——
一台设备同一时刻只能归一个系统账号，保证账号间数据严格隔离。
"""
from backend.extensions import db
from backend.models.base import BigIntPK


class UserDevice(db.Model):
    """绑定关系：系统账号 ↔ 微信设备（消息/会话/通讯录都按 openid 隔离）。"""

    ONLINE_UNKNOWN = -1  # 尚未轮询到
    ONLINE_OFF = 0
    ONLINE_ON = 1

    __tablename__ = "user_device"

    id = db.Column(BigIntPK, primary_key=True, autoincrement=True)
    user_id = db.Column(BigIntPK, nullable=False, index=True, comment="所属系统账号")
    openid = db.Column(db.String(64), nullable=False, unique=True,
                       comment="中间方设备标识，全局唯一：一台设备只绑一个账号")
    remark = db.Column(db.String(64), comment="设备备注名（顶栏账号卡片显示，空则显示 openid）")
    online = db.Column(db.SmallInteger, nullable=False, default=ONLINE_UNKNOWN,
                       comment="-1未知 0离线 1在线（check_online 定时轮询回写）")
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime, nullable=False, server_default=db.func.now(), onupdate=db.func.now()
    )

    @property
    def display_name(self):
        """卡片显示名：备注优先；无备注返回空串，由 API 层按绑定顺序补「设备N」。

        脱敏契约：不再回退 openid（那是设备微信号，不能出现在前端展示里）。
        """
        return self.remark or ""

    def to_json(self):
        """绑定信息；online 供顶栏卡片在线点显示。"""
        return {
            "openid": self.openid,
            "remark": self.remark or "",
            "display_name": self.display_name,
            "online": self.online,
        }
