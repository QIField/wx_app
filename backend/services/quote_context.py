"""询价上下文组装：拉最近 N 条消息 → 拼服务方 chat_content 数组。

组装规则（防切割，docs/auto-quote-plan.md 阶段 2）：
- 最近 10 条，客户消息与客服消息都带（服务方靠客服回复算 is_replied）
- 文本：`YYYY-MM-DD HH:mm:ss【昵称】：内容` 整条进出，不按字数切
- 图片/语音/文件/视频：无公网直链路由，V1 只带占位备注条目（媒体直链阶段 5 前补）
- 引用消息取摘要前 80 字；业务端合并转发卡片跳过；发送失败的消息跳过
"""
from backend.models.message import Message

WINDOW_SIZE = 10

_PLACEHOLDER = {
    Message.MSG_IMAGE: "发送了一张图片",
    Message.MSG_VOICE: "发送了一条语音",
    Message.MSG_FILE: "发送了一个文件",
    Message.MSG_VIDEO: "发送了一段视频",
    Message.MSG_EMOJI: "发送了一个表情",
}


def fetch_recent_messages(conversation_id, limit=WINDOW_SIZE):
    """该会话最近 limit 条消息，返回正序（旧→新）。"""
    rows = (
        Message.query.filter(
            Message.conversation_id == conversation_id, Message.deleted_at.is_(None),
        )
        .order_by(Message.id.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(rows))


def build_chat_content(messages):
    """消息行 → chat_content 数组（服务方 input_text/input_image 结构）。"""
    out = []
    for m in messages:
        if m.direction == Message.DIR_OUT and m.status == Message.ST_FAILED:
            continue  # 没发出去的消息不进上下文，AI 看见会困惑
        name = m.sender_name or m.sender_wxid or "未知"
        when = m.create_time.strftime("%Y-%m-%d %H:%M:%S")
        if m.msg_type == Message.MSG_TEXT:
            out.append({"type": "input_text", "text": f"{when}【{name}】：{m.content or ''}"})
        elif m.msg_type == Message.MSG_QUOTE:
            text = (m.content or "")[:80]
            out.append({"type": "input_text", "text": f"{when}【{name}】(引用)：{text}"})
        elif m.msg_type in _PLACEHOLDER:
            out.append({"type": "input_text", "text": f"{when}【{name}】{_PLACEHOLDER[m.msg_type]}"})
        # MSG_FORWARD（业务端卡片）与其余未知类型跳过
    return out


def build_empty_check(chat_content):
    """无任何文本条目时跳过本次分析（纯图片占位场景 V1 无法识别）。"""
    return any(item.get("type") == "input_text" for item in chat_content)
