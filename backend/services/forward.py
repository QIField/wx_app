"""消息转发编排：统一按逐条真实下发（中间方无合并卡片接口，产品定稿不再提供合并选项）。

逐条（single）：把原消息按类型重新拼参，走 send_service 正常下发到微信，
对方收到的就是普通气泡。收到的媒体（无 payload url）先经媒体缓存取回文件，
挂到中间方可拉取的上传 URL 后重发。
"""
import shutil
from datetime import datetime
from uuid import uuid4

from backend.extensions import db
from backend.models.conversation import Conversation
from backend.models.forward_snapshot import ForwardSnapshot
from backend.models.group_member import GroupMember
from backend.models.message import Message
from backend.sync import msg_xml
from backend.sync.send_service import SendDispatchError, send_message

# 逐条转发一次最多带的原消息条数：防止异常 payload 放大下发体积
SINGLE_LIMIT = 50
# 合并转发快照上限：微信卡片本身也不展示无限长记录
MERGE_LIMIT = 100

# 快照里的类型占位标签（无文本可取的类型不强行编内容）
_TYPE_LABEL = {
    Message.MSG_IMAGE: "[图片]",
    Message.MSG_FILE: "[文件]",
    Message.MSG_VIDEO: "[视频]",
    Message.MSG_VOICE: "[语音]",
    Message.MSG_EMOJI: "[表情]",
    Message.MSG_QUOTE: "[引用]",
}


def snapshot_text_of(msg):
    """原消息 → 快照/预览文本：文本用原文，媒体类型转占位标签，系统 XML 显示 [系统消息]。"""
    if msg.msg_type == Message.MSG_TEXT:
        text = (msg.content or "").strip()
        # 残留的系统 XML（拍一拍等）与普通消息区分开，不让原始 XML 进快照
        return "[系统消息]" if text.startswith("<") else text
    return _TYPE_LABEL.get(msg.msg_type, "[未知类型]")


def _sender_display(conv, msg):
    """快照里的发送者展示信息 → (显示名, 头像url)。

    message.sender_name 存的是 wxid 原文（中间方不提供昵称），必须经名册解析：
    群聊查 GroupMember（昵称+头像），单聊取会话资料（对方昵称+头像）；
    出方向用操作人快照。在转发时刻解析并冻结——成员改名不影响已生成的卡片。
    """
    if msg.direction == Message.DIR_OUT:
        return msg.operator_name or "客服", None
    if conv.chat_type == Conversation.CHAT_GROUP:
        member = (
            GroupMember.query.filter_by(
                openid=conv.openid,
                chatroom_wxid=conv.wxid,
                wxid=msg.sender_wxid or "",
                deleted_at=None,
            ).first()
            if msg.sender_wxid else None
        )
        if member:
            return member.nickname or "成员", member.avatar
        return "成员", None  # 名册未同步到该成员：不落 wxid 原文
    return conv.name or "客户", conv.avatar


def _rehost_media(msg):
    """收到的媒体（payload 无中间方 url）→ 取回文件挂到中间方可下载的 URL。

    借媒体缓存（media_fetch，带档位降级与短退避）拿到本地文件，复制进
    media/uploads/（与上传接口同一目录、同一下载路由，中间方直接按 url 拉）。
    下载失败（中间方 502/媒体过期）返回 None，由调用方跳过该条。
    """
    from flask import request

    from backend.config import MEDIA_DIR, PUBLIC_BASE_URL
    from backend.services import media_fetch

    try:
        src = media_fetch.fetch_and_cache(msg)
    except Exception:  # noqa: BLE001 转发主流程不因单条媒体下载失败中断
        return None
    if not src or not src.is_file():
        return None

    dest_dir = MEDIA_DIR / "uploads"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{uuid4().hex}{src.suffix}"
    shutil.copyfile(src, dest)
    path = f"/media/uploads/{dest.name}"
    base = PUBLIC_BASE_URL or request.url_root.rstrip("/")
    return base + path, path  # url 给中间方下载；path 给本地气泡预览


def _redispatch_params(msg):
    """原消息 → 逐条转发的 (msg_type, content, payload)；该类型不支持转发返回 None。

    媒体类优先用 payload 里的原始 url（自己发的/上传过的），收到的消息没有 url
    就走 _rehost_media 取回重挂；拿不到可下载地址的类型跳过。
    引用/语音/表情没有对应发送接口，一律不支持。
    """
    p = dict(msg.payload or {})
    if p.get("revoked") or p.get("system"):
        return None
    t = msg.msg_type
    if t == Message.MSG_TEXT:
        text = (msg.content or "").strip()
        if not text or text.startswith("<"):
            return None
        # 产品定稿：逐条转发不带「原发送者：」前缀，按原文直达（出处由合并卡片承担）
        return Message.MSG_TEXT, text, {}
    if t == Message.MSG_IMAGE:
        if p.get("img_url"):
            return Message.MSG_IMAGE, "", {"img_url": p["img_url"]}
        rehosted = _rehost_media(msg)
        if rehosted:
            url, path = rehosted
            return Message.MSG_IMAGE, "", {"img_url": url, "path": path, "w": p.get("w"), "h": p.get("h")}
        return None
    if t == Message.MSG_VIDEO:
        if p.get("video_url"):
            return Message.MSG_VIDEO, "", {
                "video_url": p["video_url"],
                "thumb_url": p.get("thumb_url") or "",
                "video_duration": p.get("video_duration") or 0,
            }
        rehosted = _rehost_media(msg)
        if rehosted:
            url, path = rehosted
            return Message.MSG_VIDEO, "", {
                "video_url": url,
                "thumb_url": "",
                "video_duration": p.get("video_duration") or 0,
                "path": path,
            }
        return None
    if t == Message.MSG_FILE and p.get("file_url"):
        return Message.MSG_FILE, "", {"file_url": p["file_url"], "file_name": p.get("file_name") or msg.content or "文件"}
    if t == Message.MSG_LINK:
        app = p.get("app") or msg_xml.app_info(msg.content or "")
        if app.get("url"):
            return Message.MSG_LINK, "", {
                "title": app.get("title") or "[链接]",
                "desc": app.get("desc") or "",
                "link_url": app["url"],
                "thumb_url": p.get("thumb_url") or "",
            }
    return None


def forward_single(src_msgs, targets, operator):
    """逐条转发：对每个目标会话逐条下发真实消息。返回 (成功条数, 失败条数, 跳过条数)。"""
    sent = failed = skipped = 0
    for conv in targets:
        for src in src_msgs:
            params = _redispatch_params(src)
            if params is None:
                skipped += 1
                continue
            try:
                send_message(conv.id, *params, operator=operator)
                sent += 1
            except SendDispatchError:
                failed += 1
    return sent, failed, skipped


def forward_merge(src_msgs, src_conv, targets, operator):
    """合并转发：每个目标会话落一张本地卡片 + 一组快照行（同一次转发快照内容一致）。

    当前（2026-11-15 产品定稿）中间方无原生卡片发送接口，卡片只在业务端可见，
    前端已无入口；保留本函数作为升级预案——中间方提供 appmsg 19 发送接口后，
    在这里追加：用 items 拼原生 XML → 逐目标调 adapter/sender 的新下发函数。
    升级步骤全文见 docs/message-forward.md 第三节。

    返回创建的卡片消息列表（供 WS 广播按 id 幂等去重）。
    """
    now = datetime.now()
    items = []
    for i, m in enumerate(src_msgs[:MERGE_LIMIT]):
        name, avatar = _sender_display(src_conv, m)
        items.append({
            "seq": i + 1,
            "sender_name": name,
            "sender_avatar": avatar,
            "content": snapshot_text_of(m),
            "create_time": m.create_time or now,
        })
    # 卡片预览：前两条「发送者：内容」，与微信转发卡片观感一致
    preview = [f"{it['sender_name']}：{it['content']}" for it in items[:2]]
    title = f"「{src_conv.name or '会话'}」的聊天记录"

    cards = []
    for conv in targets:
        card = Message(
            conversation_id=conv.id,
            msg_type=Message.MSG_FORWARD,
            direction=Message.DIR_OUT,
            content=title,
            payload={"title": title, "count": len(items), "preview": preview},
            status=Message.ST_SENT,  # 本地落库即送达（不经中间方，无发送中态）
            operator_id=operator.id,
            operator_name=operator.name,
            org_name=operator.org_name,
            create_time=now,
        )
        db.session.add(card)
        db.session.flush()  # 拿卡片自增 id，快照挂上去
        db.session.add_all([
            ForwardSnapshot(
                forward_msg_id=card.id,
                seq=it["seq"],
                sender_name=it["sender_name"],
                sender_avatar=it["sender_avatar"],
                content=it["content"],
                create_time=it["create_time"],
            )
            for it in items
        ])
        conv.last_msg = f"[聊天记录] {len(items)}条消息"
        conv.last_msg_at = now
        cards.append(card)
    db.session.commit()
    return cards


def broadcast_cards(cards):
    """合并卡片落库后广播 new_message：已打开的页面即时上屏，按 message_id 幂等。

    openid 按卡片所属会话取（目标会话可能跨绑定设备）。
    """
    from backend.models.conversation import Conversation
    from backend.ws import hub

    for card in cards:
        conv = db.session.get(Conversation, card.conversation_id)
        hub.broadcast("new_message", {
            "message_id": card.id,
            "conversation_id": card.conversation_id,
            "openid": (conv.openid or "") if conv else "",
            "direction": card.direction,
            "msg_type": card.msg_type,
            "content": card.content,
            "payload": card.payload,
            "summary": card.payload.get("title") if card.payload else "",
            "operator_name": card.operator_name,
            "create_time": card.create_time.strftime("%Y-%m-%d %H:%M:%S"),
        })
