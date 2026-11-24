"""互斥控制插件 · 公共 API 入口。

用法（message_sync.py 的 broadcast_messages 中）：
    from backend.plugins.mutex_protocol import should_process
    if not should_process(conversation_id, openid=openid):
        continue
    on_new_message(conversation_id, ...)

设计原则：
- 插件任何异常 → 兜底返回 True（放行）→ 不阻断业务
- 没启用 → 默认放行 → 系统完全无感
- 按群聊 wxid 粒度互斥，单聊天然不需要

后端选择（init_app 自动探测）：
- 优先 Redis（高性能分布式锁）
- Redis 不可用 → 降级 DB 锁（用项目已有 SQLite/MySQL，零额外基础设施）
"""
from __future__ import annotations

import logging
import threading
from typing import Optional

from .lock import LockManager
from .monitor import DeviceMonitor

log = logging.getLogger(__name__)

# ---------- 进程内单例（可被多个 openid 共享） ----------

# {device_id: DeviceMonitor}  —— 一个进程管理多台设备
_monitors: dict[str, DeviceMonitor] = {}
_init_lock = threading.Lock()

# 全局开关：未 init_app 或 init 时失败 → 所有 should_process 返回 True
_initialized = False
_lock_manager = None  # LockManager | DBLockManager | None
_backend = ""  # "redis" / "db" / ""


def init_app(app, *, backend: str = "auto", redis_client=None, db=None) -> None:
    """应用启动时调用：初始化锁管理器。

    db 后端必须传 db 对象，并且调用时必须有 app context ——
    _ensure_table() 在 context 内执行，engine 会被缓存，
    后续心跳线程从缓存 engine 拿连接，不再依赖 Flask app context。
    """
    global _initialized, _lock_manager, _backend

    candidates = []

    if backend in ("auto", "redis") and redis_client is not None:
        candidates.append(("redis", lambda: LockManager(redis_client)))

    if backend in ("auto", "db"):
        if db is None:
            try:
                from backend.extensions import db as _db
                db = _db
            except Exception:
                db = None
        if db is not None:
            from .db_lock import DBLockManager
            candidates.append(("db", lambda: DBLockManager(db)))

    for name, factory in candidates:
        try:
            mgr = factory()
            # DB 锁后端：第一次必须在 app context 内建表 + 抓 engine
            ensure_fn = getattr(mgr, "_ensure_table", None)
            if callable(ensure_fn):
                ensure_fn()
            _lock_manager = mgr
            _initialized = True
            _backend = name
            app.logger.info("🔐 MutexProtocol 已初始化 (backend=%s)", name)
            return
        except Exception as exc:
            app.logger.warning("🔐 MutexProtocol 后端 %s 初始化失败: %s", name, exc)

    app.logger.warning("🔐 MutexProtocol 所有后端不可用，降级为全放行")
    _initialized = False
    _lock_manager = None
    _backend = ""


def get_backend() -> str:
    """返回当前使用的后端名称（调试/日志用）。"""
    return _backend if _initialized else "disabled"


def _get_or_create_monitor(device_id: str) -> DeviceMonitor:
    """按 device_id 懒创建 DeviceMonitor（进程内单例）。"""
    with _init_lock:
        if device_id not in _monitors:
            _monitors[device_id] = DeviceMonitor(_lock_manager, device_id)
        return _monitors[device_id]


# ---------- 公共主入口 ----------

def should_process(conversation_id: int, openid: str) -> bool:
    """插件拦截主入口。

    Args:
        conversation_id: 会话 ID（群聊/单聊）
        openid: 设备 openid（哪个设备收到的消息）

    Returns:
        True  → 放行到业务逻辑（自动报价执行）
        False → 静默丢弃（Follower 设备）
    """
    # --- 快速放行 ---
    if not _initialized or _lock_manager is None:
        return True  # 插件没启用 → 放行

    if not openid:
        return True  # 没有设备身份 → 放行

    try:
        from backend.extensions import db
        from backend.models.conversation import Conversation

        conv = db.session.get(Conversation, conversation_id)
        if conv is None:
            return True  # 会话不存在，让下游自己处理

        # 只在群聊场景生效 —— 单聊天然只有一个设备参与
        if conv.chat_type != Conversation.CHAT_GROUP:
            return True

        group_wxid = conv.wxid
        monitor = _get_or_create_monitor(openid)

        # --- 快速路径：本地已知自己是 Leader 且心跳健康 ---
        if monitor.is_leader(group_wxid) and monitor.heartbeat_ok(group_wxid):
            return True

        # --- 查 Redis 锁 ---
        lock = _lock_manager.peek(group_wxid)

        if lock is not None:
            if lock.get("owner") == openid:
                # 锁还是自己的 —— 兜底放行
                return True

            # 别人有锁，对比任期号
            local_term = monitor.get_term(group_wxid)
            remote_term = int(lock.get("term", 0))
            if remote_term > local_term:
                # 同步任期号 → 下次选举有正确基线
                with _init_lock:
                    pass  # term 在 monitor 内部维护，通过 promote 更新
            log.debug("should_process: follower 静默 group=%s device=%s owner=%s term=%d",
                      group_wxid[:20], openid[:12],
                      lock.get("owner", "?")[:12], remote_term)
            return False

        # --- 锁空 → 选举：抢锁 ---
        local_term = monitor.get_term(group_wxid)
        new_term = local_term + 1

        if _lock_manager.try_acquire(group_wxid, openid, new_term):
            monitor.promote(group_wxid, new_term)
            return True  # 🎉 当选

        # 抢锁失败 → 读 winner 同步状态
        winner = _lock_manager.peek(group_wxid)
        if winner:
            winner_term = int(winner.get("term", 0))
            winner_owner = winner.get("owner", "?")
            log.debug("should_process: 选举失败，winner=%s term=%d (local=%d) device=%s",
                      winner_owner[:12], winner_term, local_term, openid[:12])
            if winner_term > local_term:
                # 让 monitor 下次能看到最新 term
                with _init_lock:
                    pass  # promote 已经把 term 写进去了，follower 这边下次会重新抢锁
        return False

    except Exception as exc:
        # 任何异常都兜底放行 —— 插件不能阻断业务
        log.exception("MutexProtocol should_process 异常 (兜底放行): %s", exc)
        return True
