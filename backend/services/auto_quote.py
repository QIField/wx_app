"""自动报价触发器（阶段 2 核心，docs/auto-quote-plan.md 定案版流程）。

  收到新消息 → 资格判定（契约 C：通讯录开关（群看群/单聊看用户）
              AND 设备级 AI 执行开关 quote_config.device.ai_enabled）
  → 每会话 3s 去抖（新消息重置计时，等客户连发收齐）
  → 拉最近 10 条组装 chat_content → extract_parts_demand
  → 契约 B 状态机落表（quote_dispatch）。

触发器挂在消息同步链路里，任何异常只记日志，绝不影响收信。
定时器线程无 Flask 上下文，fire 时经 init_app 存入的 app 包 app_context。
"""
import logging
import re
import threading
from datetime import timedelta

from backend import qq_client
from backend.api.quote_config import merged_config
from backend.models.contact_remark_config import ContactRemarkConfig
from backend.models.conversation import Conversation
from backend.models.quote_inquiry import QuoteInquiry
from backend.services.quote_context import (
    build_chat_content, build_empty_check, fetch_recent_messages, split_by_progress,
)
from backend.services.quote_dispatch import dispatch, parse_scenarios
from backend.services.rule_extract import rule_extract, should_trigger
from backend.services.text_utils import normalize_spaced_digits

log = logging.getLogger(__name__)

ANALYZE_DELAY = 3.0  # 静默去抖：客户连发图+文字的间隔内不再触发
NEW_MSG_FOCUS_WINDOW_MINUTES = 60  # focus 时间窗：距离最新 IN 消息超过 60 分钟的陈旧 IN 消息，
                                   # 即使没被分析过也不从中提取配件（避免 41 小时前的旧询价
                                   # 被当成新询价融合进当前回复）

_app = None
_timers = {}
_lock = threading.Lock()
_timer_factory = threading.Timer  # 测试注入替身


def init_app(app):
    """由 create_app 调用：保存 app 引用供定时器线程包 app_context。"""
    global _app
    _app = app


# ---------- 资格判定（契约 C） ----------


def _remark_enabled(scope_type, wxid, openid):
    """设备维度的联系人级自动报价开关（设备独立，同一联系人在不同设备可单独开关）。"""
    q = ContactRemarkConfig.query.filter_by(
        scope_type=scope_type, target_wxid=wxid, deleted_at=None,
    )
    row = q.filter(ContactRemarkConfig.openid == openid).first() if openid else None
    if row is None:
        row = q.filter(ContactRemarkConfig.openid.is_(None)).first()  # 兼容迁移过渡
    return bool(row.auto_quote_enabled) if row else False


def is_eligible(conversation_id, message_time=None):
    """群会话只看群开关、单聊只看用户开关（群>用户），再 AND 全局+设备执行开关。

    message_time（datetime，可选）：若有值且 ai_enabled_at 闸门已生效
    （AI 最近从关→开），则 message_time < ai_enabled_at 的历史消息直接跳过。
    这层闸门挡掉补拉历史消息、AI 开关开启前已入库的旧消息。
    """
    conv = Conversation.query.filter_by(id=conversation_id, deleted_at=None).first()
    if conv is None:
        return False
    scope = "group" if conv.chat_type == Conversation.CHAT_GROUP else "user"
    if not _remark_enabled(scope, conv.wxid, conv.openid):
        return False
    cfg = merged_config(conv.openid)
    if not cfg["ai_enabled"]:
        return False
    # 时间闸门：AI 关→开后产生的 ai_enabled_at
    gate_at = cfg.get("ai_enabled_at_dt")
    if gate_at and message_time and message_time < gate_at:
        log.debug(
            "跳过闸门前历史消息 conv=%s msg_time=%s gate_at=%s",
            conversation_id, message_time, gate_at,
        )
        return False
    return True


# ---------- 去抖计时 ----------


def reset_timer(conversation_id):
    """起/重置该会话的 3s 静默计时（新消息不断来就不断顺延）。"""
    with _lock:
        old = _timers.pop(conversation_id, None)
        if old:
            old.cancel()
        timer = _timer_factory(ANALYZE_DELAY, _analyze_with_context, args=(conversation_id,))
        timer.daemon = True
        _timers[conversation_id] = timer
        timer.start()


def cancel_timer(conversation_id):
    with _lock:
        timer = _timers.pop(conversation_id, None)
    if timer:
        timer.cancel()


def on_new_message(conversation_id, message_time=None):
    """消息同步钩子入口：资格不过直接跳过；过了就重置计时。

    message_time（datetime，可选）：该消息的原始 create_time，用于与
    ai_enabled_at 闸门比较——闸门前的历史消息不触发 AI。
    """
    try:
        if not is_eligible(conversation_id, message_time=message_time):
            return
        reset_timer(conversation_id)
    except Exception:  # noqa: BLE001 触发器不影响收信
        log.exception("自动报价资格判定失败 conv=%s", conversation_id)


# ---------- 分析编排 ----------


def _analyze_with_context(conversation_id):
    """定时器线程入口：无 Flask 上下文，包一层。失败只记日志。"""
    with _app.app_context():
        try:
            analyze_conversation(conversation_id)
        except Exception:  # noqa: BLE001
            log.exception("自动报价分析失败 conv=%s", conversation_id)
        finally:
            from backend.extensions import db

            db.session.remove()


# ---------- 空壳 scene 检测（2026-11-20 层 1 修复） ----------
# 问题：普通识别产出 scene 但 part_name 全 None → 挡掉了 AI 兜底。
# 修复：如果 scenes 全是空壳 且 窗口里有中文配件文字 → 清空 scenes 让 AI 兜底。


def _all_scenes_shell(scenes) -> bool:
    """所有 scene 都缺 part_name → 空壳（只有 VIN/OE 没配件名）。

    True 条件：scenes 非空 且 每个 scene 的 part_name strip 后都为空。
    """
    if not scenes:
        return False
    return all(
        not (s.get("part_name") or "").strip()
        for s in scenes
    )


# 剥 VIN（17 位大写字母+数字，不含 O/I/Q）
_STRIP_VIN_RE = re.compile(r'[A-HJ-NPR-Z0-9]{17}', re.IGNORECASE)
# 剥带前缀的号码（LR025632、GDB12345）
_STRIP_OEM_PREFIX_RE = re.compile(r'\b[A-Z]{1,4}\d{5,}\b', re.IGNORECASE)
# 剥纯数字（≥6 位）
_STRIP_OEM_DIGITS_RE = re.compile(r'\b\d{6,}\b')
# 剥品牌车型词（避免把"宝马 530Li"误判成配件名）
_BRAND_CAR_WORDS = frozenset({
    '宝马', '奔驰', '奥迪', '大众', '丰田', '保时捷', '路虎', '沃尔沃',
    '本田', '日产', '福特', '别克', '雪佛兰', '凯迪拉克', '雷克萨斯',
    '英菲尼迪', '讴歌', '马自达', '斯巴鲁', '三菱', '现代', '起亚', '双龙',
    'MINI', 'Jeep', '特斯拉', '理想', '蔚来', '小鹏', '问界', '方程豹',
    '轿车', 'SUV', '越野车', 'MPV', '皮卡', '跑车', '新能源车', '电车', '混动',
    'VIN', '车架号', '年份', '排量', '手自一体', '自动', '手动',
})


# 剥一行里的 VIN/OE/纯数字/品牌车型，剩下的就是可能的配件名片段。
# 先做空格归一化（"264 200 3201" → "2642003201"），否则带空格的号码会残留
# 导致 _has_part_text_in_window 误判（号码数字被当成配件名的一部分）。
def _strip_noise_line(line: str) -> str:
    # 先归一化空格分隔的数字片段
    cur = normalize_spaced_digits(line)
    # 再剥离各类号码模式
    for pat in (_STRIP_VIN_RE, _STRIP_OEM_PREFIX_RE, _STRIP_OEM_DIGITS_RE):
        cur = pat.sub(' ', cur)
    # 剥品牌车型词
    for w in sorted(_BRAND_CAR_WORDS, key=len, reverse=True):
        cur = re.sub(re.escape(w), ' ', cur, flags=re.IGNORECASE)
    # 剥 ★数字、①②③、序号前缀等
    cur = re.sub(r'^[\s]*[★☆]?[\s]*\d{1,2}[\s]*[、\.．]\s*', '', cur)
    cur = re.sub(r'[①②③④⑤⑥⑦⑧⑨⑩]+', ' ', cur)
    # 剥括号里的内容（通常是号码）
    cur = re.sub(r'[（(][^)）]*[)）]', ' ', cur)
    return cur.strip()


def _has_part_text_in_window(messages, focus_ids) -> bool:
    """窗口里有没有"像配件名的中文短词"（后缀表漏的缩写）。

    做法：对 focus 消息的每行 → 剥 VIN/OE/品牌车型 → 看剩下的
    是否包含 2-4 个连续中文字符（"前减震"3字、"打气泵"3字 都是典型配件缩写）。
    """
    for m in messages:
        if m.id not in focus_ids:
            continue
        from backend.models.message import Message
        if m.direction != Message.DIR_IN or m.msg_type != Message.MSG_TEXT:
            continue
        for raw_line in (m.content or "").splitlines():
            cleaned = _strip_noise_line(raw_line)
            # 找 2-4 个连续中文字符
            m = re.search(r'[\u4e00-\u9fa5]{2,4}', cleaned)
            if m:
                return True
    return False


def _filter_focus_by_time(new_msgs) -> set:
    """new_msgs → focus_ids：只保留时间窗口内的 IN 消息。

    问题：窗口拉 10 条时，如果客户停了几天又回来发新询价，那几天前没被分析过的
    旧 IN 消息也会落在 new_msgs 里（id > last_analyzed_msg_id），被当成新询价融合
    进当前回复。

    过滤规则：
      - IN 消息：create_time 距最新 IN 消息 ≤ NEW_MSG_FOCUS_WINDOW_MINUTES 才进 focus
      - OUT 消息：不进 focus（配件只从客户消息提）
      - 如果所有 IN 消息都被过滤掉（只剩陈旧 IN 或只有 OUT），focus_ids 为空集

    进度条仍然推进到 new_msgs 最大值——陈旧消息标记"已看过"，不会再被重提。
    """
    from backend.models.message import Message

    # 找最新 IN 消息的 create_time 作为锚点
    in_msgs = [m for m in new_msgs if m.direction == Message.DIR_IN]
    if not in_msgs:
        return set()

    anchor_time = max(m.create_time for m in in_msgs)
    cutoff = anchor_time - timedelta(minutes=NEW_MSG_FOCUS_WINDOW_MINUTES)

    focus = set()
    skipped = 0
    for m in in_msgs:
        if m.create_time >= cutoff:
            focus.add(m.id)
        else:
            skipped += 1

    if skipped:
        log.info(
            "focus 时间过滤 conv_msgs=%d anchor=%s cutoff=%s 保留=%d 跳过=%d（陈旧 IN 消息）",
            len(in_msgs), anchor_time, cutoff, len(focus), skipped,
        )
    return focus


def analyze_conversation(conversation_id):
    """拉窗口 → 增量切分 → 普通识别 → AI 兜底 → 分流落表。调用方需持有 app_context。

    增量语义（2026-11-19 V2）：
    - conv.last_analyzed_msg_id 是"已处理到哪条消息"的进度条
    - 拉 10 条 → 按进度条切 (context_msgs, new_msgs)
    - 无 new_msgs → 直接跳过（没新消息）
    - 触发条件只看 new_msgs
    - rule_extract 传 focus=new_msgs 的 id（配件/号码只从新消息提）
    - AI 的 chat_content 加【历史】【新询价】标签 + 系统提示
    - 分析完成 → 进度条更新到 new_msgs 里最大的 id
    """
    conv = Conversation.query.filter_by(id=conversation_id, deleted_at=None).first()
    if conv is None:
        return
    cfg = merged_config(conv.openid)

    # 时间闸门：只拉 AI 开启时间之后的消息（闸门之前的历史消息不再参与分析）
    gate_dt = cfg.get("ai_enabled_at_dt")
    messages = fetch_recent_messages(conversation_id, min_time=gate_dt)
    if not messages:
        return

    # 增量切分
    context_msgs, new_msgs = split_by_progress(messages, conv.last_analyzed_msg_id)

    # 没有新消息 → 更新进度条到窗口里最大的 id，避免重复分析旧消息
    if not new_msgs:
        max_id = max(m.id for m in messages)
        if conv.last_analyzed_msg_id is None or max_id > conv.last_analyzed_msg_id:
            conv.last_analyzed_msg_id = max_id
            from backend.extensions import db
            db.session.commit()
        return

    # 触发条件只看 new_msgs
    if not should_trigger(new_msgs):
        # 不触发也推进进度条（这些消息已经看过了，以后别再重提）
        conv.last_analyzed_msg_id = max(m.id for m in new_msgs)
        from backend.extensions import db
        db.session.commit()
        return

    focus_ids = _filter_focus_by_time(new_msgs)

    # Step 1：普通识别（传 focus_ids，配件/号码只从新消息提，VIN 全窗口扫）
    scenes = rule_extract(messages, focus_msg_ids=focus_ids)

    # 层 1 修复（2026-11-20）：空壳 scene 检测
    # 普通识别产出了 scene，但 part_name 全 None（后缀表漏了配件名）
    # 且窗口里有中文配件缩写 → 扔掉空壳，让 Step 2 AI 兜底接管
    if _all_scenes_shell(scenes) and _has_part_text_in_window(messages, focus_ids):
        log.info(
            "普通识别产出空壳 scene（part_name 全 None），强制走 AI 兜底 conv=%s",
            conversation_id,
        )
        scenes = []  # 清空后 Step 2 的 if not scenes 自然触发

    # Step 2：普通识别没覆盖 → AI 兜底
    if not scenes:
        chat_content = build_chat_content(
            messages, focus_msg_ids=focus_ids, include_hint=True,
        )
        if not build_empty_check(chat_content):
            # 窗口内无文本，更新进度条后退出
            conv.last_analyzed_msg_id = max(m.id for m in new_msgs)
            from backend.extensions import db
            db.session.commit()
            return
        data = qq_client.extract_parts(chat_content)
        scenes = parse_scenarios(data)

    if not scenes:
        # 无论如何推进进度条，避免历史消息反复被分析
        conv.last_analyzed_msg_id = max(m.id for m in new_msgs)
        from backend.extensions import db
        db.session.commit()
        return

    rows = []
    try:
        rows = dispatch(conversation_id, scenes, cfg["parts_blacklist"])
    except Exception as e:
        log.exception("dispatch 异常 conv=%s: %s", conversation_id, e)
        # 哪怕 dispatch 挂了也要推进进度条，不然下次重跑还是挂（死循环）
        conv.last_analyzed_msg_id = max(m.id for m in new_msgs)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        return

    # 更新进度条（dispatch 成功才推进，失败了下次可以重跑）
    conv.last_analyzed_msg_id = max(m.id for m in new_msgs)
    from backend.extensions import db
    db.session.commit()

    pending = [r for r in rows if r.status == QuoteInquiry.ST_PENDING]
    if pending:
        # 阶段 4：待报价行立即算价回写 price_json（异常内部兜底，不影响分析流程）
        from backend.services.quote_pricing import price_inquiries

        price_inquiries(pending)
        # 阶段 5：算价后仍 pending 的行自动发送（quote_mode=auto 才发，preview 留人工）
        from backend.services.quote_sender import auto_send_pending

        auto_send_pending([r for r in pending if r.status == QuoteInquiry.ST_PENDING])
    log.info(
        "自动报价分析 conv=%s 场景=%d 状态=%s", conversation_id, len(scenes),
        [QuoteInquiry.STATUS_LABELS.get(r.status) for r in rows],
    )
