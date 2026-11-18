"""报价分析统计 API（拓展栏重做 · 报价分析视图数据源）。

口径与询价列表一致：join Conversation 限绑定设备（user_openids）。聚合在
Python 分桶——不用 SQL date 函数（跨 SQLite/MySQL 方言且单测好造数），
取数范围限最近 10 周，客服场景量级可控。

- GET /api/quote/stats?period=day|month
  day:   最近 15 天日桶；KPI=今日，对比=昨日
  month: 最近 10 周周桶（周一为界）；KPI=本月，对比=上月
"""
from bisect import bisect_right
from datetime import datetime, timedelta

from flask import Blueprint, g, jsonify, request

from backend.extensions import db
from backend.models.conversation import Conversation
from backend.models.quote_inquiry import QuoteInquiry
from backend.services.auth import require_role
from backend.services.devices import user_openids

bp = Blueprint("quote_stats", __name__)

DAY_BUCKETS = 15
WEEK_BUCKETS = 10
TOP_PARTS = 5
_PERIODS = ("day", "month")


def _floor_day(dt):
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def _week_start(dt):
    """该日所在周的周一 0 点。"""
    d = _floor_day(dt)
    return d - timedelta(days=d.weekday())


def _month_next(dt):
    """下月 1 日 0 点（当月窗口的右开边界）。"""
    return (dt + timedelta(days=32)).replace(day=1)


def _buckets(period, now):
    """period → [(start, end, label)] 旧→新：day=15 个日桶；month=10 个周桶。"""
    out = []
    if period == "day":
        start = _floor_day(now) - timedelta(days=DAY_BUCKETS - 1)
        for i in range(DAY_BUCKETS):
            b = start + timedelta(days=i)
            out.append((b, b + timedelta(days=1), b.strftime("%m-%d")))
    else:
        start = _week_start(now) - timedelta(weeks=WEEK_BUCKETS - 1)
        for i in range(WEEK_BUCKETS):
            b = start + timedelta(weeks=i)
            label = f"{b.strftime('%m-%d')}~{(b + timedelta(days=6)).strftime('%m-%d')}"
            out.append((b, b + timedelta(weeks=1), label))
    return out


def _period_window(period, now):
    """KPI 对比窗口：((当期起, 止), (上期起, 止))。day=今日/昨日；month=本月/上月。"""
    if period == "day":
        cur = _floor_day(now)
        return (cur, cur + timedelta(days=1)), (cur - timedelta(days=1), cur)
    first = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return (first, _month_next(first)), (_month_next(first - timedelta(days=32)), first)


def _fetch_rows(user_id, since):
    """绑定设备口径的询价聚合行 (created_at, vin, oem_no, part_name)，since 之后。"""
    openids = user_openids(user_id)
    if not openids:
        return []
    rows = (
        db.session.query(
            QuoteInquiry.created_at, QuoteInquiry.vin,
            QuoteInquiry.oem_no, QuoteInquiry.part_name,
        )
        .join(Conversation, QuoteInquiry.conversation_id == Conversation.id)
        .filter(
            QuoteInquiry.deleted_at.is_(None),
            Conversation.deleted_at.is_(None),
            Conversation.openid.in_(openids),
            QuoteInquiry.created_at >= since,
        )
        .all()
    )
    return [r for r in rows if r[0] is not None]


def _empty():
    return {"quote": 0, "oe": 0, "vin": 0}


def _count_in(rows, start, end):
    """窗口内计数：quote=新增询价；vin/oem 非空分别计 VIN 解析与 OE 次数。"""
    c = _empty()
    for created, vin, oem, _part in rows:
        if start <= created < end:
            c["quote"] += 1
            if (vin or "").strip():
                c["vin"] += 1
            if (oem or "").strip():
                c["oe"] += 1
    return c


def _aggregate(rows, buckets):
    """行分桶计数 + 配件 Top 计数（part_name|oem_no 组合键，全窗口口径）。

    桶按起点升序且互不重叠，二分定位行所属桶 O(log n)；落点早于首桶或
    晚于末桶（右开边界之外）丢弃。
    """
    starts = [b[0] for b in buckets]
    counts = [_empty() for _ in buckets]
    top = {}
    for created, vin, oem, part in rows:
        idx = bisect_right(starts, created) - 1
        if idx < 0 or created >= buckets[idx][1]:
            continue
        c = counts[idx]
        c["quote"] += 1
        if (vin or "").strip():
            c["vin"] += 1
        if (oem or "").strip():
            c["oe"] += 1
        key = f"{(part or '').strip()}|{(oem or '').strip()}"
        top[key] = top.get(key, 0) + 1
    return counts, top


def _top_parts(top):
    """组合键 → [{name, oe, ct}] 按次数降序取 Top5。"""
    out = []
    for key, ct in sorted(top.items(), key=lambda kv: -kv[1])[:TOP_PARTS]:
        name, oe = key.split("|", 1)
        out.append({"name": name or oe or "未知配件", "oe": oe, "ct": ct})
    return out


@bp.get("/api/quote/stats")
@require_role()
def quote_stats():
    """报价分析：KPI（当期/上期/差值）+ 趋势序列 + TOP 配件。"""
    period = (request.args.get("period") or "day").strip().lower()
    if period not in _PERIODS:
        return jsonify(code=400, msg="period 只能是 day / month"), 400

    now = datetime.now()
    buckets = _buckets(period, now)
    cur_w, prev_w = _period_window(period, now)
    rows = _fetch_rows(g.current_user.id, min(buckets[0][0], prev_w[0]))

    counts, top = _aggregate(rows, buckets)
    cur = _count_in(rows, cur_w[0], cur_w[1])
    prev = _count_in(rows, prev_w[0], prev_w[1])
    return jsonify(code=0, msg="success", data={
        "period": period,
        "kpi": cur,
        "prev": prev,
        "trend": {k: cur[k] - prev[k] for k in cur},
        "days": [b[2] for b in buckets],
        "series": {
            "quote": [c["quote"] for c in counts],
            "oe": [c["oe"] for c in counts],
            "vin": [c["vin"] for c in counts],
        },
        "top": _top_parts(top),
    })
