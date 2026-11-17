"""统一备注配置：用户级（全局生效）与群级两级作用域，业务自建、不写回微信。

- scope=user：按成员 wxid 一行——私聊与所有群聊全局共用（配置跟随"人"），
  群成员入口写入的也是这一行，保证切换会话/群聊配置一致。
- scope=group：仅群自身（群备注名）。
- wxid 只存数据库与后端内部逻辑，出参一律经 anonymize 脱敏（alias 短码）。
- 标签为 JSON 整列覆盖；单次改写痕迹由 log_action 审计日志记录（含 before/after）。
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
    remark_name = db.Column(db.String(100), nullable=False, default="", comment="备注名称")
    auto_quote_enabled = db.Column(
        db.Boolean, nullable=False, default=False, comment="是否开启自动报价",
    )
    level = db.Column(
        db.String(20), nullable=False, default=LEVEL_NORMAL, server_default=LEVEL_NORMAL,
        comment="客户等级：vip_a/vip_b/normal（报价系数）",
    )
    tags = db.Column(db.JSON, nullable=False, default=list)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    __table_args__ = (
        db.UniqueConstraint("scope_type", "target_wxid", name="uk_remark_scope_target"),
        db.Index("idx_remark_target", "target_wxid"),
    )

    def to_json(self):
        return {
            "scope_type": self.scope_type,
            "remark_name": self.remark_name or "",
            "auto_quote_enabled": bool(self.auto_quote_enabled),
            "level": self.level or self.LEVEL_NORMAL,
            "tags": list(self.tags or []),
        }
