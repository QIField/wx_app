"""MutexProtocol 互斥插件冒烟测试：LockManager + DeviceMonitor 核心逻辑。

使用 unittest.mock 模拟 Redis —— 不需要真的装 redis 包或起 Redis 服务。
"""
import json
import threading
import time
from unittest.mock import MagicMock

from backend.plugins.mutex_protocol.lock import LockManager, LOCK_TTL_SEC
from backend.plugins.mutex_protocol.monitor import DeviceMonitor


# ---------- Mock Redis ----------

class MockRedis:
    """最小实现 Redis dict-like SET/GET/DEL/SETEX 语义。"""
    def __init__(self):
        self._store = {}
        self._ttl = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self._store:
            return False
        self._store[key] = value
        if ex:
            self._ttl[key] = time.time() + ex
        return True

    def setex(self, key, ttl, value):
        self._store[key] = value
        self._ttl[key] = time.time() + ttl

    def get(self, key):
        exp = self._ttl.get(key)
        if exp and time.time() > exp:
            self._store.pop(key, None)
            self._ttl.pop(key, None)
            return None
        return self._store.get(key)

    def delete(self, key):
        self._store.pop(key, None)
        self._ttl.pop(key, None)
        return 1


def test_lock_try_acquire_basic():
    """UT-LOCK-001: SET NX 成功获取锁。"""
    r = MockRedis()
    lm = LockManager(r)
    ok = lm.try_acquire("grpA", "dev_01", 1)
    assert ok is True
    raw = r.get("mutex:lock:grpA")
    data = json.loads(raw)
    assert data["owner"] == "dev_01"
    assert data["term"] == 1


def test_lock_try_acquire_conflict():
    """UT-LOCK-002: 锁被别人持有 → 抢锁失败。"""
    r = MockRedis()
    lm = LockManager(r)
    assert lm.try_acquire("grpA", "dev_01", 1) is True
    assert lm.try_acquire("grpA", "dev_02", 2) is False
    # 原锁不变
    data = json.loads(r.get("mutex:lock:grpA"))
    assert data["owner"] == "dev_01"


def test_lock_renew_success():
    """UT-LOCK-003: 自己能续租自己的锁。"""
    r = MockRedis()
    lm = LockManager(r)
    lm.try_acquire("grpA", "dev_01", 1)
    # 过一点时间后续租
    time.sleep(0.01)
    ok = lm.renew("grpA", "dev_01", 1)
    assert ok is True


def test_lock_renew_wrong_owner():
    """UT-LOCK-004: 别人的锁不能续租。"""
    r = MockRedis()
    lm = LockManager(r)
    lm.try_acquire("grpA", "dev_01", 1)
    assert lm.renew("grpA", "dev_02", 1) is False


def test_lock_renew_wrong_term():
    """UT-LOCK-005: term 不匹配不能续租（fencing token）。"""
    r = MockRedis()
    lm = LockManager(r)
    lm.try_acquire("grpA", "dev_01", 5)
    assert lm.renew("grpA", "dev_01", 4) is False  # 落后一期


def test_lock_release_wrong_owner():
    """释放别人的锁 → 拒绝。"""
    r = MockRedis()
    lm = LockManager(r)
    lm.try_acquire("grpA", "dev_01", 1)
    assert lm.release("grpA", "dev_02", 1) is False


def test_lock_release_success():
    """自己释放自己的锁 → 删除。"""
    r = MockRedis()
    lm = LockManager(r)
    lm.try_acquire("grpA", "dev_01", 1)
    assert lm.release("grpA", "dev_01", 1) is True
    assert r.get("mutex:lock:grpA") is None


def test_lock_peek():
    """peek 读锁内容。"""
    r = MockRedis()
    lm = LockManager(r)
    assert lm.peek("grpA") is None
    lm.try_acquire("grpA", "dev_01", 3)
    data = lm.peek("grpA")
    assert data["owner"] == "dev_01"
    assert data["term"] == 3


def test_monitor_promote_and_is_leader():
    """DeviceMonitor promote 后 is_leader 返回 True。"""
    r = MockRedis()
    lm = LockManager(r)
    mon = DeviceMonitor(lm, "dev_01")
    assert mon.is_leader("grpA") is False
    mon.promote("grpA", term=1)
    assert mon.is_leader("grpA") is True
    assert mon.heartbeat_ok("grpA") is True


def test_monitor_demote():
    """demote 后 is_leader 返回 False。"""
    r = MockRedis()
    lm = LockManager(r)
    mon = DeviceMonitor(lm, "dev_01")
    mon.promote("grpA", term=1)
    mon.demote("grpA", reason="test")
    assert mon.is_leader("grpA") is False


def test_multiple_groups_independent():
    """DeviceMonitor 可以同时管理多个群，互不干扰。"""
    r = MockRedis()
    lm = LockManager(r)
    mon = DeviceMonitor(lm, "dev_01")
    mon.promote("grpA", term=1)
    mon.promote("grpB", term=1)
    assert mon.is_leader("grpA") is True
    assert mon.is_leader("grpB") is True
    mon.demote("grpA")
    assert mon.is_leader("grpA") is False
    assert mon.is_leader("grpB") is True


if __name__ == "__main__":
    import sys
    import traceback

    tests = [v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
            print(f"  ✅ {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  ❌ {t.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"  💥 {t.__name__}: {type(e).__name__}: {e}")
            traceback.print_exc()
    print(f"\n结果: {passed} passed, {failed} failed / {len(tests)} total")
    sys.exit(0 if failed == 0 else 1)
