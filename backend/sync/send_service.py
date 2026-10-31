"""发送消息编排：先落库再下发，最终结果由 confirm_worker 轮询收尾。

流程（已确认的《发送消息闭环》流程图）：
客户端 POST → 写 message(发送中) + send_task(待下发，带 uuid)
  → 调中间方 post_xxx → 成功：task=已下发
                      → 失败：task=失败 + message=失败，抛 SendDispatchError
"""
from datetime import datetime
from uuid import uuid4

from flask import abort

from backend.adapter import sender as middle_sender
from backend.extensions import db
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.models.send_task import SendTask
from backend.sync.message_sync import _short_summary  # 收发共用同一套摘要规则


class SendDispatchError(Exception):
    """向中间方下发失败（网络错误或接口返回 code != 0）。"""


def _text_params(to_wxid, content, p):
    return {"to_wxid": to_wxid, "content": content, "ats": p.get("ats", "")}


def _image_params(to_wxid, content, p):
    return {"to_wxid": to_wxid, "img_url": p.get("img_url", "")}


def _file_params(to_wxid, content, p):
    return {
        "to_wxid": to_wxid,
        "file_url": p.get("file_url", ""),
        "file_name": p.get("file_name", ""),
    }


def _video_params(to_wxid, content, p):
    return {
        "to_wxid": to_wxid,
        "video_url": p.get("video_url", ""),
        "thumb_url": p.get("thumb_url", ""),
        "video_duration": p.get("video_duration", 0),
    }


def _link_params(to_wxid, content, p):
    return {
        "to_wxid": to_wxid,
        "title": p.get("title", ""),
        "desc": p.get("desc", ""),
        "link_url": p.get("link_url", ""),
        "thumb_url": p.get("thumb_url", ""),
    }


# msg_type → (中间方 action, 下发函数名, 参数拼装函数)
# 下发函数名在调用时经 getattr 查找，方便单测 mock 替换
_DISPATCH = {
    Message.MSG_TEXT: ("post_text_message", "post_text", _text_params),
    Message.MSG_IMAGE: ("post_image_message", "post_image", _image_params),
    Message.MSG_FILE: ("post_file_message", "post_file", _file_params),
    Message.MSG_VIDEO: ("post_video_message", "post_video", _video_params),
    Message.MSG_LINK: ("post_link_message", "post_link", _link_params),
}

# 非文本消息的摘要字段：content 为空时从 payload 里取这个字段当摘要
_DISPLAY_FALLBACK = {
    Message.MSG_IMAGE: "img_url",
    Message.MSG_FILE: "file_name",
    Message.MSG_VIDEO: "video_url",
    Message.MSG_LINK: "title",
}


def _get_conversation(conversation_id):
    """软删除过滤：删过的会话当不存在。"""
    conv = db.session.get(Conversation, conversation_id)
    if conv is not None and conv.deleted_at is not None:
        return None
    return conv


def _display_content(msg_type, content, payload):
    """消息摘要：文本用原文，其他类型取主字段（文件名/标题等）。"""
    if content:
        return content
    key = _DISPLAY_FALLBACK.get(msg_type)
    return (payload or {}).get(key, "")


def send_message(conversation_id, msg_type, content, payload):
    """发消息主流程，返回写库后的 message。

    下发成功时消息保持"发送中"，等轮询确认后变已发送/失败；
    下发本身失败（网络错误等）则直接标失败并抛 SendDispatchError。
    """
    payload = payload or {}
    conv = _get_conversation(conversation_id)
    if conv is None:
        abort(404, description="会话不存在")
    entry = _DISPATCH.get(msg_type)
    if entry is None:
        abort(400, description="不支持的消息类型")
    action, fn_name, build_params = entry

    msg = Message(
        conversation_id=conv.id,
        msg_type=msg_type,
        direction=Message.DIR_OUT,
        content=_display_content(msg_type, content, payload),
        payload=payload,
        status=Message.ST_SENDING,
    )
    task = SendTask(uuid=str(uuid4()), action=action, status=SendTask.ST_PENDING)
    db.session.add_all([msg, task])
    db.session.flush()  # 拿到自增 id
    task.message_id = msg.id

    task.request_payload = build_params(conv.wxid, content, payload)
    db.session.flush()

    try:
        post_fn = getattr(middle_sender, fn_name)
        post_fn(uuid=task.uuid, openid=conv.openid or "", **task.request_payload)
        task.status = SendTask.ST_DISPATCHED
    except Exception as exc:
        task.status = SendTask.ST_FAILED
        msg.status = Message.ST_FAILED
        db.session.commit()
        raise SendDispatchError(str(exc)) from exc

    # 下发成功才刷新会话摘要（失败时预览不动，避免误导已发出）
    conv.last_msg = _short_summary(msg_type, content)
    conv.last_msg_at = datetime.now()

    db.session.commit()
    return msg
