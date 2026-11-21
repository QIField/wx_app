"""询价上下文组装：拉最近 N 条消息 → 拼服务方 chat_content 数组。

增量分析语义（2026-11-19 V2）：
- 每个会话有 last_analyzed_msg_id（进度条），标记"已分析到哪条消息"
- 每次拉最近 10 条 → 按进度条切分：
    context = msg.id <= last_analyzed_msg_id（历史上下文，提供 VIN 关联）
    new     = msg.id >  last_analyzed_msg_id（本次新消息，真正要分析的）
- 全部 10 条都喂给 AI / rule_extract，但：
    AI：靠【历史】【新询价】标签 + 系统指令区分
    rule_extract：focus 列表硬性区分（配件/号码只从 focus 提取，VIN 全窗口提取）

组装规则（docs/auto-quote-plan.md 阶段 2；署名契约按 ai_api/extract_parts_demand 接口文档）：
- 客服（发出）消息统一署名【我回复】；客户消息用昵称，缺省退 wxid
- 图片/语音/文件/视频：无公网直链路由，V1 不传媒体条目，只带
  `【系统备注】：上一条是【发送者】发的图片` 样式的说明条目
"""
from backend.models.message import Message

WINDOW_SIZE = 10

_MEDIA_NOTE = {
    Message.MSG_IMAGE: "发的图片",
    Message.MSG_VOICE: "发的语音",
    Message.MSG_FILE: "发的文件",
    Message.MSG_VIDEO: "发的视频",
    Message.MSG_EMOJI: "发的表情",
}

_AI_HINT = (
    "【系统提示】以下聊天记录已按【历史】和【新询价】标记。"
    "请只从【新询价】里提取配件（part_name/oem_no）和 VIN。"
    "【历史】标记的消息已经处理过，不要再提取配件。"
    "历史消息里的 VIN 可以用于关联新询价的配件。"
    "客服在历史里回复过报价不影响新询价的状态判断。"
)


def fetch_recent_messages(conversation_id, limit=WINDOW_SIZE, min_time=None):
    """该会话最近 limit 条消息，返回正序（旧→新）。

    min_time（datetime）：只拉 create_time >= min_time 的消息，用于 AI 开关
    时间闸门——开关前的历史消息不再参与分析。None 表示不过滤。
    """
    q = Message.query.filter(
        Message.conversation_id == conversation_id, Message.deleted_at.is_(None),
    )
    if min_time is not None:
        q = q.filter(Message.create_time >= min_time)
    rows = q.order_by(Message.id.desc()).limit(limit).all()
    return list(reversed(rows))


def split_by_progress(messages, last_analyzed_msg_id):
    """按进度条切分消息 → (context_msgs, new_msgs)。

    context：id <= last_analyzed_msg_id（历史上下文，可能包含 VIN 供关联）
    new：    id >  last_analyzed_msg_id（本次新消息，真正要分析的）
    进度条为 None（首次分析）时全部归 new。
    """
    if last_analyzed_msg_id is None:
        return [], list(messages)
    context, new = [], []
    for m in messages:
        (context if m.id <= last_analyzed_msg_id else new).append(m)
    return context, new


def build_chat_content(messages, focus_msg_ids=None, include_hint=True):
    """消息行 → chat_content 数组（服务方 input_text/input_image 结构）。

    focus_msg_ids: set[int]，这些消息标【新询价】，其余标【历史】。
                   None 表示全部消息都不打标签（兼容旧调用）。
    include_hint: 是否在数组最前面加 AI 系统提示。
    """
    out = []
    if include_hint and focus_msg_ids is not None:
        out.append({"type": "input_text", "text": _AI_HINT})

    focus = focus_msg_ids or set()
    for m in messages:
        if m.direction == Message.DIR_OUT and m.status == Message.ST_FAILED:
            continue  # 没发出去的消息不进上下文，AI 看见会困惑
        name = "我回复" if m.direction == Message.DIR_OUT else (
            m.sender_name or m.sender_wxid or "未知"
        )
        when = m.create_time.strftime("%Y-%m-%d %H:%M:%S")
        # 打标签
        tag = ""
        if focus_msg_ids is not None:
            tag = "【新询价】" if m.id in focus else "【历史】"
        if m.msg_type == Message.MSG_TEXT:
            out.append({
                "type": "input_text",
                "text": f"{when}【{name}】{tag}：{m.content or ''}",
            })
        elif m.msg_type == Message.MSG_QUOTE:
            text = (m.content or "")[:80]
            out.append({
                "type": "input_text",
                "text": f"{when}【{name}】{tag}(引用)：{text}",
            })
        elif m.msg_type in _MEDIA_NOTE:
            out.append({
                "type": "input_text",
                "text": (
                    f"{when}【系统备注】{tag}："
                    f"上一条是【{name}】{_MEDIA_NOTE[m.msg_type]}"
                ),
            })
        # MSG_FORWARD（业务端卡片）与其余未知类型跳过
    return out


def build_empty_check(chat_content):
    """无任何文本条目时跳过本次分析（纯图片占位场景 V1 无法识别）。"""
    return any(item.get("type") == "input_text" for item in chat_content)
