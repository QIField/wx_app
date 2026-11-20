"""自动报价触发器（阶段 2 核心，docs/auto-quote-plan.md 定案版流程）。

  收到新消息 → 资格判定（契约 C：通讯录开关（群看群/单聊看用户）
              AND 全局 AI 执行开关 quote_config.ai_enabled）
  → 每会话 3s 去抖（新消息重置计时，等客户连发收齐）
  → 拉最近 10 条组装 chat_content → extract_parts_demand
  → 契约 B 状态机落表（quote_dispatch）。

触发器挂在消息同步链路里，任何异常只记日志，绝不影响收信。
定时器线程无 Flask 上下文，fire 时经 init_app 存入的 app 包 app_context。
"""
import logging
import threading

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

log = logging.getLogger(__name__)

ANALYZE_DELAY = 3.0  # 静默去抖：客户连发图+文字的间隔内不再触发

_app = None
_timers = {}
_lock = threading.Lock()
_timer_factory = threading.Timer  # 测试注入替身


def init_app(app):
    """由 create_app 调用：保存 app 引用供定时器线程包 app_context。"""
    global _app
    _app = app


# ---------- 资格判定（契约 C） ----------


def _remark_enabled(scope_type, wxid):
    row = ContactRemarkConfig.query.filter_by(
        scope_type=scope_type, target_wxid=wxid, deleted_at=None,
    ).first()
    return bool(row.auto_quote_enabled) if row else False


def is_eligible(conversation_id):
    """群会话只看群开关、单聊只看用户开关（群>用户），再 AND 全局执行开关。"""
    conv = Conversation.query.filter_by(id=conversation_id, deleted_at=None).first()
    if conv is None:
        return False
    scope = "group" if conv.chat_type == Conversation.CHAT_GROUP else "user"
    if not _remark_enabled(scope, conv.wxid):
        return False
    return bool(merged_config(0)["ai_enabled"])


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


def on_new_message(conversation_id):
    """消息同步钩子入口：资格不过直接跳过；过了就重置计时。"""
    try:
        if not is_eligible(conversation_id):
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
    cfg = merged_config(0)
    conv = Conversation.query.filter_by(id=conversation_id, deleted_at=None).first()
    if conv is None:
        return

    messages = fetch_recent_messages(conversation_id)
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

    focus_ids = {m.id for m in new_msgs}

    # Step 1：普通识别（传 focus_ids，配件/号码只从新消息提，VIN 全窗口扫）
    scenes = rule_extract(messages, focus_msg_ids=focus_ids)

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

    rows = dispatch(conversation_id, scenes, cfg["parts_blacklist"])

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
