"""快捷报价查询代理 API 单测（拓展栏重做 · 手动报价视图数据源）。

上游全部 mock（qq_client 模块函数 monkeypatch），断言：编排链路、类型识别、
错误映射（QuoteApiError → 502 带步骤名）、缺参 400、爆炸图失败静默降级。
"""
import pytest

from backend import qq_client

VIN = "WBAWX3100G0L69597"
OE = "11538635689"

VININFO = [{
    "vin": VIN, "carBrandCode": "BMW", "carBrandName": "宝马",
    "carModelName": "进口宝马 X3 20iX", "fuelType": "汽油",
    "saleModelName": "进口宝马 X3 20iX 2016 2.0T 手自一体",
}]

PARTNO = [{"oeCode": "11 53 8 635 689", "oeCodeTrim": OE, "oeName": "节温器", "price4s": "628.14"}]

BRAND_ROW = {
    "product_id": 1, "brand_name": "博世", "name": "节温器总成",
    "cost_price": "96.21", "store_price": "300.00", "stock": 5,
    "bigpic": "https://data.gzbbr.com/pic/1.jpg", "l_model_zh": "X3",
    "display_number": [
        {"key": "OE", "number": OE},
        {"key": "PARTENT", "number": "724500401"},
        {"key": "store", "number": "A" + OE},
    ],
}
PRODUCT_ROW = {"no": OE, "child": [BRAND_ROW]}
IMAGES = [{"imageId": "10097483", "oeCode": OE}]
IMAGE_LIST = [{
    "imageLabel": "1", "oeName": "冷却液泵", "stdName": "电子水泵",
    "oeCode": OE, "price4s": "5220.00", "count": 1,
}]


def product_payload(rows, missing=()):
    """product_list 三层信封实测形态。"""
    return {"status": 200, "msg": "返回成功",
            "data": {"data": rows, "no_exist_oe": list(missing)}}


@pytest.fixture()
def upstream(monkeypatch):
    """全链 mock + 调用记录；用例可覆写某个键注入失败/空返回。"""
    calls = {}

    def patch(key, fn):
        monkeypatch.setattr(qq_client, key, fn)
        return fn

    patch("vininfo", lambda vin: calls.setdefault("vininfo", []).append(vin) or VININFO)
    patch("partno", lambda vin, nos: calls.setdefault("partno", []).append((vin, nos)) or PARTNO)
    patch("product_list", lambda num: calls.setdefault("product_list", []).append(num) or product_payload([PRODUCT_ROW]))
    patch("part_images", lambda vin, oe: calls.setdefault("part_images", []).append((vin, oe)) or IMAGES)
    patch("part_images_list",
          lambda vin, ids, oe, brand: calls.setdefault("pil", []).append((vin, ids, oe, brand)) or IMAGE_LIST)
    return calls


def search(client, payload):
    return client.post("/api/quote/query/manual-search", json=payload)


# ---------- manual-search：三条链路 ----------


def test_manual_search_vin_full_chain(client, upstream):
    resp = search(client, {"q": VIN, "part_name": "节温器"})
    body = resp.get_json()
    assert resp.status_code == 200 and body["code"] == 0
    data = body["data"]
    assert data["type"] == "vin"
    assert data["chain"] == ["VIN译码", "OE译码", "产品档案"]
    assert data["car"]["brandName"] == "宝马" and data["car"]["carBrandCode"] == "BMW"
    assert data["product"]["product_name"] == "节温器总成"
    assert data["product"]["display_number"]["value"] == OE
    assert data["partImagesList"][0]["oeName"] == "冷却液泵"
    # 爆炸图参数闭环：carBrandId 取 carBrandCode
    assert upstream["pil"] == [(VIN, "10097483", OE, "BMW")]


def test_manual_search_vin_without_part_name(client, upstream):
    """纯 VIN 不带件名：只出车型卡，不调译码/产品/爆炸图。"""
    resp = search(client, {"q": VIN})
    data = resp.get_json()["data"]
    assert resp.status_code == 200
    assert "vininfo" in upstream and "partno" not in upstream
    assert data["product"] is None and data["partImagesList"] is None


def test_manual_search_oe_direct(client, upstream):
    resp = search(client, {"q": OE})
    data = resp.get_json()["data"]
    assert resp.status_code == 200 and data["type"] == "oe"
    assert "product_list" in upstream and "vininfo" not in upstream
    assert data["car"] is None and data["product"]["brand_name"] == "博世"


def test_manual_search_name_chain(client, upstream):
    """名称查询：默认 VIN 译码 + 兜底车型（vininfo 命中则带 car）。"""
    resp = search(client, {"q": "节温器"})
    data = resp.get_json()["data"]
    assert resp.status_code == 200 and data["type"] == "name"
    assert upstream["partno"][0][0] == "WBAWX3100G0L69597"  # 兜底 VIN（原型同款）
    assert data["car"] is not None and data["product"] is not None


# ---------- manual-search：失败与降级 ----------


def test_manual_search_vin_miss(client, monkeypatch):
    monkeypatch.setattr(qq_client, "vininfo", lambda vin: [])
    resp = search(client, {"q": VIN})
    assert resp.status_code == 502
    assert "VIN 未命中" in resp.get_json()["msg"]


def test_manual_search_oe_miss_echo(client, monkeypatch):
    monkeypatch.setattr(qq_client, "product_list", lambda num: product_payload([], missing=[OE]))
    resp = search(client, {"q": OE})
    assert resp.status_code == 502
    assert "no_exist_oe" in resp.get_json()["msg"]


def test_manual_search_name_decode_fail(client, monkeypatch):
    """partno 空串字段 = 无档案（实测形态）→ 502 译码失败。"""
    monkeypatch.setattr(qq_client, "partno", lambda vin, nos: [{"oeCodeTrim": "", "oeCode": ""}])
    resp = search(client, {"q": "节温器"})
    assert resp.status_code == 502 and "译码失败" in resp.get_json()["msg"]


def test_manual_search_upstream_error_maps_502(client, monkeypatch):
    def boom(vin):
        raise qq_client.QuoteApiError("快捷报价服务不可达：boom")

    monkeypatch.setattr(qq_client, "vininfo", boom)
    resp = search(client, {"q": VIN})
    assert resp.status_code == 502 and "快捷报价服务不可达" in resp.get_json()["msg"]


def test_explosion_failure_degrades_not_fails(client, upstream, monkeypatch):
    """爆炸图上游不稳定（实测红线）：失败只降级 partImagesList=None，主结果照常。"""
    def boom(vin, oe):
        raise qq_client.QuoteApiError("上游 502")

    monkeypatch.setattr(qq_client, "part_images", boom)
    resp = search(client, {"q": VIN, "part_name": "节温器"})
    body = resp.get_json()
    assert resp.status_code == 200 and body["code"] == 0
    assert body["data"]["partImagesList"] is None


def test_explosion_empty_image_id_degrades(client, upstream, monkeypatch):
    monkeypatch.setattr(qq_client, "part_images", lambda vin, oe: [{"imageId": ""}])
    resp = search(client, {"q": VIN, "part_name": "节温器"})
    assert resp.get_json()["data"]["partImagesList"] is None


# ---------- 参数与鉴权 ----------


def test_manual_search_missing_q(client):
    assert search(client, {}).status_code == 400
    assert search(client, {"q": "  "}).status_code == 400


def test_query_endpoints_require_login(app):
    plain = app.test_client()
    assert plain.post("/api/quote/query/manual-search", json={"q": "x"}).status_code == 401
    assert plain.post("/api/quote/query/zpy", json={"number": "1"}).status_code == 401


# ---------- extract-parts / zpy / jqr / purchase-history ----------


def test_extract_parts_passthrough(client, monkeypatch):
    got = {}

    def fake_extract(content):
        got["content"] = content
        return [{"part_name": "节温器", "vin": "", "oem_no": OE, "quoted": False}]

    monkeypatch.setattr(qq_client, "extract_parts", fake_extract)
    resp = client.post("/api/quote/query/extract-parts", json={"text": "节温器多少钱"})
    body = resp.get_json()
    assert resp.status_code == 200 and body["data"][0]["part_name"] == "节温器"
    assert got["content"] == [{"type": "input_text", "text": "节温器多少钱"}]


def test_extract_parts_empty_text(client):
    assert client.post("/api/quote/query/extract-parts", json={}).status_code == 400


def test_zpy_and_jqr_passthrough(client, monkeypatch):
    monkeypatch.setattr(qq_client, "zpy", lambda num: [{"城市": "佛山", "含税售价": 628}])
    monkeypatch.setattr(qq_client, "jqr", lambda num: {"jy_data": [{"custom_brand_name": "博世"}]})
    zpy = client.post("/api/quote/query/zpy", json={"number": OE}).get_json()
    jqr = client.post("/api/quote/query/jqr", json={"number": OE}).get_json()
    assert zpy["code"] == 0 and zpy["data"][0]["城市"] == "佛山"
    assert jqr["code"] == 0 and jqr["data"]["jy_data"][0]["custom_brand_name"] == "博世"


def test_zpy_upstream_error(client, monkeypatch):
    def boom(num):
        raise qq_client.QuoteApiError("快捷报价业务失败：参数错误")

    monkeypatch.setattr(qq_client, "zpy", boom)
    resp = client.post("/api/quote/query/zpy", json={"number": OE})
    assert resp.status_code == 502


def test_purchase_history_args(client, monkeypatch):
    got = {}

    def fake_history(num, page=1, limit=5):
        got.update(number=num, page=page, limit=limit)
        return {"total": {"purchase_quantity": "3", "totalprice": "1884.42"},
                "list": {"total": 3, "current_page": "2", "last_page": 1, "data": []}}

    monkeypatch.setattr(qq_client, "purchase_history", fake_history)
    resp = client.post("/api/quote/query/purchase-history",
                       json={"number": OE, "page": 2, "limit": 10})
    body = resp.get_json()
    assert resp.status_code == 200 and body["code"] == 0
    assert got == {"number": OE, "page": 2, "limit": 10}
    assert body["data"]["total"]["purchase_quantity"] == "3"


def test_purchase_history_bad_args(client):
    assert client.post("/api/quote/query/purchase-history", json={}).status_code == 400
    assert client.post("/api/quote/query/purchase-history",
                       json={"number": OE, "page": "x"}).status_code == 400
