"""同步预下载：新媒体消息入库后立刻把媒体拉回本地缓存。

背景（2026-10-31 日志复盘）：原先前端打开会话才按需下载，页面几十个
媒体同时并发，撞中间方「该微信正在下载的任务已达上限」限流。
改为同步阶段逐条串行下载、图片只拉常规规格（img_type=2），
前端打开会话直接命中缓存；按需下载降级为兜底。

单轮限时 BUDGET_SECONDS，防止批量媒体拖住收消息轮询（间隔 2 秒）；
超出的留给下一轮，缓存命中检查保证不重复下载；
单条失败只记运行日志不中断，不影响同步主流程。
"""
import time

from flask import current_app

from backend.adapter.client import MiddleApiError
from backend.models.message import Message
from backend.services import media_fetch

# 单轮预下载预算（秒）：收消息轮询间隔 2 秒，不能被批量下载长期占用
BUDGET_SECONDS = 30


def predownload_media(pushed):
    """串行预下载本轮新入库的媒体消息；单条失败跳过继续。pushed 为空直接返回。"""
    media_ids = [p["message_id"] for p in pushed
                 if p["msg_type"] in media_fetch.DOWNLOAD_ACTION]
    if not media_ids:
        return

    rows = Message.query.filter(Message.id.in_(media_ids)).all()
    deadline = time.monotonic() + BUDGET_SECONDS
    for msg in rows:
        if time.monotonic() > deadline:  # 预算用完，剩余的下轮靠缓存查重续传
            return
        try:
            media_fetch.fetch_and_cache(msg)  # 图片默认 img_type=2，只此一个规格
        except MiddleApiError as exc:
            current_app.logger.warning("媒体预下载失败 消息 %s：%s", msg.id, exc)
