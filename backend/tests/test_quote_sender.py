"""自动报价发送单测（阶段 5）：模式闸门 / 图前文后 / 失败转 review / 广播形态。

中间方发送接口 mock（send_service.middle_sender，参数 kwargs 捕获），
广播 monkeypatch backend.ws.hub.broadcast 捕获。
"""
import pytest

from backend.config import SEND_ENABLED
from backend.extensions import db
from backend.models.conversation import Conversation
from backend.models.quote_inquiry import QuoteInquiry
from backend.models.quote_config import SCOPE_GLOBAL, QuoteConfig
from backend.services import quote_sender
from backend.sync import send_service

IMAGE = "https://data.gzbbr.com/admin/Tools.Pic/?frey_no=724500877"
TEXT = "【宝马 X3】\n节温器总成（OE 11538635689）\n报价 ¥72.16"


def make_conv(wxid="group1"):
    conv = Conversation(openid="dev01", wxid=wxid, chat_type=Conversation.CHAT_GROUP, name="测试群")
    db.session.add(conv)
    db.session.commit()
    return conv


def set_global_mode(mode):
    """global 行报价模式 upsert（merged_config 只读 global 行）。"""
    row = QuoteConfig.query.filter_by(scope=SCOPE_GLOBAL).first()
    if row is None:
        db.session.add(QuoteConfig(scope=SCOPE_GLOBAL, quote_mode=mode, ai_enabled=True))
    else:
        row.quote_mode = mode
    db.session.commit()


def make_inquiry(conv, image=IMAGE, text=TEXT, status=QuoteInquiry.ST_PENDING):
    """一条已算价（契约 A r 结构齐备）的询价行。"""
    row = QuoteInquiry(
        conversation_id=conv.id, sender_name="老王", part_name="节温器",
        oem_no="11538635689", status=status,
        price_json={
            "car": {"vin": "X", "brandName": "宝马", "model": "X3", "yearPattern": "2016",
                    "displacement": "2.0T", "fuel": "汽油"},
            "product": {"product_id": 1, "image": image, "product_name": "节温器总成"},
            "pricing": {"text": text, "final_price": "72.16"},
            "error": None,
        },
    )
    db.session.add(row)
    db.session.commit()
    return row


@pytest.fixture()
def sender_spy(monkeypatch):
    """捕获中间方 post_image/post_text 调用与 hub 广播。"""
    calls = {"image": [], "text": [], "broadcast": []}
    monkeypatch.setattr(send_service.middle_sender, "post_image",
                        lambda **kw: calls["image"].append(kw) or {"code": 0})
    monkeypatch.setattr(send_service.middle_sender, "post_text",
                        lambda **kw: calls["text"].append(kw) or {"code": 0})
    from backend.ws import hub

    monkeypatch.setattr(hub, "broadcast", lambda event, data: calls["broadcast"].append((event, data)))
    return calls


def test_skipped_in_preview_mode(app):
    """quote_mode=preview（默认）：不发送，保持 pending。"""
    conv = make_conv()
    row = make_inquiry(conv)
    assert quote_sender.auto_send_pending([row]) == 0
    assert row.status == QuoteInquiry.ST_PENDING


def test_skipped_when_send_disabled(app, monkeypatch):
    """SEND_ENABLED=false（只收不发阶段）：整体跳过。"""
    conv = make_conv()
    row = make_inquiry(conv)
    set_global_mode("auto")
    monkeypatch.setattr(quote_sender, "SEND_ENABLED", False)
    assert quote_sender.auto_send_pending([row]) == 0
    assert row.status == QuoteInquiry.ST_PENDING


def test_auto_send_image_first_then_text(app, sender_spy):
    """图前文后：先 post_image(img_url) 再 post_text(话术)，成功置已报价。"""
    conv = make_conv()
    row = make_inquiry(conv)
    set_global_mode("auto")

    assert quote_sender.auto_send_pending([row]) == 1
    assert [c["img_url"] for c in sender_spy["image"]] == [IMAGE]
    assert [c["content"] for c in sender_spy["text"]] == [TEXT]
    assert row.status == QuoteInquiry.ST_SENT
    assert row.sent_at is not None

    events = [d for e, d in sender_spy["broadcast"] if e == "new_message"]
    assert [m["msg_type"] for m in events] == [2, 1]  # 广播顺序 = 发送顺序
    assert events[0]["payload"]["img_url"] == IMAGE
    assert events[1]["content"] == TEXT
    assert all(m["direction"] == 2 for m in events)
    assert events[0]["operator_name"] == "自动报价"


def test_text_only_without_image(app, sender_spy):
    """无产品图：只发话术，照样置已报价。"""
    conv = make_conv()
    row = make_inquiry(conv, image="")
    set_global_mode("auto")

    assert quote_sender.auto_send_pending([row]) == 1
    assert sender_spy["image"] == []
    assert len(sender_spy["text"]) == 1
    assert row.status == QuoteInquiry.ST_SENT


def test_no_product_or_text_stays_pending(app):
    """无产品或无话术：没有可发内容，不发送不置状态。"""
    conv = make_conv()
    bare = make_inquiry(conv, image="")
    bare.price_json = {"car": None, "product": None, "pricing": {"text": ""}, "error": None}
    db.session.commit()
    assert quote_sender.auto_send_pending([bare]) == 0
    assert bare.status == QuoteInquiry.ST_PENDING


def test_dispatch_failure_goes_review(app, sender_spy, monkeypatch):
    """图片下发失败降级发话术，话术也失败才进 review。"""
    conv = make_conv()
    row = make_inquiry(conv)
    set_global_mode("auto")

    def boom(**kw):
        raise send_service.SendDispatchError("网络不可达")

    # 图片失败但话术成功 → 仍然已报价（图片是可选项，话术是核心交付）
    monkeypatch.setattr(send_service.middle_sender, "post_image", boom)
    assert quote_sender.auto_send_pending([row]) == 1
    assert row.status == QuoteInquiry.ST_SENT  # 话术发出去了
    assert len(sender_spy["text"]) == 1  # 话术确实发了
    assert len(sender_spy["image"]) == 0  # 图片失败没发
    # 只广播话术一条（图片失败不广播）
    events = [d for e, d in sender_spy["broadcast"] if e == "new_message"]
    assert [m["msg_type"] for m in events] == [1]

    # 话术也失败 → 进 review
    def boom_also_text(**kw):
        raise send_service.SendDispatchError("网络不可达")

    row2 = make_inquiry(conv)
    monkeypatch.setattr(send_service.middle_sender, "post_text", boom_also_text)
    assert quote_sender.auto_send_pending([row2]) == 0
    assert row2.status == QuoteInquiry.ST_REVIEW
    assert "自动发送失败" in row2.price_json["error"]


def test_batch_resilient(app, sender_spy, monkeypatch):
    """批量：单条发送异常不影响其余行。"""
    conv = make_conv()
    bad = make_inquiry(conv)
    good = make_inquiry(conv)
    set_global_mode("auto")

    real_post_text = send_service.middle_sender.post_text
    state = {"n": 0}

    def flaky(**kw):
        state["n"] += 1
        if state["n"] == 1:  # 第一条行（bad）的文本发送炸掉
            raise RuntimeError("意外异常")
        return {"code": 0}

    monkeypatch.setattr(send_service.middle_sender, "post_text", flaky)
    assert quote_sender.auto_send_pending([bad, good]) == 1
    assert bad.status in (QuoteInquiry.ST_REVIEW, QuoteInquiry.ST_PENDING)
    assert good.status == QuoteInquiry.ST_SENT
