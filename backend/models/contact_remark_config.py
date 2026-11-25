"""统一备注配置：设备维度 —— scope_type + target_wxid + openid 唯一。

一个设备上的一个联系人/群 对应一行配置。同一联系人在不同设备上各有独立行，
互不影响；同一行被多账号关联到该设备时共享。

- scope_type=user  + target_wxid=好友wxid + openid：该设备上这个好友的全局备注
- scope_type=group + target_wxid=群wxid + openid：该设备上这个群的群级备注
- wxid 只存数据库与后端内部逻辑，出参一律经 anonymize 脱敏。
- 标签为 JSON 整列覆盖；单次改写痕迹由 log_action 审计日志记录。
"""
from backend.extensions import db
from backend.models.base import BigIntPK, SoftDeleteMixin

SCOPE_USER = "user"
SCOPE_GROUP = "group"


class ContactRemarkConfig(db.Model, SoftDeleteMixin):
    __tablename__ = "contact_remark_config"

    # 业务约束（接口层据此校验）
    MAX_REMARK_LEN = 100
    MAX_TAGS = 10
    MAX_TAG_LEN = 12

    # 客户等级（报价系数映射的 key，见 QuoteConfig.price_map）
    LEVEL_VIP_A = "vip_a"
    LEVEL_VIP_B = "vip_b"
    LEVEL_NORMAL = "normal"
    ALLOWED_LEVELS = (LEVEL_VIP_A, LEVEL_VIP_B, LEVEL_NORMAL)

    id = db.Column(BigIntPK, primary_key=True, autoincrement=True)
    scope_type = db.Column(
        db.String(10), nullable=False,
        comment="作用域：user=用户级(私聊+所有群聊全局生效) / group=群级",
    )
    target_wxid = db.Column(
        db.String(64), nullable=False, comment="目标wxid（user=成员/好友wxid，group=群ID）",
    )
    # ★ 2026-11-25 设备维度：同一个联系人在不同设备上各有独立行
    # 存量行 openid 为 NULL（db_migrate 回填后全部非空）；
    # 新代码创建行必须显式传 openid
    openid = db.Column(
        db.String(64), nullable=True, index=True,
        comment="所属设备 openid；NULL 表示未绑定设备（存量迁移遗留）",
    )
    remark_name = db.Column(db.String(100), nullable=False, default="", comment="备注名称")
    auto_quote_enabled = db.Column(
        db.Boolean, nullable=False, default=False, comment="是否开启自动报价",
    )
    level = db.Column(
        db.String(20), nullable=False, default=LEVEL_NORMAL, server_default=LEVEL_NORMAL,
        comment="客户等级：vip_a/vip_b/normal（报价系数）",
    )
    tags = db.Column(db.JSON, nullable=False, default=list)
    oe_detail_enabled = db.Column(
        db.Boolean, nullable=False, default=False,
        comment="是否在报价话术里显示原厂替换/对号的原始 OE 号码",
    )
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    __table_args__ = (
        # ★ 2026-11-25 设备维度唯一键：同一设备上 scope + wxid 唯一
        db.UniqueConstraint("scope_type", "target_wxid", "openid", "deleted_at",
                            name="uk_remark_scope_wxid_openid_deleted"),
    )

    def to_json(self):
        return {
            "scope_type": self.scope_type,
            "remark_name": self.remark_name or "",
            "auto_quote_enabled": bool(self.auto_quote_enabled),
            "oe_detail_enabled": bool(self.oe_detail_enabled),
            "level": self.level or self.LEVEL_NORMAL,
            "tags": list(self.tags or []),
        }
