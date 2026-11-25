"""快捷报价配置 API（quote_config：global 行 = 黑名单/系数；device 行 = 设备独立开关与模式）。

两级 scope 语义：
- scope=global：全系统一行（黑名单、价格系数、ai_enabled_at 兜底值）
- scope=device：每设备一行（openid + ai_enabled + quote_mode + ai_enabled_at）

合并视图 merged_config(openid)：
  parts_blacklist / price_map → 永远读 global 行
  ai_enabled / quote_mode → 只读 device 行（NULL 默认 True / preview）
  ai_enabled_at → device 行优先，没有再回 global 行兜底

权限：读侧所有登录人；写侧仅 admin/developer。
"""
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from backend.extensions import db
from backend.models.contact_remark_config import ContactRemarkConfig
from backend.models.quote_config import (
    ALLOWED_MODES, DEFAULT_PRICE_MAP, MAX_BLACKLIST, MAX_PART_LEN,
    SCOPE_DEVICE, SCOPE_GLOBAL, QuoteConfig,
)
from backend.services.audit import AuditModule, log_action
from backend.services.auth import require_role
from backend.services.devices import active_openid_for

bp = Blueprint("quote_config", __name__)

_MANAGE_ROLES = ("developer", "admin")


# ---------- scope 定位 ----------


def _global_row():
    return QuoteConfig.query.filter_by(scope=SCOPE_GLOBAL, deleted_at=None).first()


def _device_row(openid):
    """指定设备的 device scope 行；openid 为空返回 None。"""
    if not openid:
        return None
    return QuoteConfig.query.filter_by(
        scope=SCOPE_DEVICE, openid=openid, deleted_at=None,
    ).first()


def _active_openid():
    """当前登录人选定的设备 openid。

    优先级：request.args 里显式传的 openid > 绑定列表第一个。
    显式传了但不在绑定列表 → 按 active_openid_for 返回的错误处理（_save_device 会收不到 openid）。
    """
    req_openid = (request.args.get("openid") or "").strip()
    openid, err = active_openid_for(g.current_user, req_openid)
    return openid if err is None else None


# ---------- 合并读视图 ----------


def merged_config(openid=None):
    """合并视图（global 行 + device 行）。

    global 行 = 配件黑名单 / 价格系数 / AI 时间闸门（跟设备无关）。
    device 行 = 每设备独立的 ai_enabled / quote_mode，NULL 表示从未设置 → 默认 True / preview。

    注意：global 行的 ai_enabled / quote_mode 字段已废弃（2026-11-25 设备维度改造后），
    保留在表中仅为历史兼容，不再参与任何判定逻辑。
    """
    g_row = _global_row()
    d_row = _device_row(openid) if openid else None

    # global 行：parts_blacklist / price_map 永远从这里取；ai_enabled_at 兜底
    price_map = dict(DEFAULT_PRICE_MAP)
    if g_row:
        price_map.update(g_row.price_map or {})
    # 时间闸门：device 行优先（该设备独立的关→开时间点），没有再回 global 行兜底
    gate_dt = (d_row.ai_enabled_at if d_row else None) or (g_row.ai_enabled_at if g_row else None)

    # ai_enabled：device 行独立；device 行不存在或字段为 NULL → 默认 True（开）
    # global 行的 ai_enabled 旧值不再兜底
    if d_row is not None and d_row.ai_enabled is not None:
        ai_enabled = bool(d_row.ai_enabled)
    else:
        ai_enabled = True

    # quote_mode：device 行独立；device 行不存在或字段为 NULL → 默认 preview
    quote_mode = (d_row.quote_mode if d_row and d_row.quote_mode else None) or "preview"

    return {
        "parts_blacklist": list(g_row.parts_blacklist or []) if g_row else [],
        "price_map": price_map,
        "ai_enabled": ai_enabled,
        "ai_enabled_at": gate_dt.isoformat() if gate_dt else None,
        "ai_enabled_at_dt": gate_dt,  # datetime 对象，供业务代码直接比时间
        "quote_mode": quote_mode,
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


# ---------- 保存 ----------


def _save_global(body, diff):
    """黑名单/价格系数/AI 时间闸门 → global 行（仅 admin/developer）。"""
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
    # global 行只存时间闸门；ai_enabled / quote_mode 不在 global 行改，改 device 行
    return None


def _save_device(body, diff, openid):
    """设备级开关 / 模式 → device 行（仅 admin/developer）。

    ai_enabled 关→开时也写时间闸门（该设备下的"新消息"从此刻开始算）。
    """
    if not openid:
        return "缺少设备上下文（openid 为空）"

    row = _device_row(openid)
    if row is None:
        row = QuoteConfig(scope=SCOPE_DEVICE, openid=openid, ai_enabled=True, quote_mode="preview")
        db.session.add(row)
    else:
        row.restore()

    if "ai_enabled" in body:
        val = bool(body.get("ai_enabled"))
        cur = bool(row.ai_enabled) if row.ai_enabled is not None else True
        if cur != val:
            diff.append("设备AI开关开→关" if not val else "设备AI开关关→开")
            # 关→开：写时间闸门（该设备下闸门之前的历史消息不触发 AI）
            if val:
                row.ai_enabled_at = datetime.utcnow()
        row.ai_enabled = val

    if "quote_mode" in body:
        mode = str(body.get("quote_mode") or "").strip()
        if mode not in ALLOWED_MODES:
            return "quote_mode 只能是 preview / auto"
        if row.quote_mode != mode:
            diff.append(f"设备报价模式[{row.quote_mode}]→[{mode}]")
        row.quote_mode = mode

    return None


# ---------- 端点 ----------


@bp.get("/api/quote/config")
@require_role()
def get_quote_config():
    """读配置：合并视图（global 行 + 当前设备的 device 行）。"""
    openid = _active_openid()
    return jsonify(code=0, msg="success", data=merged_config(openid))


@bp.put("/api/quote/config")
@require_role()
def put_quote_config():
    body = request.get_json(silent=True) or {}
    keys = set(body.keys())
    allowed_global = {"parts_blacklist", "price_map"}
    allowed_device = {"ai_enabled", "quote_mode"}
    if not (keys & (allowed_global | allowed_device)):
        return jsonify(code=400, msg="无可保存字段"), 400
    if g.current_user.role not in _MANAGE_ROLES:
        return jsonify(code=403, msg="报价配置仅管理员可修改"), 403

    diff = []
    err = None
    # global 行字段
    if keys & allowed_global:
        err = _save_global({k: body[k] for k in allowed_global if k in body}, diff)
    # device 行字段
    device_keys = keys & allowed_device
    if err is None and device_keys:
        openid = _active_openid()
        if not openid:
            err = "无可用设备，无法保存设备级开关"
        else:
            err = _save_device({k: body[k] for k in device_keys}, diff, openid)

    if err:
        db.session.rollback()
        return jsonify(code=400, msg=err), 400
    db.session.commit()

    # 价格系数变更 → 自动重算所有 pending/review 询价
    if any("价格系数" in d for d in diff):
        from backend.services.quote_pricing import recompute_pending
        recompute_pending()

    log_action(
        AuditModule.SYSTEM, "保存报价配置",
        f"账号 {g.current_user.name}",
        detail=("；".join(diff) or "无变更")[:200],
    )
    openid = _active_openid()
    return jsonify(code=0, msg="success", data=merged_config(openid)), 200
