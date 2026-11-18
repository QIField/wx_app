"""报价分析统计 API 单测（拓展栏重做 · 真实聚合口径）。

造数用相对时间（now 为基准），覆盖：空库、day/月分桶、KPI 当期/上期/差值、
top 排序取 5、绑定设备隔离、period 校验。
"""
from datetime import datetime, timedelta

from backend.extensions import db
from backend.models.conversation import Conversation
from backend.models.quote_inquiry import QuoteInquiry


def make_conv(openid, wxid, name="测试群"):
    conv = Conversation(openid=openid, wxid=wxid, chat_type=Conversation.CHAT_GROUP, name=name)
    db.session.add(conv)
    db.session.commit()
    return conv


def make_inquiry(conv, created, vin=None, oem=None, part=None):
    row = QuoteInquiry(
        conversation_id=conv.id, sender_name="老王", vin=vin, oem_no=oem,
        part_name=part, status=QuoteInquiry.ST_PENDING, created_at=created,
    )
    db.session.add(row)
    db.session.commit()
    return row


def _today_at(hour=10):
    """今天 hour 点（0 点兜底：凌晨跑测试也不会落到昨天）。"""
    base = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return base + timedelta(hours=min(hour, 23), minutes=1)


def _yesterday():
    return _today_at() - timedelta(hours=12)


def stats(client, period="day"):
    resp = client.get(f"/api/quote/stats?period={period}")
    return resp, resp.get_json()


# ---------- 空库与结构 ----------


def test_stats_empty_all_zero(client):
    resp, body = stats(client)
    assert resp.status_code == 200 and body["code"] == 0
    data = body["data"]
    assert data["kpi"] == {"quote": 0, "oe": 0, "vin": 0}
    assert data["trend"] == {"quote": 0, "oe": 0, "vin": 0}
    assert len(data["days"]) == 15 and len(data["series"]["quote"]) == 15
    assert set(data["days"][0]) <= set("0123456789-")  # MM-DD 标签
    assert data["top"] == []


def test_stats_month_bucket_shape(client):
    resp, body = stats(client, period="month")
    data = body["data"]
    assert resp.status_code == 200
    assert len(data["days"]) == 10 and len(data["series"]["oe"]) == 10
    assert "~" in data["days"][-1]  # 周桶标签 MM-DD~MM-DD
    assert data["days"][0] < data["days"][-1]  # 旧→新


def test_stats_invalid_period(client):
    assert client.get("/api/quote/stats?period=week").status_code == 400
    assert client.get("/api/quote/stats?period=").status_code == 200  # 空=缺省 day


# ---------- KPI 与 trend ----------


def test_stats_day_kpi_trend(client):
    conv = make_conv("dev01", "group1")
    # 当期（今日）：3 条 —— 1 仅 VIN、1 仅 OE、1 双有
    make_inquiry(conv, _today_at(9), vin="WBAWX3100G0L69597")
    make_inquiry(conv, _today_at(10), oem="11538635689")
    make_inquiry(conv, _today_at(11), vin="WDC1671931V123456", oem="1665000075", part="上水管")
    # 上期（昨日）：2 条
    make_inquiry(conv, _yesterday(), oem="0005400017", part="火花塞")
    make_inquiry(conv, _yesterday())

    resp, body = stats(client)
    data = body["data"]
    assert resp.status_code == 200
    assert data["kpi"] == {"quote": 3, "oe": 2, "vin": 2}
    assert data["prev"] == {"quote": 2, "oe": 1, "vin": 0}
    assert data["trend"] == {"quote": 1, "oe": 1, "vin": 2}
    # 今日落在最后一个日桶
    assert data["series"]["quote"][-1] == 3
    assert data["series"]["vin"][-2] == 0  # 昨日桶有 vin 计数前的相邻桶为 0


def test_stats_month_kpi_uses_calendar_month(client):
    conv = make_conv("dev01", "group1")
    make_inquiry(conv, _today_at(8), oem="11538635689")
    resp, body = stats(client, period="month")
    data = body["data"]
    assert resp.status_code == 200
    assert data["kpi"]["quote"] == 1 and data["kpi"]["oe"] == 1
    # 月份趋势图：今日落在最后一个周桶
    assert data["series"]["quote"][-1] == 1


def test_stats_old_rows_out_of_range(client):
    conv = make_conv("dev01", "group1")
    make_inquiry(conv, datetime.now() - timedelta(days=100), oem="11111111")
    resp, body = stats(client)
    assert body["data"]["kpi"]["quote"] == 0  # 早于取数窗口（15 天）不进统计
    assert sum(body["data"]["series"]["quote"]) == 0


# ---------- TOP 配件 ----------


def test_stats_top_sorted_and_limited(client):
    conv = make_conv("dev01", "group1")
    today = _today_at(9)
    for _ in range(3):
        make_inquiry(conv, today, part="节温器", oem="11538635689")
    for _ in range(2):
        make_inquiry(conv, today, part="上水管", oem="1665000075")
    make_inquiry(conv, today, part="火花塞", oem="885625662")
    for i in range(5):  # 凑满超过 5 种组合，验证截断
        make_inquiry(conv, today, part=f"件{i}", oem=f"900000000{i}")

    _, body = stats(client)
    top = body["data"]["top"]
    assert len(top) == 5
    assert top[0] == {"name": "节温器", "oe": "11538635689", "ct": 3}
    assert top[1]["name"] == "上水管" and top[1]["ct"] == 2
    assert all(top[i]["ct"] >= top[i + 1]["ct"] for i in range(len(top) - 1))


def test_stats_top_falls_back_to_oe_name(client):
    conv = make_conv("dev01", "group1")
    make_inquiry(conv, _today_at(9), oem="11538635689")  # 无件名：name 回落 OE
    _, body = stats(client)
    assert body["data"]["top"][0]["name"] == "11538635689"


# ---------- 绑定设备隔离 ----------


def test_stats_isolated_by_device(client):
    mine = make_conv("dev01", "group1")
    theirs = make_conv("other-device", "group9")
    make_inquiry(mine, _today_at(9), oem="11538635689")
    make_inquiry(theirs, _today_at(9), oem="1665000075")

    _, body = stats(client)
    assert body["data"]["kpi"]["quote"] == 1  # 只统计自己绑定设备
