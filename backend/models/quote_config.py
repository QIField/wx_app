"""快捷报价配置：全局行（配件黑名单/价格系数）+ 用户行（面板执行开关/模式）。

- scope=global：全系统一行——配件黑名单、客户等级价格映射（报价 = 我方价 × 系数）。
- scope=user：每登录人一行——工作台 AI 执行开关与自动报价模式（跟随账号跨端一致）。
- 与通讯录自动报价开关（contact_remark_config.auto_quote_enabled，资格闸门）是两级开关，
  运行时二者 AND；真值表见 docs/auto-quote-plan.md 契约 C。
"""
from backend.extensions import db
from backend.models.base import BigIntPK, SoftDeleteMixin

SCOPE_GLOBAL = "global"
SCOPE_USER = "user"

ALLOWED_MODES = ("preview", "auto")

# 默认价格系数（与原型/方案一致；可在 global 行覆盖）
DEFAULT_PRICE_MAP = {"vip_a": "0.75", "vip_b": "0.82", "normal": "0.90"}

# 配件黑名单约束（接口层据此校验）
MAX_BLACKLIST = 20
MAX_PART_LEN = 20


class QuoteConfig(db.Model, SoftDeleteMixin):
    __tablename__ = "quote_config"

    id = db.Column(BigIntPK, primary_key=True, autoincrement=True)
    scope = db.Column(
        db.String(10), nullable=False,
        comment="作用域：global=全系统一行 / user=每登录人一行",
    )
    user_id = db.Column(
        BigIntPK, nullable=True,
        comment="user 行=登录人 id；global 行为 NULL",
    )
    parts_blacklist = db.Column(
        db.JSON, nullable=False, default=list,
        comment="配件黑名单（仅 global 行），命中不报价不自动发送",
    )
    price_map = db.Column(
        db.JSON, nullable=False, default=dict,
        comment="等级→报价系数（仅 global 行），key 对应 contact_remark_config.level",
    )
    ai_enabled = db.Column(
        db.Boolean, nullable=False, default=True,
        comment="工作台 AI 执行开关（仅 user 行），关=纯手动普通模式",
    )
    quote_mode = db.Column(
        db.String(10), nullable=False, default="preview",
        comment="自动报价模式（仅 user 行）：preview=仅侧边预览 / auto=自动发送",
    )
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    __table_args__ = (
        db.Index("idx_quote_config_user", "user_id"),
    )
