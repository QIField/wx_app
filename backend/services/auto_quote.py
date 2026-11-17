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
from backend.services.quote_context import (
    build_chat_content, build_empty_check, fetch_recent_messages,
)
from backend.services.quote_dispatch import dispatch, parse_scenarios

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
    try:
        with _app.app_context():
            analyze_conversation(conversation_id)
    except Exception:  # noqa: BLE001
        log.exception("自动报价分析失败 conv=%s", conversation_id)
    finally:
        from backend.extensions import db

        db.session.remove()


def analyze_conversation(conversation_id):
    """拉窗口 → 组装 → AI 分析 → 分流落表。调用方需持有 app_context。"""
    cfg = merged_config(0)
    messages = fetch_recent_messages(conversation_id)
    chat_content = build_chat_content(messages)
    if not build_empty_check(chat_content):
        return  # 窗口内无文本（纯图片占位），V1 不分析
    data = qq_client.extract_parts(chat_content)
    scenes = parse_scenarios(data)
    if not scenes:
        return
    rows = dispatch(conversation_id, scenes, cfg["parts_blacklist"])
    from backend.models.quote_inquiry import QuoteInquiry

    log.info(
        "自动报价分析 conv=%s 场景=%d 状态=%s", conversation_id, len(scenes),
        [QuoteInquiry.STATUS_LABELS.get(r.status) for r in rows],
    )
