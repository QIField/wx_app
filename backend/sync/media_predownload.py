"""同步后置媒体预下载：新媒体消息入库后把媒体拉回本地缓存。

背景（2026-10-31 日志复盘）：原先前端打开会话才按需下载，页面几十个
媒体同时并发，撞中间方「该微信正在下载的任务已达上限」限流。
改为后台单线程串行下载：图片按 1→2→3 档降级，成功即停，每条只存一张；
其余媒体拉单个文件。

2026-11-07 调整：原先在 sync_once 里同步调用，单轮预算 30 秒且图片单张
要 2~5 秒，会把收消息轮询整轮卡住（延迟从 2 秒变成 30+ 秒）。
改为「入队 + 后台单线程消费」：收消息立即返回，媒体慢慢下，前端打开会话
命中缓存；未命中的仍由按需下载兜底。单轮预算只限制后台线程连续占用。
"""
import threading
import time

from flask import current_app

from backend.adapter.client import MiddleApiError
from backend.extensions import db
from backend.models.message import Message
from backend.services import media_fetch

# 后台线程单轮连续下载预算（秒）：超出的留到下一批，缓存命中检查保证不重复下载
BUDGET_SECONDS = 30

_PENDING_IDS: list[int] = []
_PENDING_LOCK = threading.Lock()
_WORKER_RUNNING = False


def enqueue_predownload(pushed):
    """同步阶段调用：只入队，立刻返回，不阻塞 2 秒一轮的收消息。"""
    ids = [p["message_id"] for p in pushed if p["msg_type"] in media_fetch.DOWNLOAD_ACTION]
    if not ids:
        return
    global _WORKER_RUNNING
    with _PENDING_LOCK:
        _PENDING_IDS.extend(ids)
        if _WORKER_RUNNING:
            return
        _WORKER_RUNNING = True
    app = current_app._get_current_object()
    threading.Thread(target=_worker, args=(app,), daemon=True, name="media-predownload").start()


def _worker(app):
    """后台唯一消费者：串行下载，避免并发触发中间方下载任务上限。"""
    global _WORKER_RUNNING
    with app.app_context():
        try:
            while True:
                with _PENDING_LOCK:
                    batch = list(_PENDING_IDS)
                    _PENDING_IDS.clear()
                if batch:
                    predownload_ids(batch)
                    continue
                # 队列空时在锁内让出 running 标记：此时若有人入队会看到 False 并起新线程
                with _PENDING_LOCK:
                    if _PENDING_IDS:
                        continue
                    _WORKER_RUNNING = False
                    return
        finally:
            db.session.remove()  # 必须在 app context 内释放线程独立的 session
            with _PENDING_LOCK:   # 异常退出时也要让出标记，否则新任务永远排不进来
                _WORKER_RUNNING = False


def predownload_media(pushed):
    """同步版入口（测试/手动补下载用）：直接串行下载本轮新入库媒体。"""
    ids = [p["message_id"] for p in pushed if p["msg_type"] in media_fetch.DOWNLOAD_ACTION]
    if ids:
        predownload_ids(ids)


def predownload_ids(message_ids):
    """串行预下载给定消息的媒体；单条失败跳过继续。"""
    rows = Message.query.filter(Message.id.in_(message_ids)).all()
    deadline = time.monotonic() + BUDGET_SECONDS
    for msg in rows:
        if time.monotonic() > deadline:  # 预算用完，剩余的下批靠缓存查重续传
            return
        try:
            # 图片按 1→2→3 档降级，成功即停（每条只存一张）
            media_fetch.fetch_and_cache(msg)
        except MiddleApiError as exc:
            current_app.logger.warning("媒体预下载失败 消息 %s：%s", msg.id, exc)
