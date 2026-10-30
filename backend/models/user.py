"""user 账号表模型：developer / admin / agent 三级角色。"""
from backend.extensions import db
from backend.models.base import BigIntPK

ROLE_DEVELOPER = "developer"  # 开发者：最高权限，含设备绑定与操作日志
ROLE_ADMIN = "admin"          # 管理员：账号管理（不可操作开发者行）
ROLE_AGENT = "agent"          # 客服：消息工作台

STATUS_ON = 1   # 启用
STATUS_OFF = 0  # 停用


class User(db.Model):
    """账号：登录凭证 + 角色权限 + 微信设备绑定。

    不做删除（操作日志靠姓名快照追溯，账号只停用）；open_id 一台设备绑一个账号。
    """

    __tablename__ = "user"

    id = db.Column(BigIntPK, primary_key=True, autoincrement=True)
    username = db.Column(db.String(64), nullable=False, unique=True, comment="登录账号")
    name = db.Column(db.String(64), nullable=False, comment="姓名（展示用）")
    role = db.Column(db.String(32), nullable=False, default=ROLE_AGENT,
                     comment="developer/admin/agent")
    open_id = db.Column(db.String(64), unique=True, comment="中间方设备标识，一台设备绑一个账号")
    password_hash = db.Column(db.String(255), nullable=False, comment="密码哈希")
    must_change_password = db.Column(
        db.SmallInteger, nullable=False, default=0,
        comment="1=仍是初始密码，登录后必须改密才能用",
    )
    status = db.Column(db.SmallInteger, nullable=False, default=STATUS_ON, comment="1启用 0停用")
    last_login_at = db.Column(db.DateTime, comment="最近一次登录时间")
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime, nullable=False, server_default=db.func.now(), onupdate=db.func.now()
    )

    def to_json(self, with_openid=False):
        """账号信息；open_id 是敏感配置，仅管理接口按需返回。"""
        data = {
            "id": self.id,
            "username": self.username,
            "name": self.name,
            "role": self.role,
            "status": self.status,
            "must_change_password": bool(self.must_change_password),
            "last_login_at": (
                self.last_login_at.strftime("%Y-%m-%d %H:%M:%S") if self.last_login_at else None
            ),
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }
        if with_openid:
            data["open_id"] = self.open_id or ""
        return data

    @property
    def enabled(self):
        return self.status == STATUS_ON
