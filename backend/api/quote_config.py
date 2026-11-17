"""快捷报价配置 API（quote_config：global 黑名单/系数 + user 执行开关/模式）。

- GET /api/quote/config：合并视图（global 行 + 当前登录人 user 行）。
- PUT /api/quote/config：body 任意子集。
  parts_blacklist / price_map → global 行，仅 admin/developer；
  ai_enabled / quote_mode → user 行，全角色（每人自己的执行开关）。
- 读侧容错：price_map 黑名单缺键时回落默认系数，保证阶段 4 计算永远拿得到全三档。
"""
from flask import Blueprint, g, jsonify, request

from backend.extensions import db
from backend.models.contact_remark_config import ContactRemarkConfig
from backend.models.quote_config import (
    ALLOWED_MODES, DEFAULT_PRICE_MAP, MAX_BLACKLIST, MAX_PART_LEN,
    SCOPE_GLOBAL, SCOPE_USER, QuoteConfig,
)
from backend.services.audit import AuditModule, log_action
from backend.services.auth import require_role

bp = Blueprint("quote_config", __name__)

_MANAGE_ROLES = ("developer", "admin")


# ---------- 读取 ----------


def _global_row():
    return QuoteConfig.query.filter_by(scope=SCOPE_GLOBAL, deleted_at=None).first()


def _user_row(user_id):
    return QuoteConfig.query.filter_by(
        scope=SCOPE_USER, user_id=user_id, deleted_at=None,
    ).first()


def merged_config(user_id):
    """合并视图：全局黑名单/系数 + 个人执行开关。阶段 2 触发器与前端都读这里。"""
    g_row, u_row = _global_row(), _user_row(user_id)
    price_map = dict(DEFAULT_PRICE_MAP)
    if g_row:
        price_map.update(g_row.price_map or {})
    return {
        "parts_blacklist": list(g_row.parts_blacklist or []) if g_row else [],
        "price_map": price_map,
        "ai_enabled": bool(u_row.ai_enabled) if u_row else True,
        "quote_mode": (u_row.quote_mode if u_row else None) or "preview",
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
    """黑名单/价格系数 → global 行（仅 admin/developer）。"""
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
    return None


def _save_user(body, diff):
    """执行开关/模式 → 当前登录人 user 行。"""
    row = _user_row(g.current_user.id)
    if row is None:
        row = QuoteConfig(scope=SCOPE_USER, user_id=g.current_user.id)
        db.session.add(row)
    else:
        row.restore()
    if "ai_enabled" in body:
        val = bool(body.get("ai_enabled"))
        if bool(row.ai_enabled) != val:
            diff.append("AI开关开→关" if not val else "AI开关关→开")
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
    touches_global = ("parts_blacklist" in body) or ("price_map" in body)
    touches_user = ("ai_enabled" in body) or ("quote_mode" in body)
    if not touches_global and not touches_user:
        return jsonify(code=400, msg="无可保存字段"), 400
    if touches_global and g.current_user.role not in _MANAGE_ROLES:
        return jsonify(code=403, msg="黑名单与价格系数仅管理员可修改"), 403

    diff = []
    if touches_global:
        err = _save_global(body, diff)
        if err:
            db.session.rollback()
            return jsonify(code=400, msg=err), 400
    if touches_user:
        err = _save_user(body, diff)
        if err:
            db.session.rollback()
            return jsonify(code=400, msg=err), 400
    db.session.commit()
    log_action(
        AuditModule.SYSTEM, "保存报价配置",
        f"账号 {g.current_user.name}",
        detail=("；".join(diff) or "无变更")[:200],
    )
    return jsonify(code=0, msg="success", data=merged_config(g.current_user.id)), 200
