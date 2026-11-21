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
    """客服自己发的消息也带（服务方靠它算 is_replied），统一署名【我回复】；失败发出的跳过。"""
    conv = make_conv("group1")
    cs = make_msg(conv.id, "宝马 1198 有货", direction=Message.DIR_OUT, sender="客服小张")
    items = build_chat_content([cs])
    assert items == [{"type": "input_text", "text": "2026-11-17 10:00:00【我回复】：宝马 1198 有货"}]

    failed = make_msg(conv.id, "这条没发出去", direction=Message.DIR_OUT,
                      sender="客服小张", status=Message.ST_FAILED)
    assert build_chat_content([failed]) == []


def test_build_chat_content_placeholders(app):
    """图片/语音/文件等无直链，V1 只带系统备注条目说明发送者；转发卡片跳过。"""
    conv = make_conv("group1")
    img = make_msg(conv.id, "IMG_001.jpg", msg_type=Message.MSG_IMAGE)
    fwd = make_msg(conv.id, "合并转发", msg_type=Message.MSG_FORWARD)
    items = build_chat_content([img, fwd])
    assert items == [{"type": "input_text",
                      "text": "2026-11-17 10:00:00【系统备注】：上一条是【老王】发的图片"}]


def test_build_chat_content_outgoing_self_reply(app):
    """接口契约：客服消息统一署名【我回复】，不看设备名称与 sender_name。"""
    from backend.models.device import Device
    db.session.add(Device(openid="dev-openid", name="辉哥设备A"))
    db.session.commit()
    conv = make_conv("group1")
    m = make_msg(conv.id, "宝马 1198 有货", direction=Message.DIR_OUT, sender="")
    items = build_chat_content([m])
    assert items == [{"type": "input_text", "text": "2026-11-17 10:00:00【我回复】：宝马 1198 有货"}]


# ---------- 分流（契约 B） ----------


def test_parse_scenarios_shapes():
    assert parse_scenarios([{"vin": "V"}]) == [{"vin": "V"}]
    assert parse_scenarios({"list": [{"vin": "V"}]}) == [{"vin": "V"}]
    assert parse_scenarios(None) == []
    assert parse_scenarios("junk") == []


def test_dispatch_status_gates(app):
    """守门顺序：黑名单 > quoted 闸门 > is_replied 闸门 > 缺字段(vin/part/oem 全空)丢弃 > pending。

    注意：空场景（vin/part_name/oem_no 全 None）现在直接丢弃，不入表。
    """
    conv = make_conv("group1")
    scenes = [
        {"sender_name": "甲", "part_name": "前保险杠总成", "vin": "VIN1", "quoted": False},   # 黑名单
        {"sender_name": "乙", "part_name": "节温器", "vin": "VIN2", "quoted": "true"},        # 跟进旧报价
        {"sender_name": "丙", "part_name": "节温器", "vin": "VIN3", "quoted": False,          # 客服已回复过
         "is_replied": True},
        {"sender_name": "丁", "quoted": False},                                              # 全缺 vin/part/oem → 丢弃
        {"sender_name": "戊", "part_name": "节温器", "vin": "VIN5", "quoted": False},         # 正常 VIN+配件
        {"sender_name": "己", "oem_no": "34356865613", "quoted": False},                      # 只有 OE 编号（纯数字零件号）
    ]
    rows = dispatch(conv.id, scenes, ["保险杠"])
    # 空场景（丁）不入表 → 只有 5 行
    assert [r.status for r in rows] == [
        QuoteInquiry.ST_BLOCKED, QuoteInquiry.ST_REVIEW,
        QuoteInquiry.ST_REVIEW, QuoteInquiry.ST_PENDING, QuoteInquiry.ST_PENDING,
    ]
    assert rows[0].quoted is False and rows[1].quoted is True


def test_dispatch_sender_name_unknown_normalized(app):
    """AI 输出「未知」署名归 None，不落未知进询价卡片。"""
    conv = make_conv("group1")
    rows = dispatch(conv.id, [{"sender_name": "未知", "vin": "VIN1"}], [])
    assert rows[0].sender_name is None


def test_dispatch_broadcasts_inquiry_changed(app, monkeypatch):
    """落库后广播 quote_inquiry_changed（拓展栏 feed 静默 refresh 信号）。"""
    captured = []
    monkeypatch.setattr("backend.services.quote_dispatch.broadcast",
                        lambda event, data: captured.append((event, data)))
    conv = make_conv("group1")
    rows = dispatch(conv.id, [{"sender_name": "老王", "part_name": "节温器", "vin": "VIN1"}], [])

    assert len(captured) == 1
    event, data = captured[0]
    assert event == "quote_inquiry_changed"
    assert data["created"] is True
    assert data["ids"] == [rows[0].id]
    assert data["conversation_id"] == conv.id
    assert data["statuses"] == [QuoteInquiry.ST_PENDING]


def test_dispatch_empty_scenes_no_broadcast(app, monkeypatch):
    """空场景不落表也不广播。"""
    captured = []
    monkeypatch.setattr("backend.services.quote_dispatch.broadcast",
                        lambda event, data: captured.append((event, data)))
    conv = make_conv("group1")
    assert dispatch(conv.id, [], []) == []
    assert captured == []


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


# ====================================================================
# 号码空格归一化修复（2026-11-21）
# 问题："264 200 3201" 这种空格分隔的号码无法被识别，
#       因为正则只匹配连续数字，空格打断后每段都不够 6 位。
# 修复：在号码提取前先将每行内空格分隔的数字片段合并。
# ====================================================================


class TestSpacedDigitNormalization:
    """带空格格式号码的识别测试。"""

    def test_extract_part_numbers_spaced_multiline(self):
        """核心测试用例：多行带空格号码批量识别。"""
        from backend.services.rule_extract import _extract_part_numbers
        from backend.services.text_utils import normalize_spaced_digits

        text = "264 200 3201\n238 501 9400"
        # 归一化验证
        norm = normalize_spaced_digits(text)
        assert norm == "2642003201\n2385019400"
        # 号码提取验证
        numbers = _extract_part_numbers(text)
        assert numbers == ["2642003201", "2385019400"]

    def test_extract_part_numbers_spaced_with_prefix(self):
        """带前缀的号码 + 空格分隔。"""
        from backend.services.rule_extract import _extract_part_numbers

        text = "LR025 632"
        numbers = _extract_part_numbers(text)
        assert numbers == ["LR025632"]

    def test_extract_part_numbers_spaced_mixed(self):
        """正常号码 + 带空格号码混合输入。"""
        from backend.services.rule_extract import _extract_part_numbers

        text = "11538635689\n264 200 3201"
        numbers = _extract_part_numbers(text)
        assert "11538635689" in numbers
        assert "2642003201" in numbers

    def test_extract_part_numbers_no_false_merge_brand(self):
        """不会误伤车型词："宝马 530Li" 里的 530 不会被拼接。"""
        from backend.services.rule_extract import _extract_part_numbers

        text = "宝马 530Li 报价"
        numbers = _extract_part_numbers(text)
        # 530 和 3 不会被拼成 5303（中间是字母 L，不是空格+数字）
        assert numbers == []

    def test_extract_part_numbers_standalone_still_works(self):
        """原有正常格式号码识别不受影响。"""
        from backend.services.rule_extract import _extract_part_numbers

        assert _extract_part_numbers("11538635689") == ["11538635689"]
        assert _extract_part_numbers("LR025632") == ["LR025632"]
        assert _extract_part_numbers("节温器 LR025632") == ["LR025632"]

    def test_has_long_digits_detects_spaced(self):
        """触发条件检测：带空格号码能正确触发识别流程。"""
        from backend.services.rule_extract import _has_long_digits

        assert _has_long_digits("264 200 3201") is True
        assert _has_long_digits("11538635689") is True
        assert _has_long_digits("短号 123") is False

    def test_rule_extract_with_spaced_numbers(self, app):
        """完整 rule_extract 流程：带空格号码消息 → 能提取出 oem_no。"""
        from backend.services.rule_extract import rule_extract

        conv = make_conv("group_spaced", chat_type=Conversation.CHAT_GROUP)
        msg = make_msg(conv.id, "264 200 3201\n238 501 9400")

        scenes = rule_extract([msg])
        assert len(scenes) >= 1
        oem_nos = scenes[0].get("oem_no") or ""
        assert "2642003201" in oem_nos
        assert "2385019400" in oem_nos

    def test_strip_noise_handles_spaced(self):
        """噪音剥离：带空格号码能被正确剥离，不会残留成伪配件名。"""
        from backend.services.auto_quote import _strip_noise_line

        # 带空格号码应该被完全剥离，剩下空串或纯空白
        result = _strip_noise_line("264 200 3201")
        # 号码被剥离后只剩空白
        assert result == ""

        # 混合场景：配件名 + 带空格号码 → 号码被剥离，配件名保留
        result = _strip_noise_line("节温器 264 200 3201")
        assert "节温器" in result


# ====================================================================
# VIN 自动补全安全修复（2026-11-21）
# 问题：客服 OUT 消息里复述的 VIN 也被扫进 all_vins，
#       导致"客户 A 的 VIN 补到客户 B 的询价"张冠李戴。
#       且 all_vins[0] 无脑补，不区分 sender。
# 修复：方向过滤（只扫 IN）+ sender 匹配 + 时序约束。
# ====================================================================


def test_vin_cross_link_out_direction_ignored(app):
    """客服 OUT 消息里的 VIN 不得被扫进 all_vins。"""
    from backend.services.rule_extract import _extract_vin_only_from_message
    from backend.models.message import Message

    conv = make_conv("group_vin", chat_type=Conversation.CHAT_GROUP)
    m_out = make_msg(conv.id, "好的 VIN 是 WBAWX3100G0L69597", direction=Message.DIR_OUT)
    assert _extract_vin_only_from_message(m_out) is None

    m_in = make_msg(conv.id, "我的 VIN 是 WBAWX3100G0L69597", direction=Message.DIR_IN)
    assert _extract_vin_only_from_message(m_in) == "WBAWX3100G0L69597"


def test_vin_cross_link_sender_isolation(app):
    """客户 A 的 VIN 不得补到客户 B 的询价上（多人群聊场景）。"""
    conv = make_conv("group_multi_vin", chat_type=Conversation.CHAT_GROUP)
    msg_a_vin = make_msg(conv.id, "WBAWX3100G0L69597", sender="客户A")
    msg_a_inq = make_msg(conv.id, "节温器多少钱", sender="客户A")
    msg_b_inq = make_msg(conv.id, "空气滤芯多少钱", sender="客户B")

    from backend.services.rule_extract import rule_extract
    scenes = rule_extract([msg_a_vin, msg_a_inq, msg_b_inq])

    for s in scenes:
        if s.get("sender_name") == "客户B":
            # 客户 B 没发过 VIN，也没带号码 → scene 里不该有 VIN
            assert not s.get("vin"), f"客户B 不应被补 VIN，实际={s.get('vin')!r}"


def test_vin_cross_link_same_sender_works(app):
    """同一 sender：先发 VIN 后发询价 → VIN 正确关联（设计目标不能被破坏）。"""
    conv = make_conv("group_same", chat_type=Conversation.CHAT_GROUP)
    msg_vin = make_msg(conv.id, "我的 VIN 是 WBAWX3100G0L69597", sender="老王")
    msg_inq = make_msg(conv.id, "节温器多少钱", sender="老王")

    from backend.services.rule_extract import rule_extract
    scenes = rule_extract([msg_vin, msg_inq])

    # 老王的询价应该带上老王自己发的 VIN
    assert any(s.get("vin") == "WBAWX3100G0L69597" and s.get("sender_name") == "老王" for s in scenes)


# ---------- AI 开关时间闸门（2026-11-21）----------


def test_time_gate_blocks_messages_before_enable(app, monkeypatch):
    """闸门生效时：message_time < ai_enabled_at 的历史消息不触发资格。"""
    conv = make_conv("gate1", chat_type=Conversation.CHAT_GROUP)
    make_remark("group", "gate1", enabled=True)

    gate_time = datetime(2026, 11, 21, 10, 0, 0)
    monkeypatch.setattr(
        auto_quote.auto_quote if hasattr(auto_quote, "auto_quote") else auto_quote,
        "merged_config",
        lambda *a, **kw: {
            "ai_enabled": True, "ai_enabled_at_dt": gate_time, "ai_enabled_at": gate_time.isoformat(),
            "parts_blacklist": [], "price_map": {}, "quote_mode": "preview",
        },
    )

    old = datetime(2026, 11, 20, 8, 0, 0)   # 闸门之前 → 不放行
    assert auto_quote.is_eligible(conv.id, message_time=old) is False

    new = datetime(2026, 11, 21, 11, 0, 0)  # 闸门之后 → 放行
    assert auto_quote.is_eligible(conv.id, message_time=new) is True


def test_time_gate_blocks_old_message_from_triggering_timer(app, monkeypatch):
    """闸门生效时：on_new_message 收到闸门前的旧消息 → 不起计时器。"""
    monkeypatch.setattr(auto_quote, "_timer_factory", FakeTimer)
    FakeTimer.started_count = 0

    conv = make_conv("gate2", chat_type=Conversation.CHAT_GROUP)
    make_remark("group", "gate2", enabled=True)

    gate_time = datetime(2026, 11, 21, 10, 0, 0)
    monkeypatch.setattr(auto_quote, "merged_config", lambda *a, **kw: {
        "ai_enabled": True, "ai_enabled_at_dt": gate_time, "ai_enabled_at": gate_time.isoformat(),
        "parts_blacklist": [], "price_map": {}, "quote_mode": "preview",
    })

    # 闸门前的补拉消息 → 不起计时器
    auto_quote.on_new_message(conv.id, message_time=datetime(2026, 11, 20, 8, 0, 0))
    assert conv.id not in auto_quote._timers  # 无计时器

    # 闸门后的新消息 → 正常起计时
    auto_quote.on_new_message(conv.id, message_time=datetime(2026, 11, 21, 11, 0, 0))
    assert conv.id in auto_quote._timers


def test_no_gate_when_ai_enabled_at_is_none(app, monkeypatch):
    """闸门未生效（ai_enabled_at_dt=None）时，任何消息时间都放行——开关从初始 True 直接用的场景。"""
    conv = make_conv("gate3", chat_type=Conversation.CHAT_GROUP)
    make_remark("group", "gate3", enabled=True)

    monkeypatch.setattr(auto_quote, "merged_config", lambda *a, **kw: {
        "ai_enabled": True, "ai_enabled_at_dt": None, "ai_enabled_at": None,
        "parts_blacklist": [], "price_map": {}, "quote_mode": "preview",
    })

    # 任何时间都放行
    assert auto_quote.is_eligible(conv.id, message_time=datetime(2020, 1, 1)) is True
    assert auto_quote.is_eligible(conv.id) is True  # 无时间参数也放行
