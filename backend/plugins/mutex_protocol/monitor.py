"""DeviceMonitor: 心跳续租 + 本地状态管理。

设计要点：
1. 每个设备（openid）可以管理多个群的互斥状态
2. 心跳线程每个群一个（被 promote 后启动，demote 后退出）
3. 连续 MAX_FAILURES 次续租失败 → 主动降级（防假 Leader 脑裂）
4. 异常只记日志，不向上冒泡
"""
from __future__ import annotations

import logging
import threading
import time

log = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = 10  # 心跳周期（秒）
MAX_FAILURES = 3         # 连续失败上限 → 触发降级


class DeviceMonitor:
    """单台设备的互斥状态监控器。"""

    def __init__(self, lock_manager, device_id: str):
        self._lock = lock_manager
        self._device_id = device_id

        # {group_wxid: {"leader": bool, "term": int, "failures": int}}
        self._groups: dict[str, dict] = {}
        self._lock_state = threading.Lock()

    # ---------- 公共：角色切换 ----------

    def promote(self, group_wxid: str, term: int) -> None:
        """当选 Leader：更新状态 + 启动心跳线程。"""
        with self._lock_state:
            state = self._groups.setdefault(group_wxid, {
                "leader": False, "term": 0, "failures": 0,
                "thread": None, "stop": False,
            })
            state["leader"] = True
            state["term"] = int(term)
            state["failures"] = 0

            if state["thread"] is None:
                state["stop"] = False
                t = threading.Thread(
                    target=self._heartbeat_loop,
                    args=(group_wxid,),
                    name=f"hb-{group_wxid[:12]}",
                    daemon=True,
                )
                state["thread"] = t
                t.start()

        log.info("👑 promote leader device=%s group=%s term=%d",
                 self._device_id, group_wxid[:20], term)

    def demote(self, group_wxid: str, reason: str = "") -> None:
        """降级为 Follower：停心跳、清 leader 标记。"""
        thread = None
        with self._lock_state:
            state = self._groups.get(group_wxid)
            if not state:
                return
            state["leader"] = False
            state["failures"] = 0
            state["stop"] = True
            thread = state.get("thread")

        if thread and thread.is_alive():
            # 心跳线程会自己读 stop 退出，不 join 避免阻塞
            pass

        log.info("⚙️  demote device=%s group=%s reason=%s",
                 self._device_id, group_wxid[:20], reason or "-")

    def shutdown(self) -> None:
        """进程退出前清理：所有群 demote + 主动释放 Redis 锁。"""
        with self._lock_state:
            items = list(self._groups.items())
            for group_wxid, state in items:
                if state["leader"]:
                    try:
                        self._lock.release(group_wxid, self._device_id, state["term"])
                    except Exception:
                        log.exception("shutdown release 异常 group=%s", group_wxid[:20])
                    state["stop"] = True
                    state["leader"] = False

    # ---------- 公共：状态查询 ----------

    def is_leader(self, group_wxid: str) -> bool:
        with self._lock_state:
            state = self._groups.get(group_wxid)
            return bool(state and state["leader"])

    def heartbeat_ok(self, group_wxid: str) -> bool:
        """心跳是否健康（failures < MAX_FAILURES）。"""
        with self._lock_state:
            state = self._groups.get(group_wxid)
            return bool(state and state["failures"] < MAX_FAILURES)

    def get_term(self, group_wxid: str) -> int:
        with self._lock_state:
            state = self._groups.get(group_wxid)
            return state["term"] if state else 0

    # ---------- 内部：心跳循环 ----------

    def _heartbeat_loop(self, group_wxid: str) -> None:
        """心跳线程入口：循环调用 lock.renew()。"""
        # 每轮先等一个间隔，再检查 stop 标记
        while True:
            # 等间隔（用小步循环读 stop，让外部 demote 能及时打断）
            for _ in range(HEARTBEAT_INTERVAL * 10):
                time.sleep(0.1)
                with self._lock_state:
                    state = self._groups.get(group_wxid)
                    if not state or state["stop"] or not state["leader"]:
                        return

            # 读当前 term（持锁读 → 避免和 promote 竞态）
            with self._lock_state:
                state = self._groups.get(group_wxid)
                if not state or state["stop"] or not state["leader"]:
                    return
                term = state["term"]

            # 续租
            try:
                ok = self._lock.renew(group_wxid, self._device_id, term)
            except Exception:
                log.exception("💥 心跳异常 group=%s", group_wxid[:20])
                ok = False

            with self._lock_state:
                state = self._groups.get(group_wxid)
                if not state:
                    return
                if ok:
                    state["failures"] = 0
                else:
                    state["failures"] += 1
                    n = state["failures"]
                    if n >= MAX_FAILURES:
                        log.error("🚨 心跳连续失败 %d 次，主动降级 device=%s group=%s",
                                  n, self._device_id, group_wxid[:20])
                        state["leader"] = False
                        state["stop"] = True
                        return
