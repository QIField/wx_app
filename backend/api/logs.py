"""接口调用日志查询（规范见 docs/interface-log.md）。

只读：仅供开发者排障检索；删除只走每日定时清理（保留 90 天）。
"""
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from backend.models.access_log import AccessLog
from backend.models.middle_call_log import MiddleCallLog
from backend.models.user import ROLE_DEVELOPER
from backend.services.auth import require_role

bp = Blueprint("logs", __name__)

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20


def _page_args():
    """分页参数：page 从 1 起，page_size 上限 100。"""
    try:
        page = max(1, int(request.args.get("page", 1)))
        page_size = min(MAX_PAGE_SIZE, max(1, int(request.args.get("page_size", DEFAULT_PAGE_SIZE))))
    except ValueError:
        page, page_size = 1, DEFAULT_PAGE_SIZE
    return page, page_size


def _parse_bound(value, end_of_day=False):
    """时间边界：完整时间或日期；日期形式的 end 补到当天 23:59:59。"""
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(value, fmt)
        except ValueError:
            continue
        if end_of_day and fmt == "%Y-%m-%d":
            dt += timedelta(days=1, seconds=-1)
        return dt
    return None


def _paginate(q, order_col):
    """统一分页返回结构 {items, total, page, page_size}，新→旧。"""
    page, page_size = _page_args()
    total = q.count()
    rows = q.order_by(order_col.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [r.to_json() for r in rows], "total": total,
            "page": page, "page_size": page_size}


@bp.get("/api/logs/access")
@require_role(ROLE_DEVELOPER)
def list_access_logs():
    """入站日志检索：start/end/path 前缀/user_id/org_id/status/method。"""
    q = AccessLog.query
    start = _parse_bound(request.args.get("start"))
    end = _parse_bound(request.args.get("end"), end_of_day=True)
    if start:
        q = q.filter(AccessLog.access_time >= start)
    if end:
        q = q.filter(AccessLog.access_time <= end)
    path = (request.args.get("path") or "").strip()
    if path:
        q = q.filter(AccessLog.path.like(f"{path}%"))
    for field, column in (("user_id", AccessLog.user_id), ("org_id", AccessLog.org_id)):
        value = (request.args.get(field) or "").strip()
        if value.isdigit():
            q = q.filter(column == int(value))
    status = (request.args.get("status") or "").strip()
    if status.startswith(">="):
        try:
            q = q.filter(AccessLog.status_code >= int(status[2:]))
        except ValueError:
            pass
    elif status.isdigit():
        q = q.filter(AccessLog.status_code == int(status))
    method = (request.args.get("method") or "").strip().upper()
    if method:
        q = q.filter(AccessLog.method == method)
    return jsonify(code=0, msg="success", data=_paginate(q, AccessLog.id))


@bp.get("/api/logs/middle")
@require_role(ROLE_DEVELOPER)
def list_middle_logs():
    """出站日志检索：start/end/module/action/uuid 精确/success/openid。"""
    q = MiddleCallLog.query
    start = _parse_bound(request.args.get("start"))
    end = _parse_bound(request.args.get("end"), end_of_day=True)
    if start:
        q = q.filter(MiddleCallLog.call_time >= start)
    if end:
        q = q.filter(MiddleCallLog.call_time <= end)
    for field, column in (("module", MiddleCallLog.module),
                          ("action", MiddleCallLog.action),
                          ("uuid", MiddleCallLog.uuid),
                          ("openid", MiddleCallLog.openid)):
        value = (request.args.get(field) or "").strip()
        if value:
            q = q.filter(column == value)
    success = (request.args.get("success") or "").strip()
    if success in ("0", "1"):
        q = q.filter(MiddleCallLog.success == int(success))
    return jsonify(code=0, msg="success", data=_paginate(q, MiddleCallLog.id))
