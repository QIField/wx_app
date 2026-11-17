"""询价查询 API 单测（阶段 3）：状态/会话过滤、分页、权限口径与出参脱敏。"""
from backend.extensions import db
from backend.models.contact_remark_config import ContactRemarkConfig
from backend.models.conversation import Conversation
from backend.models.quote_inquiry import QuoteInquiry
from backend.services.devices import user_openids


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
