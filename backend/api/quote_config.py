"""快捷报价配置 API（quote_config：global 行 = 黑名单/系数/执行开关，user 行预留）。

- GET /api/quote/config：合并视图（global 行为主，user 行预留未启用）。
- PUT /api/quote/config：body 任意子集，全部仅 admin/developer 可写
  （黑名单/系数是业务配置；AI 执行开关/报价模式是全局总闸——自动报价由后台定时器
  触发，无登录人上下文，语义见 models/quote_config.py 模块注释）。
- 读侧容错：price_map 缺键时回落默认系数，保证阶段 4 计算永远拿得到全三档。
"""
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from backend.extensions import db
from backend.models.contact_remark_config import ContactRemarkConfig
from backend.models.quote_config import (
    ALLOWED_MODES, DEFAULT_PRICE_MAP, MAX_BLACKLIST, MAX_PART_LEN,
    SCOPE_GLOBAL, QuoteConfig,
)
from backend.services.audit import AuditModule, log_action
from backend.services.auth import require_role

bp = Blueprint("quote_config", __name__)

_MANAGE_ROLES = ("developer", "admin")


# ---------- 读取 ----------


def _global_row():
    return QuoteConfig.query.filter_by(scope=SCOPE_GLOBAL, deleted_at=None).first()


def merged_config(user_id=0):
    """合并视图（执行开关全局化后与 user_id 无关，保留签名兼容阶段 0 调用方）。"""
    g_row = _global_row()
    price_map = dict(DEFAULT_PRICE_MAP)
    if g_row:
        price_map.update(g_row.price_map or {})
    gate_dt = g_row.ai_enabled_at if g_row else None
    return {
        "parts_blacklist": list(g_row.parts_blacklist or []) if g_row else [],
        "price_map": price_map,
        "ai_enabled": bool(g_row.ai_enabled) if g_row else True,
        "ai_enabled_at": gate_dt.isoformat() if gate_dt else None,
        "ai_enabled_at_dt": gate_dt,  # datetime 对象，供业务代码直接比时间
        "quote_mode": (g_row.quote_mode if g_row else None) or "preview",
    }


# ---------- 校验 ----------


def _validate_blacklist(items):
    """配件黑名单：字符串去空去重，≤20 个、单个 ≤20 字 → (list, None) 或 (None, err)。"""
    parts = []
    for t in items if isinstance(items, list) else []:
        t = str(t).strip()
        if t and t not in parts:
            parts.append(t)
    if len(parts) > MAX_BLACKLIST:
        return None, f"黑名单最多 {MAX_BLACKLIST} 个配件"
    if any(len(t) > MAX_PART_LEN for t in parts):
        return None, f"单个配件不能超过 {MAX_PART_LEN} 字"
    return parts, None


def _validate_price_map(mapping):
    """价格系数：三档键必须齐全，系数 (0, 1] 两位小数 → (dict, None) 或 (None, err)。"""
    if not isinstance(mapping, dict):
        return None, "price_map 必须是对象"
    if set(mapping.keys()) != set(ContactRemarkConfig.ALLOWED_LEVELS):
        return None, f"price_map 必须且只能包含 {', '.join(ContactRemarkConfig.ALLOWED_LEVELS)}"
    out = {}
    for k, v in mapping.items():
        try:
            rate = float(v)
        except (TypeError, ValueError):
            return None, f"系数 {k} 必须是数字"
        if not 0 < rate <= 1:
            return None, f"系数 {k} 必须在 (0, 1] 区间"
        out[k] = f"{rate:.2f}"
    return out, None


def _save_global(body, diff):
    """黑名单/价格系数/AI 执行开关/报价模式 → global 行（仅 admin/developer）。"""
    parts, err = _validate_blacklist(body.get("parts_blacklist") or [])
    if err:
        return err
    if "price_map" in body:
        pmap, err = _validate_price_map(body.get("price_map"))
        if err:
            return err

    row = _global_row()
    if row is None:
        row = QuoteConfig(scope=SCOPE_GLOBAL)
        db.session.add(row)
    else:
        row.restore()
    if list(row.parts_blacklist or []) != parts:
        diff.append(f"配件黑名单{list(row.parts_blacklist or [])}→{parts}")
    row.parts_blacklist = parts
    if "price_map" in body:
        if dict(row.price_map or {}) != pmap:
            diff.append(f"价格系数{dict(row.price_map or {})}→{pmap}")
        row.price_map = pmap
    if "ai_enabled" in body:
        val = bool(body.get("ai_enabled"))
        # 新建行 flush 前实例属性为 None，按模型默认 True 参与比较
        cur = bool(row.ai_enabled) if row.ai_enabled is not None else True
        if cur != val:
            diff.append("AI开关开→关" if not val else "AI开关关→开")
            # 时间闸门：关→开 写当前时间；开→关 清空（下次再开重新计时）
            if val and not cur:
                row.ai_enabled_at = datetime.now()
            elif not val and cur:
                row.ai_enabled_at = None
        row.ai_enabled = val
    if "quote_mode" in body:
        mode = str(body.get("quote_mode") or "").strip()
        if mode not in ALLOWED_MODES:
            return "quote_mode 只能是 preview / auto"
        if (row.quote_mode or "preview") != mode:
            diff.append(f"报价模式[{row.quote_mode}]→[{mode}]")
        row.quote_mode = mode
    return None


# ---------- 端点 ----------


@bp.get("/api/quote/config")
@require_role()
def get_quote_config():
    return jsonify(code=0, msg="success", data=merged_config(g.current_user.id))


@bp.put("/api/quote/config")
@require_role()
def put_quote_config():
    body = request.get_json(silent=True) or {}
    keys = {"parts_blacklist", "price_map", "ai_enabled", "quote_mode"}
    if not (keys & set(body)):
        return jsonify(code=400, msg="无可保存字段"), 400
    if g.current_user.role not in _MANAGE_ROLES:
        return jsonify(code=403, msg="报价配置仅管理员可修改"), 403

    diff = []
    err = _save_global(body, diff)
    if err:
        db.session.rollback()
        return jsonify(code=400, msg=err), 400
    db.session.commit()
    # 价格系数变更 → 自动重算 pending/review 询价，让新系数立即生效
    if any("价格系数" in d for d in diff):
        from backend.services.quote_pricing import recompute_pending
        recompute_pending()
    log_action(
        AuditModule.SYSTEM, "保存报价配置",
        f"账号 {g.current_user.name}",
        detail=("；".join(diff) or "无变更")[:200],
    )
    return jsonify(code=0, msg="success", data=merged_config(g.current_user.id)), 200
