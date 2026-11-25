"""快捷报价配置：两级 scope。

- scope=global：全系统一行——配件黑名单 / 价格系数 / AI 时间闸门兜底值。
  黑名单和系数是业务定价策略，所有设备共用。
  ai_enabled_at 兜底（device 行无闸门时回这里）。
- scope=device：每设备一行——ai_enabled / quote_mode / ai_enabled_at。
  各设备独立，互不影响。同一设备被多账号关联时共享这一行。
  ai_enabled_at 存该设备最近一次关→开时间点（闸门之前的历史消息不触发 AI）。

"两级 AND" 语义：
  is_eligible() 先过 ContactRemarkConfig.auto_quote_enabled（联系人级），
  再过 QuoteConfig.device.ai_enabled（设备级）。
  两级 AND 才真正触发 AI 分析。
"""
from backend.extensions import db
from backend.models.base import BigIntPK, SoftDeleteMixin

SCOPE_GLOBAL = "global"
SCOPE_USER = "user"
SCOPE_DEVICE = "device"

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
        comment="作用域：global=全系统一行 / user=每登录人一行（预留未启用） / device=每设备一行",
    )
    user_id = db.Column(
        BigIntPK, nullable=True,
        comment="user 行=登录人 id；global / device 行为 NULL",
    )
    # ★ 2026-11-25 设备维度：device 行填 openid，global/user 行为 NULL
    openid = db.Column(
        db.String(64), nullable=True, index=True,
        comment="device 行=设备 openid；global/user 行为 NULL",
    )
    # === global 行专属 ===
    parts_blacklist = db.Column(
        db.JSON, nullable=False, default=list,
        comment="配件黑名单（仅 global 行），命中不报价不自动发送",
    )
    price_map = db.Column(
        db.JSON, nullable=False, default=dict,
        comment="等级→报价系数（仅 global 行），key 对应 contact_remark_config.level",
    )
    # === global + device 行共有（device 行独立；global 行 ai_enabled / quote_mode 已废弃） ===
    # 注意：ai_enabled / quote_mode 在 device 行 NULL → 默认 True / preview
    # global 行的 ai_enabled / quote_mode 字段保留仅为历史兼容，不再参与判定
    ai_enabled = db.Column(
        db.Boolean, nullable=True, default=None,
        comment="AI 执行开关；global 行 = 全局总闸（默认 True），device 行 = 设备独立开关（NULL 回 global）",
    )
    ai_enabled_at = db.Column(
        db.DateTime, nullable=True,
        comment="AI 最近一次从关→开的时间闸门（仅 global 行使用）",
    )
    quote_mode = db.Column(
        db.String(10), nullable=True, default=None,
        comment="自动报价模式：preview / auto；device 行 NULL 回 global 行；global 行默认 preview",
    )
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    __table_args__ = (
        db.Index("idx_quote_config_user", "user_id"),
        # device 行按 openid + deleted_at 唯一（同一设备恢复软删行冲突）
        db.Index("idx_quote_config_openid", "openid"),
    )
