"""询价查询 + 人工动作 API 单测（阶段 3 查询 / 阶段 6 动作）。

查询：状态/会话过滤、分页、权限口径与出参脱敏。
动作：人工发送（改价话术联动/图前文后/409/403）、忽略，下发失败转 review。
"""
import pytest

from backend.extensions import db
from backend.models.contact_remark_config import ContactRemarkConfig
from backend.models.conversation import Conversation
from backend.models.quote_inquiry import QuoteInquiry
from backend.services.devices import user_openids

IMAGE = "https://data.gzbbr.com/pic/1.jpg"


def priced_json():
    """一条已算价的契约 A r 结构（与 test_quote_sender 同构，够话术重生成用）。"""
    return {
        "car": {"vin": "WBAWX3100G0L69597", "brandName": "宝马", "model": "X3",
                "yearPattern": "2016", "displacement": "2.0T", "fuel": "汽油"},
        "product": {"product_id": 1, "image": IMAGE, "product_name": "节温器总成",
                    "store_price": "300.00",
                    "child": [{"brand_name": "博世", "cost_price": "96.21",
                               "store_price": "300.00", "stock": 5}]},
        "pricing": {
            "text": "【宝马 X3 2016款 2.0T】\n节温器总成（OE 11538635689）\n博世 ¥96.21"
                    "\n报价 ¥72.16\n4S对照价 ¥300.00",
            "final_price": "72.16",
            "items": [{
                "part": "节温器", "oe": "11538635689",
                "product": {"product_id": 1, "product_name": "节温器总成",
                            "store_price": "300.00",
                            "child": [{"brand_name": "博世", "cost_price": "96.21",
                                       "store_price": "300.00", "stock": 5}]},
                "cost_price": "96.21", "store_price": "300.00",
                "final_price": "72.16", "save_percent": 76,
            }],
        },
        "error": None,
    }


def make_conv(openid, wxid, chat_type=Conversation.CHAT_GROUP, name="测试群"):
    conv = Conversation(openid=openid, wxid=wxid, chat_type=chat_type, name=name)
    db.session.add(conv)
    db.session.commit()
    return conv


def make_inquiry(conv, status=QuoteInquiry.ST_PENDING, **over):
    fields = dict(
        conversation_id=conv.id, sender_name="老王", vin=None,
        part_name="节温器", status=status,
    )
    fields.update(over)
    row = QuoteInquiry(**fields)
    db.session.add(row)
    db.session.commit()
    return row


def test_empty_for_account_without_devices(client):
    resp = client.get("/api/quote/inquiries")
    body = resp.get_json()
    assert resp.status_code == 200
    assert body["code"] == 0
    assert body["data"]["total"] == 0 and body["data"]["list"] == []


def test_lists_and_filters_by_status(client):
    conv = make_conv("dev01", "group1")
    make_inquiry(conv, status=QuoteInquiry.ST_PENDING)
    make_inquiry(conv, status=QuoteInquiry.ST_REVIEW, part_name="保险杠")
    make_inquiry(conv, status=QuoteInquiry.ST_BLOCKED, part_name="保险杠")

    all_rows = client.get("/api/quote/inquiries").get_json()["data"]
    assert all_rows["total"] == 3

    pending = client.get("/api/quote/inquiries?status=0").get_json()["data"]
    assert pending["total"] == 1 and pending["list"][0]["status_label"] == "待报价"

    review = client.get("/api/quote/inquiries?status=1").get_json()["data"]
    assert review["total"] == 1 and review["list"][0]["part_name"] == "保险杠"


def test_invalid_status_rejected(client):
    conv = make_conv("dev01", "group1")
    make_inquiry(conv)
    assert client.get("/api/quote/inquiries?status=abc").status_code == 400
    assert client.get("/api/quote/inquiries?status=9").status_code == 400


def test_filter_by_conversation(client):
    conv_a = make_conv("dev01", "group1", name="群A")
    conv_b = make_conv("dev01", "group2", name="群B")
    make_inquiry(conv_a)
    make_inquiry(conv_b, part_name="火花塞")

    data = client.get(f"/api/quote/inquiries?conversation_id={conv_b.id}").get_json()["data"]
    assert data["total"] == 1
    assert data["list"][0]["part_name"] == "火花塞"
    assert data["list"][0]["conversation_name"] == "群B"


def test_pagination_order_desc(client):
    conv = make_conv("dev01", "group1")
    for i in range(3):
        make_inquiry(conv, part_name=f"件{i}")
    data = client.get("/api/quote/inquiries?limit=2&page=2").get_json()["data"]
    assert data["total"] == 3 and len(data["list"]) == 1
    ids = [r["id"] for r in data["list"]]
    all_ids = [r["id"] for r in client.get("/api/quote/inquiries").get_json()["data"]["list"]]
    assert ids[0] == all_ids[2]  # 倒序分页对得上


def test_other_device_inquiries_hidden(client):
    """权限口径：只看自己绑定设备的会话询价（与工作台一致）。"""
    mine = make_conv("dev01", "group1")
    other = make_conv("dev99", "group_other")
    make_inquiry(mine)
    make_inquiry(other)
    assert user_openids(1)  # 前置：当前账号绑的是 dev01
    data = client.get("/api/quote/inquiries").get_json()["data"]
    assert data["total"] == 1
    assert data["list"][0]["conversation_id"] == mine.id


def test_row_shape_and_desensitize(client):
    conv = make_conv("dev01", "group1")
    row = make_inquiry(
        conv, vin="WBAWX3100G0L69597", oem_no="11538635689",
        price_json={"car": None, "pricing": {"final_price": "72.16"}},
        sent_at=None,
    )
    item = client.get("/api/quote/inquiries").get_json()["data"]["list"][0]
    assert item["id"] == row.id
    assert item["vin"] == "WBAWX3100G0L69597"
    assert item["quoted"] is False
    assert item["price_json"]["pricing"]["final_price"] == "72.16"
    assert "wxid" not in item  # 脱敏契约：wxid 不出参
    assert item["status"] == 0 and item["status_label"] == "待报价"
    assert item["sent_at"] is None and item["created_at"]


# ---------- 人工动作（阶段 6） ----------


@pytest.fixture()
def send_spy(monkeypatch):
    """中间方发送 mock（与 test_quote_sender 同款）：捕获 post_image/post_text 调用。"""
    from backend.sync import send_service

    calls = {"image": [], "text": []}
    monkeypatch.setattr(send_service.middle_sender, "post_image",
                        lambda **kw: calls["image"].append(kw) or {"code": 0})
    monkeypatch.setattr(send_service.middle_sender, "post_text",
                        lambda **kw: calls["text"].append(kw) or {"code": 0})
    return calls


def make_priced(conv, status=QuoteInquiry.ST_PENDING, **over):
    """一条已算价（契约 A r 结构齐备）的询价行。"""
    fields = dict(
        conversation_id=conv.id, sender_name="老王", vin="WBAWX3100G0L69597",
        part_name="节温器", oem_no="11538635689", status=status,
        price_json=priced_json(),
    )
    fields.update(over)
    row = QuoteInquiry(**fields)
    db.session.add(row)
    db.session.commit()
    return row


def test_send_text_only(client, send_spy):
    """人工发送：只发话术文本（图片不再下发），置已报价带 sent_at。"""
    conv = make_conv("dev01", "group1")
    row = make_priced(conv)
    resp = client.post(f"/api/quote/inquiries/{row.id}/send")
    body = resp.get_json()
    assert resp.status_code == 200 and body["code"] == 0
    assert send_spy["image"] == []  # 图片不再下发
    assert len(send_spy["text"]) == 1 and "¥72.16" in send_spy["text"][0]["content"]
    assert body["data"]["status"] == QuoteInquiry.ST_SENT
    assert body["data"]["sent_at"]


def test_send_with_price_rebuilds_text(client, send_spy):
    """改价发送：price_json 记改后价、节省百分比重算；新模板无报价行，话术结构不变。"""
    conv = make_conv("dev01", "group1")
    row = make_priced(conv)
    resp = client.post(f"/api/quote/inquiries/{row.id}/send", json={"price": 88})
    assert resp.status_code == 200
    text = send_spy["text"][0]["content"]
    assert "报价 ¥" not in text  # V2 模板品牌比价行展示价格
    assert "@老王" in text and "★1、" in text and "①" in text  # V2 带品牌比价行
    assert row.price_json["pricing"]["final_price"] == "88.00"
    assert row.price_json["pricing"]["items"][0]["save_percent"] == 71  # 1-88/300


def test_send_rejects_invalid_price(client, send_spy):
    """改价校验：非数字/非正数一律 400，不下发不置状态。"""
    conv = make_conv("dev01", "group1")
    row = make_priced(conv)
    for price in ("abc", "-5", "0"):
        assert client.post(f"/api/quote/inquiries/{row.id}/send",
                           json={"price": price}).status_code == 400
    assert send_spy["text"] == [] and send_spy["image"] == []
    assert row.status == QuoteInquiry.ST_PENDING


def test_send_without_text_rejected(client, send_spy):
    """无话术（纯车型卡/异常卡）：400 不发送，保持 pending。"""
    conv = make_conv("dev01", "group1")
    row = make_priced(conv)
    row.price_json = {"car": None, "product": None, "pricing": {"text": ""}, "error": None}
    db.session.commit()
    assert client.post(f"/api/quote/inquiries/{row.id}/send").status_code == 400
    assert send_spy["text"] == []
    assert row.status == QuoteInquiry.ST_PENDING


def test_send_conflict_when_sent(client, send_spy):
    """重复发送拒绝：已报价（sent）409。"""
    conv = make_conv("dev01", "group1")
    row = make_priced(conv, status=QuoteInquiry.ST_SENT)
    assert client.post(f"/api/quote/inquiries/{row.id}/send").status_code == 409
    assert send_spy["text"] == []


def test_send_hidden_for_other_device(client, send_spy):
    """权限口径：跨绑定设备的询价不可见 → 404。"""
    other = make_conv("dev99", "group_other")
    row = make_priced(other)
    assert client.post(f"/api/quote/inquiries/{row.id}/send").status_code == 404
    assert send_spy["text"] == []


def test_send_forbidden_when_send_disabled(client, send_spy, monkeypatch):
    """SEND_ENABLED=false（只收不发阶段）：403 不下发。"""
    conv = make_conv("dev01", "group1")
    row = make_priced(conv)
    monkeypatch.setattr("backend.api.quote_inquiry.SEND_ENABLED", False)
    assert client.post(f"/api/quote/inquiries/{row.id}/send").status_code == 403
    assert send_spy["text"] == []


def test_send_dispatch_failure_goes_review(client, send_spy, monkeypatch):
    """图片下发失败降级发话术，话术也失败才 502 + 转 review。"""
    conv = make_conv("dev01", "group1")
    row = make_priced(conv)
    from backend.sync import send_service

    def boom(**kw):
        raise send_service.SendDispatchError("网络不可达")

    # 图片失败但话术成功 → 200 已报价（图片降级）
    monkeypatch.setattr(send_service.middle_sender, "post_image", boom)
    resp = client.post(f"/api/quote/inquiries/{row.id}/send")
    assert resp.status_code == 200  # 话术发出去了
    assert row.status == QuoteInquiry.ST_SENT

    # 话术也失败 → 502 + 转 review
    row2 = make_priced(conv)
    monkeypatch.setattr(send_service.middle_sender, "post_text", boom)
    resp2 = client.post(f"/api/quote/inquiries/{row2.id}/send")
    assert resp2.status_code == 502
    assert row2.status == QuoteInquiry.ST_REVIEW
    assert "发送失败" in row2.price_json["error"]


def test_ignore_moves_to_ignored_and_conflict_on_sent(client):
    """忽略：pending → ignored（4）；已报价拒绝 409。"""
    conv = make_conv("dev01", "group1")
    row = make_inquiry(conv)
    body = client.post(f"/api/quote/inquiries/{row.id}/ignore").get_json()
    assert body["code"] == 0 and body["data"]["status"] == QuoteInquiry.ST_IGNORED

    sent = make_inquiry(conv, status=QuoteInquiry.ST_SENT)
    assert client.post(f"/api/quote/inquiries/{sent.id}/ignore").status_code == 409
