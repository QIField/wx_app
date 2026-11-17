"""自动报价触发器单测（阶段 2）：chat_content 组装 / 资格真值表 / 去抖 / 分流落表 / 编排。

网络层与定时器全 mock：extract_parts 用替身，Timer 用 FakeTimer 手动到点。
"""
from datetime import datetime

import pytest

from backend import qq_client
from backend.extensions import db
from backend.models.contact_remark_config import ContactRemarkConfig
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.models.quote_config import QuoteConfig
from backend.models.quote_inquiry import QuoteInquiry
from backend.services import auto_quote
from backend.services.quote_context import build_chat_content
from backend.services.quote_dispatch import dispatch, parse_scenarios


# ---------- 造数 ----------


def make_conv(wxid, chat_type=Conversation.CHAT_GROUP):
    conv = Conversation(openid="dev-openid", wxid=wxid, chat_type=chat_type, name="测试会话")
    db.session.add(conv)
    db.session.commit()
    return conv


def make_msg(conv_id, content, direction=Message.DIR_IN, msg_type=Message.MSG_TEXT,
             sender="老王", status=Message.ST_SENT):
    m = Message(
        conversation_id=conv_id, msg_type=msg_type, direction=direction,
        sender_wxid=f"wxid_{sender}", sender_name=sender, content=content,
        create_time=datetime(2026, 11, 17, 10, 0, 0), status=status,
    )
    db.session.add(m)
    db.session.commit()
    return m


def make_remark(scope, wxid, enabled=True):
    """upsert 开关行（真值表测试会对同一目标反复翻转）。"""
    row = ContactRemarkConfig.query.filter_by(scope_type=scope, target_wxid=wxid).first()
    if row is None:
        row = ContactRemarkConfig(scope_type=scope, target_wxid=wxid, auto_quote_enabled=enabled)
    else:
        row.restore()
        row.auto_quote_enabled = enabled
    db.session.add(row)
    db.session.commit()
    return row


def set_global_ai(enabled):
    """upsert 全局执行开关行（真值表会翻转多次，global 行只应有一行）。"""
    row = QuoteConfig.query.filter_by(scope="global", deleted_at=None).first()
    if row is None:
        row = QuoteConfig(scope="global", ai_enabled=enabled)
    else:
        row.ai_enabled = enabled
    db.session.add(row)
    db.session.commit()


# ---------- chat_content 组装（防切割） ----------


def test_build_chat_content_text_format(app):
    """文本整条进出：时间【昵称】：内容 格式逐字对齐服务方契约。"""
    conv = make_conv("group1")
    m = make_msg(conv.id, "节温器多少钱")
    items = build_chat_content([m])
    assert items == [{"type": "input_text", "text": "2026-11-17 10:00:00【老王】：节温器多少钱"}]


def test_build_chat_content_keeps_cs_messages(app):
    """客服自己发的消息也带（服务方靠它算 is_replied），失败发出的跳过。"""
    conv = make_conv("group1")
    cs = make_msg(conv.id, "宝马 1198 有货", direction=Message.DIR_OUT, sender="客服小张")
    items = build_chat_content([cs])
    assert items == [{"type": "input_text", "text": "2026-11-17 10:00:00【客服小张】：宝马 1198 有货"}]

    failed = make_msg(conv.id, "这条没发出去", direction=Message.DIR_OUT,
                      sender="客服小张", status=Message.ST_FAILED)
    assert build_chat_content([failed]) == []


def test_build_chat_content_placeholders(app):
    """图片/语音/文件等无直链，V1 只带占位备注；转发卡片跳过。"""
    conv = make_conv("group1")
    img = make_msg(conv.id, "IMG_001.jpg", msg_type=Message.MSG_IMAGE)
    fwd = make_msg(conv.id, "合并转发", msg_type=Message.MSG_FORWARD)
    items = build_chat_content([img, fwd])
    assert items == [{"type": "input_text", "text": "2026-11-17 10:00:00【老王】发送了一张图片"}]


# ---------- 分流（契约 B） ----------


def test_parse_scenarios_shapes():
    assert parse_scenarios([{"vin": "V"}]) == [{"vin": "V"}]
    assert parse_scenarios({"list": [{"vin": "V"}]}) == [{"vin": "V"}]
    assert parse_scenarios(None) == []
    assert parse_scenarios("junk") == []


def test_dispatch_status_gates(app):
    """守门顺序：黑名单 > quoted 闸门 > 缺字段 > pending。"""
    conv = make_conv("group1")
    scenes = [
        {"sender_name": "甲", "part_name": "前保险杠总成", "vin": "VIN1", "quoted": False},   # 黑名单
        {"sender_name": "乙", "part_name": "节温器", "vin": "VIN2", "quoted": "true"},        # 跟进旧报价
        {"sender_name": "丙", "quoted": False},                                              # 全缺字段
        {"sender_name": "丁", "part_name": "节温器", "vin": "VIN3", "quoted": False},         # 正常
    ]
    rows = dispatch(conv.id, scenes, ["保险杠"])
    assert [r.status for r in rows] == [
        QuoteInquiry.ST_BLOCKED, QuoteInquiry.ST_REVIEW,
        QuoteInquiry.ST_REVIEW, QuoteInquiry.ST_PENDING,
    ]
    assert rows[0].quoted is False and rows[1].quoted is True


# ---------- 资格判定（契约 C：群>用户，AND 全局开关） ----------


def test_eligibility_truth_table(app):
    conv_group = make_conv("group2", chat_type=Conversation.CHAT_GROUP)
    conv_single = make_conv("wxid_user1", chat_type=Conversation.CHAT_SINGLE)

    # 全局 AI 开（默认无 global 行=True）
    make_remark("group", "group2", enabled=True)
    make_remark("user", "wxid_user1", enabled=True)
    assert auto_quote.is_eligible(conv_group.id) is True
    assert auto_quote.is_eligible(conv_single.id) is True

    # 群开了、群行关 → 不报（用户行开也不报：群>用户）
    set_global_ai(True)
    make_remark("group", "group2", enabled=False)
    assert auto_quote.is_eligible(conv_group.id) is False

    # 单聊看用户开关
    make_remark("user", "wxid_user1", enabled=False)
    assert auto_quote.is_eligible(conv_single.id) is False

    # 全局执行开关关 → 全部不报
    make_remark("group", "group2", enabled=True)
    set_global_ai(False)
    assert auto_quote.is_eligible(conv_group.id) is False


# ---------- 去抖（3s 静默合并连发） ----------


class FakeTimer:
    def __init__(self, delay, func, args=()):
        self.delay, self.func, self.args = delay, func, args
        self.started = self.cancelled = False
        FakeTimer.started_count = getattr(FakeTimer, "started_count", 0) + 1

    def start(self):
        self.started = True

    def cancel(self):
        self.cancelled = True


def test_debounce_resets_on_new_message(app, monkeypatch):
    """连发消息：计时器不断重置；资格不过不起计时；到点只 fire 一次。"""
    monkeypatch.setattr(auto_quote, "_timer_factory", FakeTimer)
    monkeypatch.setattr(auto_quote, "_analyze_with_context", lambda cid: None)
    FakeTimer.started_count = 0

    conv = make_conv("group3", chat_type=Conversation.CHAT_GROUP)
    make_remark("group", "group3", enabled=True)

    auto_quote.on_new_message(conv.id)
    t1 = auto_quote._timers[conv.id]
    assert t1.started and t1.delay == auto_quote.ANALYZE_DELAY

    auto_quote.on_new_message(conv.id)  # 3s 内又来一条 → 重置（旧计时取消）
    assert t1.cancelled
    t2 = auto_quote._timers[conv.id]
    assert t2 is not t1

    # 资格不过：不起计时
    make_remark("group", "group3", enabled=False)
    FakeTimer.started_count = 0
    auto_quote.on_new_message(conv.id)
    assert FakeTimer.started_count == 0

    auto_quote.cancel_timer(conv.id)
    assert conv.id not in auto_quote._timers


# ---------- 分析编排（mock 服务方） ----------


def test_analyze_dispatch_and_flow(app, monkeypatch):
    """到点分析：场景落表正确；空场景不落表；QuoteApiError 不抛。"""
    conv = make_conv("group4", chat_type=Conversation.CHAT_GROUP)
    make_remark("group", "group4", enabled=True)
    make_msg(conv.id, "宝马X3 节温器多少钱")

    scenes = [{"sender_name": "老王", "part_name": "节温器", "vin": "", "quoted": False}]
    monkeypatch.setattr(qq_client, "extract_parts", lambda cc: {"list": scenes})
    rows = dispatch(conv.id, scenes, [])
    assert rows[0].status == QuoteInquiry.ST_PENDING

    monkeypatch.setattr(qq_client, "extract_parts", lambda cc: {"list": []})
    auto_quote.analyze_conversation(conv.id)  # 空场景：无异常无落表

    def boom(_cc):
        raise qq_client.QuoteApiError("服务超时")
    monkeypatch.setattr(qq_client, "extract_parts", boom)
    auto_quote._analyze_with_context(conv.id)  # 服务异常：日志兜底不抛

    assert QuoteInquiry.query.filter_by(conversation_id=conv.id).count() == 1
