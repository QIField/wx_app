"""报价计算编排单测（阶段 4）：译码映射 / OE 解析 / 系数 / 话术 / 失败语义 / 契约 A 结构。

服务方接口全 mock（vininfo/partno/product_list），fixture 按 docs/quick-quote-api-test.md
实测返回同构（字段名逐一对齐），验证真实字段 → 契约 A 稳定结构的归一层。
"""
import pytest

from backend import qq_client
from backend.extensions import db
from backend.models.contact_remark_config import ContactRemarkConfig
from backend.models.conversation import Conversation
from backend.models.quote_inquiry import QuoteInquiry
from backend.services import quote_pricing

VIN = "WBAWX3100G0L69597"

# 实测同构数据（vininfo 字段名见测试报告 §4.5：carModelName/fuelType/saleModelName）
VININFO = [{
    "vin": VIN, "carBrandCode": "BMW", "carBrandName": "宝马",
    "carModelName": "进口宝马 X3 20iX",
    "saleModelName": "进口宝马 X3 20iX 2016 2.0T 手自一体",
    "fuelType": "汽油", "transmissionType": "自动",
}]

PARTNO = [{
    "partsNo": "节温器", "brandCode": "BMW", "count": "1",
    "oeCode": "11 53 8 635 689", "oeCodeTrim": "11538635689",
    "oeName": "节温器", "price4s": "1270.0",
}]

# 实测同构数据（product_list 真实结构：三层信封，组行 {no, child:[品牌行]}，字段挂品牌行）
PRODUCT_BRAND_MAIN = {
    "product_id": 91328, "name": "节温器总成", "l_name_zh": "节温器总成",
    "brand_name": "马勒(MAHLE)", "brand_id": "14",
    "cost_price": "88.00", "store_price": "1270.00",
    "bigpic": "https://data.gzbbr.com/admin/Tools.Pic/?frey_no=724500877",
    "l_model_zh": "适配宝马 N20",
    "display_number": [
        {"key": "OE", "number": "11538635689"},
        {"key": "PARTENT", "number": "724500877"},
        {"key": "store", "number": "A11538635689"},
    ],
    "stock": "46",
}
# 产品图的 mock 返回值：pick_product_pic 遍历 child[].pic 挑真实图
MOCK_PRODUCT_PIC_URL = "https://bbrdatatest.freyparts.cn/api/pic/show/?f=mockpic&u=8&bid=1"
PRODUCT_GROUP = {
    "no": 1,
    "child": [
        PRODUCT_BRAND_MAIN,
        {"brand_name": "原厂", "cost_price": "410.00", "store_price": "1270.00", "stock": "3"},
        {"brand_name": "盖茨(GATES)", "cost_price": "105.00", "store_price": "1270.00", "stock": "0"},
    ],
}
PRODUCT_LIST = {"status": 0, "msg": "success", "data": {"data": [PRODUCT_GROUP], "no_exist_oe": []}}
NO_PRODUCT_LIST = {"status": 0, "msg": "success", "data": {"data": [], "no_exist_oe": ["11538635689"]}}


def make_conv(wxid="group1", chat_type=Conversation.CHAT_GROUP):
    conv = Conversation(openid="dev01", wxid=wxid, chat_type=chat_type, name="测试会话")
    db.session.add(conv)
    db.session.commit()
    return conv


def make_remark(scope, wxid, level):
    row = ContactRemarkConfig(scope_type=scope, target_wxid=wxid, auto_quote_enabled=True, level=level)
    db.session.add(row)
    db.session.commit()
    return row


def make_inquiry(conv, vin=None, part_name=None, oem_no=None, status=QuoteInquiry.ST_PENDING):
    row = QuoteInquiry(
        conversation_id=conv.id, sender_name="老王", vin=vin,
        part_name=part_name, oem_no=oem_no, status=status,
    )
    db.session.add(row)
    db.session.commit()
    return row


@pytest.fixture()
def mock_api(monkeypatch):
    """按实测结构 mock 三个接口，并记录调用参数。"""
    calls = {"vininfo": [], "partno": [], "product_list": [], "pick_pic": []}
    monkeypatch.setattr(qq_client, "vininfo", lambda vin: calls["vininfo"].append(vin) or VININFO)
    monkeypatch.setattr(
        qq_client, "partno",
        lambda vin, nos: calls["partno"].append((vin, nos)) or PARTNO,
    )
    monkeypatch.setattr(
        qq_client, "product_list",
        lambda number: calls["product_list"].append(number) or PRODUCT_LIST,
    )
    # 产品图 mock：pick_product_pic 遍历 child 行挑真实图，记录参与的品牌行数
    monkeypatch.setattr(
        qq_client, "pick_product_pic",
        lambda rows: calls["pick_pic"].append(len(rows) if rows else 0) or MOCK_PRODUCT_PIC_URL,
    )
    return calls


# ---------- car 映射（vininfo 真实字段 → 契约 A 子集） ----------


def test_car_block_maps_real_fields(app, mock_api):
    car = quote_pricing._car_block(VIN)
    assert mock_api["vininfo"] == [VIN]
    assert car == {
        "vin": VIN, "brandName": "宝马", "model": "进口宝马 X3 20iX",
        "yearPattern": "2016", "displacement": "2.0T", "fuel": "汽油",
        "saleModelName": "进口宝马 X3 20iX 2016 2.0T 手自一体",
        "carBrandCode": "BMW",
    }


def test_car_block_no_match_returns_none(app, monkeypatch):
    monkeypatch.setattr(qq_client, "vininfo", lambda vin: [])
    assert quote_pricing._car_block(VIN) is None
    assert quote_pricing._car_block("") is None  # 无 VIN 不调接口


# ---------- OE 解析 ----------


def test_oem_no_preferred_over_decoding(app, mock_api, monkeypatch):
    conv = make_conv()
    row = make_inquiry(conv, oem_no="1665000075", part_name="上水管")
    partno_calls = []
    monkeypatch.setattr(qq_client, "partno", lambda *a: partno_calls.append(a))
    items = quote_pricing._resolve_items(row)
    assert items == [{"part": "上水管", "oe": "1665000075"}]
    assert partno_calls == []  # AI 已给 OE，不再译码


def test_decode_by_name_via_partno(app, mock_api):
    conv = make_conv()
    row = make_inquiry(conv, vin=VIN, part_name="节温器")
    items = quote_pricing._resolve_items(row)
    assert mock_api["partno"] == [(VIN, "节温器")]
    # 多 OE 展开后 item 现在携带 partno 层的 oe_name / price4s
    assert items == [{
        "part": "节温器", "oe": "11538635689",
        "oe_name": "节温器", "price4s": "1270.0",
    }]


def test_multi_part_lines_split(app, monkeypatch):
    """多件换行分隔：oem_no 与 part_name 一一对应，逐件成列表。"""
    conv = make_conv()
    row = make_inquiry(conv, part_name="油底壳\n节温器", oem_no="11127568087\n11538635689")
    items = quote_pricing._resolve_items(row)
    assert items == [
        {"part": "油底壳", "oe": "11127568087"},
        {"part": "节温器", "oe": "11538635689"},
    ]


def test_name_without_vin_cannot_decode(app):
    """缺 VIN + AI 没给 oem_no → 占位 item oe="0"（Block B 里 ★3 形态）。"""
    conv = make_conv()
    row = make_inquiry(conv, part_name="节温器")
    assert quote_pricing._resolve_items(row) == [{"part": "节温器", "oe": "0"}]


# ---------- 系数（契约 C 同口径：群看群/单聊看用户） ----------


def test_rate_group_uses_group_level(app):
    conv = make_conv("group1", Conversation.CHAT_GROUP)
    make_remark("group", "group1", ContactRemarkConfig.LEVEL_VIP_B)
    level, rate = quote_pricing._customer_rate(conv)
    assert (level, rate) == ("vip_b", 0.82)


def test_rate_single_uses_user_level(app):
    conv = make_conv("wxid_customer", Conversation.CHAT_SINGLE)
    make_remark("group", "wxid_customer", ContactRemarkConfig.LEVEL_VIP_A)  # 群行不该影响单聊
    make_remark("user", "wxid_customer", ContactRemarkConfig.LEVEL_VIP_A)
    level, rate = quote_pricing._customer_rate(conv)
    assert (level, rate) == ("vip_a", 0.75)


def test_rate_default_normal_without_remark(app):
    conv = make_conv("nobody")
    assert quote_pricing._customer_rate(conv) == ("normal", 0.90)


# ---------- 完整编排 ----------


def test_price_inquiry_full_chain_contract_a(app, mock_api):
    """VIN+名称链路：出契约 A r 结构，product 为归一后的稳定结构，价格 = cost × 系数。"""
    conv = make_conv("group1")
    make_remark("group", "group1", ContactRemarkConfig.LEVEL_VIP_B)  # vip_b 0.82
    row = make_inquiry(conv, vin=VIN, part_name="节温器")

    quote_pricing.price_inquiry(row)
    r = row.price_json
    assert row.status == QuoteInquiry.ST_PENDING
    assert r["car"]["brandName"] == "宝马" and r["car"]["model"] == "进口宝马 X3 20iX"
    assert r["product"]["product_id"] == 91328
    assert r["product"]["display_number"] == {"key": "OE", "value": "11538635689"}
    assert r["product"]["product_name"] == "节温器总成"
    assert r["product"]["store_number"] == "A11538635689"
    assert r["product"]["image"] == MOCK_PRODUCT_PIC_URL  # pick_product_pic 挑出真实图
    assert mock_api["pick_pic"] == [3]  # 3 个品牌行参与挑图
    assert [c["brand_name"] for c in r["product"]["child"]][0] == "马勒(MAHLE)"
    assert r["partImagesList"] is None and r["error"] is None
    pricing = r["pricing"]
    assert pricing["level"] == "vip_b" and pricing["rate"] == 0.82
    assert pricing["final_price"] == "72.16"  # 88.00 × 0.82
    item = pricing["items"][0]
    assert item["save_percent"] == 94  # 1 - 72.16/1270.00
    assert "★1、节温器 (11538635689)" in pricing["text"]
    # V9 话术：品牌｜产品名｜¥价格，按我方报价升序，直接贴不对齐
    assert "① 马勒(MAHLE)｜节温器总成｜¥72" in pricing["text"]
    assert "② 盖茨(GATES)｜¥86" in pricing["text"]
    assert "③ 原厂｜¥336" in pricing["text"]
    assert "4S" not in pricing["text"]
    assert "@老王" in pricing["text"]              # 统一 @ 发送者
    assert VIN in pricing["text"]                  # VIN 独立行
    # V7: saleModelName 已含品牌，不再重复拼 brandName
    assert "进口宝马 X3 20iX 2016 2.0T 手自一体" in pricing["text"]
    assert "宝马 进口宝马" not in pricing["text"]  # 不再出现 "宝马 宝马..." 重复
    assert "系数" not in pricing["text"]           # 话术不出现"系数"二字
    assert "————————————————" in pricing["text"]   # 分隔线 16 字符


def test_product_name_falls_back_to_l_name_zh(app, mock_api, monkeypatch):
    """真实品牌行可能是 l_name_zh 无 name——归一层兜底。"""
    conv = make_conv()
    row = make_inquiry(conv, oem_no="1665000075")
    group = {**PRODUCT_GROUP, "child": [
        {k: v for k, v in PRODUCT_BRAND_MAIN.items() if k != "name"},
    ]}
    monkeypatch.setattr(qq_client, "product_list", lambda n: {
        "status": 0, "msg": "success", "data": {"data": [group], "no_exist_oe": []},
    })
    quote_pricing.price_inquiry(row)
    assert row.price_json["product"]["product_name"] == "节温器总成"


def test_no_exist_oe_goes_review(app, mock_api, monkeypatch):
    conv = make_conv()
    row = make_inquiry(conv, oem_no="11538635689")
    monkeypatch.setattr(qq_client, "product_list", lambda n: NO_PRODUCT_LIST)
    quote_pricing.price_inquiry(row)
    assert row.status == QuoteInquiry.ST_REVIEW
    assert "查无此件" in row.price_json["error"]
    assert row.price_json["product"] is None
    # V6: 无产品档案的 item 也显示 ★标题 + OE（Block B 里 ★3-★5 的形态）
    assert "★1、11538635689" in row.price_json["pricing"]["text"]
    assert "————————————————" in row.price_json["pricing"]["text"]


def test_decode_fail_goes_review(app, mock_api, monkeypatch):
    """有件名但缺 VIN → 占位 item oe="0" → 查无档案 → review 人工补。"""
    conv = make_conv()
    row = make_inquiry(conv, part_name="节温器")
    # 真实产品库查 "0" 肯定没档案，mock 对齐这个行为
    monkeypatch.setattr(qq_client, "product_list", lambda n: NO_PRODUCT_LIST)
    quote_pricing.price_inquiry(row)
    assert row.status == QuoteInquiry.ST_REVIEW
    assert "产品库查无此件" in row.price_json["error"]


def test_vin_only_keeps_pending_car_card(app, mock_api):
    """只有 VIN 无件名：车型卡场景，product 为 null，不转 review。"""
    conv = make_conv()
    row = make_inquiry(conv, vin=VIN)
    quote_pricing.price_inquiry(row)
    assert row.status == QuoteInquiry.ST_PENDING
    r = row.price_json
    assert r["car"]["vin"] == VIN and r["product"] is None
    assert r["pricing"]["final_price"] is None


def test_api_error_keeps_pending_for_retry(app, mock_api, monkeypatch):
    """服务方异常：保持 pending，price_json 记 error 可重算。"""
    conv = make_conv()
    row = make_inquiry(conv, oem_no="1665000075")

    def boom(number):
        raise qq_client.QuoteApiError("快捷报价服务超时（90s）：productList")

    monkeypatch.setattr(qq_client, "product_list", boom)
    quote_pricing.price_inquiry(row)
    assert row.status == QuoteInquiry.ST_PENDING
    assert "超时" in row.price_json["error"]


def test_non_pending_row_skipped(app, mock_api):
    conv = make_conv()
    row = make_inquiry(conv, oem_no="1665000075", status=QuoteInquiry.ST_REVIEW)
    quote_pricing.price_inquiry(row)
    assert row.price_json is None and mock_api["product_list"] == []


def test_price_inquiries_batch_resilient(app, mock_api, monkeypatch):
    """批量报价：单条异常不影响其余，最后统一 commit。"""
    conv = make_conv()
    bad = make_inquiry(conv, oem_no="1665000075")
    good = make_inquiry(conv, oem_no="11538635689")

    def flaky(number):
        if number == "1665000075":
            raise qq_client.QuoteApiError("不可达")
        return PRODUCT_LIST

    monkeypatch.setattr(qq_client, "product_list", flaky)
    quote_pricing.price_inquiries([bad, good])
    assert bad.price_json["error"] and good.price_json["product"]["product_id"] == 91328
