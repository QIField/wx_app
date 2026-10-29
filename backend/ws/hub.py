"""WebSocket hub：连接名单 + 广播（随 Flask 进程启动，全局一份）。

简单版：名单存本进程内存，单机部署够用；将来多机部署再换 Redis。
前端只收不发：每条连接一个队列，后台线程广播时往队列里放，
WS 线程循环取出来 send。连接断开靠下次 send 报错时清理。
"""
import json
from queue import Queue, Empty

from flask_sock import ConnectionClosed

from backend.extensions import sock

# 名单：每个元素是一个 Queue（一个客服浏览器一条）
_connects = []


@sock.route("/ws")
def ws_endpoint(ws):
    """一条客户端连接 = 一个循环：广播内容送到这个浏览器。"""
    q = Queue()
    _connects.append(q)
    try:
        while True:
            try:
                text = q.get(timeout=10)
            except Empty:
                # 定期探测：连接已断会在这里抛错，走 finally 清理
                ws.send('{"event":"ping"}')
                continue
            ws.send(text)
    except (ConnectionClosed, OSError, RuntimeError):
        pass
    finally:
        if q in _connects:
            _connects.remove(q)


def broadcast(event, data):
    """把一个事件推给所有连着的客服页面。

    event: 事件名（new_message / send_result）
    data:  事件内容（字典）
    """
    text = json.dumps({"event": event, "data": data}, ensure_ascii=False)
    for q in list(_connects):  # 拷贝一份，广播过程中名单可能变化
        q.put(text)


def connect_count():
    """当前连接数（健康检查/测试用）。"""
    return len(_connects)
