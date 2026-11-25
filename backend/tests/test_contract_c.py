"""契约 C 开关真值表全链路联调（阶段 6 验收②）：8 种组合逐一过。

组合 = 通讯录资格开关（群看群）× 全局 AI 开关 × 报价模式，链路
on_new_message →（资格+AI 闸门）→ analyze_conversation → dispatch → 算价 → 自动发送。

期望行为（docs/auto-quote-plan.md 契约 C，docs 模式口径以 quote_config.global 行为准）：
  资格或 AI 关 → 不分析不落表，流程根本不开始；
  资格+AI 过：mode=auto → 全自动发出（图前文后，置已报价）；
              mode=preview → 只算价入列预览（pending，人工在处理台发送）。

服务方（AI/译码/产品）与中间方发送全 mock，产物结构与阶段 2/4/5 单测同构。
"""
from datetime import datetime

import pytest

from backend import qq_client
from backend.extensions import db
from backend.models.contact_remark_config import ContactRemarkConfig
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.models.quote_config import SCOPE_GLOBAL, QuoteConfig
from backend.models.quote_inquiry import QuoteInquiry
from backend.services import auto_quote, quote_sender
from backend.sync import send_service

VIN = "WBAWX3100G0L69597"
IMAGE = "https://data.gzbbr.com/pic/1.jpg"
FINAL = "94.50"  # 开思价 105.00 × 普通系数 0.90

SCENES = [{"sender_name": "老王", "part_name": "节温器", "vin": VIN, "quoted": False}]


class FakeTimer:
    """替身计时器：只记录是否起过，不真实等待（联调断言闸门，不测 3s 时长）。"""

    def __init__(self, delay, func, args=()):
        self.delay, self.func, self.args = delay, func, args

    def start(self):
        pass

    def cancel(self):
        pass


def patch_chain(monkeypatch):
    """AI 分析 + 译码 + 产品查询 + 中间方发送 全替身（返回发送调用记录）。"""
    monkeypatch.setattr(qq_client, "extract_parts", lambda cc: {"list": SCENES})
    monkeypatch.setattr(qq_client, "vininfo", lambda vin: [{
        "carBrandName": "宝马", "carModelName": "X3",
        "saleModelName": "2021 2.0T 手自一体", "fuelType": "汽油", "vin": vin,
    }])
    monkeypatch.setattr(qq_client, "partno", lambda vin, part: [{
        "partsNo": part, "oeCode": "11 53 8 635 689", "oeCodeTrim": "11538635689",
        "oeName": "节温器", "price4s": "300.00", "count": "1", "brandCode": "",
    }])
    monkeypatch.setattr(qq_client, "product_list", lambda oe: {
        "status": 1, "msg": "success",
        "data": {"total": 1, "data": [  # 三层信封：data → 分页器 → 组行列表
            {"no": "P1", "child": [{
                "product_id": 1, "name": "节温器总成", "brand_name": "博世",
                "cost_price": "96.21", "price": "105.00", "store_price": "300.00", "stock": 5,
                "bigpic": IMAGE, "l_name_zh": "节温器总成", "l_model_zh": "",
                "display_number": [{"key": "OE", "number": "11538635689"}],
            }]},
        ]},
    })
    # 产品图：mock pick_product_pic 返回固定真实图 URL（不再绕开服务方调开思）
    monkeypatch.setattr(qq_client, "pick_product_pic", lambda rows: IMAGE)
    monkeypatch.setattr(auto_quote, "_timer_factory", FakeTimer)
    monkeypatch.setattr(quote_sender, "SEND_ENABLED", True)  # 不依赖本地 .env
    calls = {"image": [], "text": []}
    monkeypatch.setattr(send_service.middle_sender, "post_image",
                        lambda **kw: calls["image"].append(kw) or {"code": 0})
    monkeypatch.setattr(send_service.middle_sender, "post_text",
                        lambda **kw: calls["text"].append(kw) or {"code": 0})
    return calls


def make_conv():
    conv = Conversation(openid="dev-openid", wxid="group1",
                        chat_type=Conversation.CHAT_GROUP, name="真值表测试群")
    db.session.add(conv)
    db.session.commit()
    return conv


def make_msg(conv_id):
    db.session.add(Message(
        conversation_id=conv_id, msg_type=Message.MSG_TEXT, direction=Message.DIR_IN,
        sender_wxid="wxid_laowang", sender_name="老王", content="宝马X3 节温器多少钱",
        create_time=datetime(2026, 11, 17, 10, 0, 0),
        status=Message.ST_SENT,
    ))
    db.session.commit()


def set_remark(wxid, enabled):
    row = ContactRemarkConfig.query.filter_by(scope_type="group", target_wxid=wxid).first()
    if row is None:
        db.session.add(ContactRemarkConfig(scope_type="group", target_wxid=wxid,
                                           auto_quote_enabled=enabled))
    else:
        row.auto_quote_enabled = enabled
    db.session.commit()


def set_config(ai_enabled=None, quote_mode=None, openid="dev-openid"):
    """upsert device 行（按 conv.openid）。global 行不再管 ai_enabled / quote_mode。"""
    row = QuoteConfig.query.filter_by(scope="device", openid=openid, deleted_at=None).first()
    if row is None:
        row = QuoteConfig(scope="device", openid=openid)
        db.session.add(row)
    if ai_enabled is not None:
        row.ai_enabled = ai_enabled
    if quote_mode is not None:
        row.quote_mode = quote_mode
    db.session.commit()


COMBOS = [
    # (资格开关, AI 开关, 模式, 期望)：auto=全自动发出 / preview=入列待人工 / none=不进流程
    (True, True, "auto", "auto"),
    (True, True, "preview", "preview"),
    (True, False, "auto", "none"),
    (True, False, "preview", "none"),
    (False, True, "auto", "none"),
    (False, True, "preview", "none"),
    (False, False, "auto", "none"),
    (False, False, "preview", "none"),
]


@pytest.mark.parametrize("enabled,ai,mode,expect", COMBOS,
                         ids=[f"资格{e[0]}-AI{e[1]}-{e[2]}-{e[3]}" for e in COMBOS])
def test_contract_c_truth_table(app, monkeypatch, enabled, ai, mode, expect):
    calls = patch_chain(monkeypatch)
    conv = make_conv()
    make_msg(conv.id)
    set_remark(conv.wxid, enabled)
    set_config(ai_enabled=ai, quote_mode=mode)

    # 入口闸门：资格不过（含 AI 关）不起计时，流程根本不开始
    auto_quote.on_new_message(conv.id)
    if expect == "none":
        assert conv.id not in auto_quote._timers
        assert QuoteInquiry.query.count() == 0
        assert calls["image"] == [] and calls["text"] == []
        return

    assert conv.id in auto_quote._timers  # 过闸起计时
    auto_quote.cancel_timer(conv.id)      # FakeTimer 不真实等待，手动到点走全链
    auto_quote.analyze_conversation(conv.id)

    row = QuoteInquiry.query.one()
    assert row.price_json["pricing"]["final_price"] == FINAL, f"price_json={row.price_json}"  # 算价两个模式都做
    if expect == "auto":
        assert row.status == QuoteInquiry.ST_SENT and row.sent_at
        assert calls["image"] == []  # 图片不再下发
        assert "¥" in calls["text"][0]["content"]  # V2 模板：品牌比价行含价格
    else:  # preview：只入列，不发送
        assert row.status == QuoteInquiry.ST_PENDING
        assert calls["image"] == [] and calls["text"] == []
