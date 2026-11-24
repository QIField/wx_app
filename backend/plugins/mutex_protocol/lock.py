"""LockManager: 基于 Redis SET NX 的分布式互斥锁。

锁按群聊 wxid 粒度隔离（KEY = mutex:lock:{group_wxid}），
Value 是 JSON: {"owner": str, "term": int, "lease": int, "ts": int}。

term 是 fencing token：只升不降，所有操作带 term 校验，
防止脑裂恢复后旧 Leader 复活。
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

log = logging.getLogger(__name__)

LOCK_PREFIX = "mutex:lock:"
LOCK_TTL_SEC = 30


class LockManager:
    """分布式互斥锁管理器。"""

    def __init__(self, redis_client: Any):
        self._r = redis_client

    # ---------- 内部 ----------

    @staticmethod
    def _key(group_wxid: str) -> str:
        return f"{LOCK_PREFIX}{group_wxid}"

    @staticmethod
    def _encode(device_id: str, term: int) -> str:
        return json.dumps({
            "owner": device_id,
            "term": int(term),
            "lease": int(time.time()) + LOCK_TTL_SEC,
            "ts": int(time.time()),
        })

    @staticmethod
    def _decode(raw: bytes | str) -> Optional[dict]:
        if not raw:
            return None
        if isinstance(raw, bytes):
            try:
                raw = raw.decode("utf-8")
            except UnicodeDecodeError:
                return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    # ---------- 公共 API ----------

    def try_acquire(self, group_wxid: str, device_id: str, term: int) -> bool:
        """尝试获取锁（SET NX + EX）。

        term 是任期号，只升不降。
        """
        key = self._key(group_wxid)
        value = self._encode(device_id, term)
        try:
            ok = self._r.set(key, value, nx=True, ex=LOCK_TTL_SEC)
        except Exception:
            log.exception("🔒 try_acquire Redis 异常 group=%s", group_wxid[:20])
            return False
        if ok:
            log.info("🔒 抢锁成功 group=%s owner=%s term=%d",
                     group_wxid[:20], device_id, term)
        return bool(ok)

    def renew(self, group_wxid: str, device_id: str, term: int) -> bool:
        """Leader 续租：只有 owner 和 term 都匹配才延长 TTL。"""
        key = self._key(group_wxid)
        try:
            raw = self._r.get(key)
        except Exception:
            log.exception("续租 Redis 异常 group=%s", group_wxid[:20])
            return False

        data = self._decode(raw)
        if data is None:
            return False
        if data.get("owner") != device_id or int(data.get("term", -1)) != int(term):
            log.debug("续租拒绝 owner/term 不匹配 group=%s local=%s/%d remote=%s/%d",
                      group_wxid[:20], device_id, term,
                      data.get("owner"), data.get("term"))
            return False

        # 原锁还是自己的 → 重写 value 延长 TTL
        try:
            data["lease"] = int(time.time()) + LOCK_TTL_SEC
            data["ts"] = int(time.time())
            self._r.setex(key, LOCK_TTL_SEC, json.dumps(data))
        except Exception:
            log.exception("续租 setex 异常 group=%s", group_wxid[:20])
            return False
        return True

    def release(self, group_wxid: str, device_id: str, term: int) -> bool:
        """主动释放锁：只在 owner 和 term 都匹配时才删（避免删了别人的锁）。"""
        key = self._key(group_wxid)
        try:
            raw = self._r.get(key)
        except Exception:
            return False

        data = self._decode(raw)
        if data is None:
            return True  # 锁已不存在，释放也算成功
        if data.get("owner") != device_id or int(data.get("term", -1)) != int(term):
            log.warning("⚠️ 拒绝释放：锁已易主 group=%s local_term=%d remote_term=%d",
                        group_wxid[:20], term, data.get("term"))
            return False

        try:
            self._r.delete(key)
        except Exception:
            return False
        return True

    def peek(self, group_wxid: str) -> Optional[dict]:
        """读锁内容（不修改），失败返回 None。"""
        key = self._key(group_wxid)
        try:
            raw = self._r.get(key)
        except Exception:
            log.exception("peek Redis 异常 group=%s", group_wxid[:20])
            return None
        return self._decode(raw)
