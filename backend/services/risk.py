"""接口限流 + 登录失败锁定的唯一入口（无 Redis 版）。

为什么不用 Redis：
- 当前 app.run 单进程启动，进程内存里的计数全局有效；
- 未来换多 worker（gunicorn）时，只需把 _HITS / _LOGIN_FAILS 换成 Redis 结构，
  对外函数签名全部不变，调用方无需改动。

存储结构用「滑动窗口」：每个 key 保存窗口内的命中时间点，
只保留窗口内的数据，内存占用 = 活跃 key 数 × 窗口上限次数，不会无限增长。
"""
import threading
import time
from collections import deque

from backend.services.access_log import client_ip

_LOCK = threading.Lock()
_HITS = {}  # 通用限流桶：key -> deque[命中时间]
_LOGIN_FAILS = {}  # 登录失败桶：key -> deque[失败时间]

_RATE_WINDOW_SECONDS = 60  # 限流统一按「每分钟」统计
_SWEEP_KEEP_SECONDS = 3600  # 清理任务只保留最近 1 小时活跃过的 key


def _prune(q, now, window):
    """丢掉窗口外的旧时间点（队头最老，逐个弹出即可）。"""
    while q and now - q[0] > window:
        q.popleft()


def _hit(key, limit, window):
    """滑动窗口核心：窗口内已达上限返回 (False, 需等待秒数)，否则记一次并放行。

    O(1) 均摊：每个时间点只入队一次、出队一次。
    """
    now = time.monotonic()
    with _LOCK:
        q = _HITS.setdefault(key, deque())
        _prune(q, now, window)
        if len(q) >= limit:
            return False, int(window - (now - q[0])) + 1
        q.append(now)
        return True, 0


def login_key(username):
    """登录锁定的维度：IP + 账号。

    只按 IP 会误伤同一出口 IP 的其他同事；只按账号则攻击者可换 IP 继续撞库。
    """
    return f"{client_ip()}::{username}"


def login_blocked(key):
    """登录前只读判断：已锁定返回剩余秒数，否则 0（不计数、不改状态）。"""
    from backend.config import LOGIN_MAX_FAILS, LOGIN_WINDOW_SECONDS

    now = time.monotonic()
    with _LOCK:
        q = _LOGIN_FAILS.get(key)
        if not q:
            return 0
        _prune(q, now, LOGIN_WINDOW_SECONDS)
        if len(q) < LOGIN_MAX_FAILS:
            return 0
        return int(LOGIN_WINDOW_SECONDS - (now - q[0])) + 1


def record_login_failure(key):
    """密码错误时调用：把本次失败打进窗口。只能由登录接口在失败分支调用。"""
    from backend.config import LOGIN_WINDOW_SECONDS

    now = time.monotonic()
    with _LOCK:
        q = _LOGIN_FAILS.setdefault(key, deque())
        _prune(q, now, LOGIN_WINDOW_SECONDS)
        q.append(now)


def reset_login(key):
    """登录成功后清零：避免历史失败把正常用户之后的登录挡住。"""
    with _LOCK:
        _LOGIN_FAILS.pop(key, None)


def check_request(path, method, ip):
    """接口限流唯一判断：返回 (是否放行, 剩余秒数)。

    分档依据「批量拉数据」的实际路径：
    - 媒体：单条最重、最容易被脚本循环拉取 → 最严
    - 消息/会话：翻页拉历史 → 中等
    - 其余接口 → 宽松
    """
    from backend.config import (
        API_LIMIT_PER_MINUTE,
        MESSAGES_LIMIT_PER_MINUTE,
        MEDIA_LIMIT_PER_MINUTE,
    )

    if method == "OPTIONS":
        return True, 0
    # 与 access_log 豁免清单保持一致：健康检查、WebSocket、静态资源不限流
    if path.startswith(("/api/health", "/ws", "/static/")):
        return True, 0
    if not path.startswith("/api/"):
        return True, 0

    # 注意顺序：/api/messages/<id>/media 同时含 "/messages"，必须先判媒体
    if "/media" in path:
        bucket, limit = "media", MEDIA_LIMIT_PER_MINUTE
    elif "/messages" in path:
        bucket, limit = "messages", MESSAGES_LIMIT_PER_MINUTE
    else:
        bucket, limit = "api", API_LIMIT_PER_MINUTE

    return _hit(f"{bucket}:{ip or 'unknown'}", limit, _RATE_WINDOW_SECONDS)


def sweep():
    """定时清理：删掉长时间没动静的 key，防止内存随历史 IP 缓慢增长。"""
    cutoff = time.monotonic() - _SWEEP_KEEP_SECONDS
    with _LOCK:
        for bucket in (_HITS, _LOGIN_FAILS):
            for key in [k for k, q in bucket.items() if not q or q[-1] < cutoff]:
                bucket.pop(key, None)


def reset():
    """清空全部计数：单测用（避免用例之间互相污染）。"""
    with _LOCK:
        _HITS.clear()
        _LOGIN_FAILS.clear()
