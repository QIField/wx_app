"""引用消息的媒体解析：被引用的是图片时，定位库内原图片消息 id。

前端引用块直接渲染缩略图（点击看大图），媒体接口按消息 id 取文件，
所以要把 refermsg 的 svrid 对应到库内消息。是否为图片以库内原消息的
msg_type 为准（企微客服引用 content 为空、部分渠道内容带发送者前缀，
XML 格式不一，不便于在 XML 层判定）。

解析失败或找不到原消息（如超出同步窗口）时原样返回，前端回退
[图片] 标签。供两处消费：消息列表出参（api/conversations._msg_json）
与新消息广播（sync/message_sync.broadcast_messages），保证历史数据
与实时推送行为一致。
"""
from backend.models.message import Message
from backend.sync import msg_xml


def with_media_id(payload, content):
    """payload.quote 注入 media_id（被引用图片的库内消息 id）。

    非引用消息 / 已解析过 / svrid 对不上号 / 原消息不是图片时原样返回。
    """
    if not isinstance(payload, dict):
        return payload
    quote = payload.get("quote")
    if not quote or quote.get("media_id"):
        return payload
    svrid = msg_xml.quote_refer_svrid(content or "")
    if not svrid:
        return payload
    row = (
        Message.query.filter(
            Message.new_msg_id == svrid,
            Message.deleted_at.is_(None),
        )
        .order_by(Message.id.desc())
        .first()
    )
    if row is None or row.msg_type != Message.MSG_IMAGE:
        return payload
    payload["quote"] = {**quote, "media_id": row.id}
    # 缩略图精确占位：带上原消息的宽高（老消息没有就缺省，前端回退 min 占位）
    for key in ("w", "h"):
        value = (row.payload or {}).get(key)
        if value:
            payload["quote"][key] = value
    # 企微客服等渠道引用 content 为空，quote.text 是空的：补 [图片] 让降级展示也正确
    if not quote.get("text"):
        payload["quote"]["text"] = "[图片]"
    return payload
