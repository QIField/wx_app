"""收消息轮询：定时向中间方增量拉新消息并入库（多设备版）。

每轮遍历所有已绑定微信设备的启用账号，逐设备执行：
读该设备游标 → 调 get_message 拉增量 → 去重 → 入库 + 更新会话 → 推游标。
游标按 openid 隔离（sync_cursor.uk_openid_type），互不干扰。

联调实测（2026-10-29）已确认的真实结构：
- data.list 数组，元素含 from_wxid/to_wxid/msg_type(字符串)/content/create_time(RFC 1123)/raw_json
- 群消息 content = "发言人wxid:\n正文"，需拆分
- new_msg_id 在 raw_json 的 NewMsgId 字段里
- 无 is_sender：from==设备wxid 视为自己发出（设备wxid取 raw_json.Wxid）
"""
from datetime import datetime, timedelta

from backend.adapter import client as middle_client
from backend.extensions import db
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.models.sync_cursor import SyncCursor
from backend.services import conversations as conversation_service
from backend.services.audit import AuditLog, AuditModule, log_action
from backend.services.devices import pollable_devices
from backend.sync import msg_xml, revoke, sysmsg
from backend.sync.media_predownload import predownload_media

PAGE_SIZE = 100        # 每轮拉一页；单轮增量超一页的情况极少，靠下一轮补
FIRST_HOURS = 1        # 首次运行没有游标时，从最近 1 小时开始拉

# 中间方消息类型编码 → 本系统类型（微信常见编码，联调时校准）
_TYPE_MAP = {
    1: Message.MSG_TEXT,
    3: Message.MSG_IMAGE,
    34: Message.MSG_VOICE,
    43: Message.MSG_VIDEO,
    47: Message.MSG_EMOJI,
    49: Message.MSG_LINK,  # appmsg：链接/文件类，暂归链接
}

# content XML 内容分类 → 本系统类型（msg_type=1 里塞的图片/链接/撤回等，实测 2026-10-31）
_KIND_TO_TYPE = {
    msg_xml.IMAGE: Message.MSG_IMAGE,
    msg_xml.VIDEO: Message.MSG_VIDEO,
    msg_xml.VOICE: Message.MSG_VOICE,
    msg_xml.EMOJI: Message.MSG_EMOJI,
    msg_xml.FILE: Message.MSG_FILE,
    msg_xml.LINK: Message.MSG_LINK,
    msg_xml.QUOTE: Message.MSG_QUOTE,
}


def sync_once(app):
    """跑一轮同步：遍历所有绑定设备的账号，逐设备拉增量。由定时器或测试触发。

    已判定离线的设备整轮跳过（不发 get_message），等在线检测翻身自动恢复。
    """
    with app.app_context():
        for openid in pollable_devices():
            try:
                pushed, revokes = sync_device(openid)
            except Exception as exc:  # noqa: BLE001 单设备失败不拖垮其他设备
                db.session.rollback()
                log_action(AuditModule.SYNC, "消息同步", f"设备 {openid}",
                           result=AuditLog.RESULT_FAIL, detail=str(exc)[:255])
                continue
            broadcast_messages(pushed, openid)
            broadcast_revokes(revokes, openid)
            if pushed:  # 新消息涉及的会话缺名称/头像时立即补拉（函数内部自行容错）
                from backend.sync.profile_sync import refresh_missing_profiles

                refresh_missing_profiles(openid, [p["conversation_id"] for p in pushed])
            predownload_media(pushed)  # 新媒体立刻串行预下载（限时，失败不拖同步）


def sync_device(openid):
    """同步单台设备，返回 (待广播的新消息列表, 撤回事件列表)，commit 已完成。"""
    cursor = _get_cursor(openid)
    params = {
        "start_create_time": cursor.last_sync_time.strftime("%Y-%m-%d %H:%M:%S"),
        "page": 1,
        "page_size": PAGE_SIZE,
    }
    try:
        body = middle_client.call("messag_api", "get_message", params, openid=openid)
    except Exception:
        db.session.rollback()  # 拉取失败：游标不动，下一轮重来
        return [], []

    items = _extract_messages(body)
    latest = cursor.last_sync_time
    pushed = []   # 本轮新入库的消息，commit 后统一广播
    revokes = []  # 本轮命中的撤回事件（原消息已打标），commit 后广播
    for item in items:
        saved = _save_message(openid, item, revokes)
        if saved is None:
            continue
        pushed.append(saved)
        if saved["create_time"] > latest:
            latest = saved["create_time"]

    cursor.last_sync_time = latest
    db.session.commit()
    return pushed, revokes


def broadcast_messages(pushed, openid=""):
    """commit 之后才广播：保证前端听到推送时库里一定能查到。

    群消息发言人昵称/头像实时关联群成员名册（存库是 wxid 原文），
    前端直接消费推送数据，所以这里解析完再推；无昵称时按脱敏契约
    回退「匿名 + 编码」，绝不把 wxid 原文推给前端。
    openid 随事件下发：多账号前端靠它路由到对应账号卡片（跨账号 toast）。
    """
    if not pushed:
        return
    from backend.models.conversation import Conversation
    from backend.services import anonymize
    from backend.services.quote_media import with_media_id
    from backend.sync import group_member
    from backend.ws import hub

    sender_maps = {}
    conv_ids = {p["conversation_id"] for p in pushed}
    convs = Conversation.query.filter(Conversation.id.in_(conv_ids)).all()
    for conv in convs:
        wxids = [p["sender_wxid"] for p in pushed if p["conversation_id"] == conv.id]
        sender_maps[conv.id] = group_member.sender_map_for(conv, wxids)

    for saved in pushed:
        info = sender_maps.get(saved["conversation_id"], {}).get(saved["sender_wxid"] or "")
        nickname = anonymize.resolved_name(
            (info or {}).get("nickname"), saved["sender_wxid"])
        snapshot = anonymize.resolved_name(saved["sender_name"], saved["sender_wxid"])
        hub.broadcast("new_message", {
            "message_id": saved["message_id"],
            "conversation_id": saved["conversation_id"],
            "openid": openid,
            "direction": saved["direction"],
            "msg_type": saved["msg_type"],
            "content": saved["content"],
            "payload": with_media_id(saved.get("payload") or {}, saved.get("content")),  # 引用图片带 media_id
            "summary": saved.get("summary") or "",  # 会话列表摘要：后端算好的，前端直接用
            "sender_name": nickname or snapshot or anonymize.anon_label(saved["sender_wxid"]),
            "sender_avatar": (info or {}).get("avatar") if nickname else None,
            "sender_alias": anonymize.alias_of(saved["sender_wxid"]),
            "create_time": saved["create_time"].strftime("%Y-%m-%d %H:%M:%S"),
        })


def broadcast_revokes(revokes, openid=""):
    """撤回事件广播：前端把对应气泡换成微信样式灰条；openid 供多账号路由。"""
    from backend.ws import hub
    for event in revokes:
        hub.broadcast("message_revoked", {**event, "openid": openid})


def _get_cursor(openid):
    """拿该设备的收消息游标，没有就建一行（从最近 1 小时开始）。"""
    row = (
        SyncCursor.query.filter_by(openid=openid, cursor_type=SyncCursor.CURSOR_MSG)
        .filter(SyncCursor.deleted_at.is_(None))
        .first()
    )
    if row is None:
        row = SyncCursor(
            openid=openid,
            cursor_type=SyncCursor.CURSOR_MSG,
            last_sync_time=datetime.now() - timedelta(hours=FIRST_HOURS),
        )
        db.session.add(row)
        db.session.flush()
    return row


def _extract_messages(body):
    """从 get_message 返回里取消息列表（结构以实际返回为准，联调校准）。"""
    data = body.get("data")
    if isinstance(data, list):
        return data
    return (data or {}).get("list") or []


def _save_message(openid, item, revokes=None):
    """单条消息入库：去重 → 转字段 → 建/找会话 → 写 message → 更新会话。

    撤回通知不入库：按 msgid 定位原消息打 revoked 标记，事件挂到 revokes；
    原消息找不到（未同步过）就落一条系统灰条兜底，保证撤回这件事可见。
    噪音消息（51 状态同步/游戏中心等微信不渲染的事件）入库即软删：留底
    不展示，不建会话、不广播、不刷摘要。正常入库时返回推送信息字典
    （commit 后供广播用）；重复或坏数据返回 None。
    """
    fields = _normalize(item, openid)
    if fields is None:
        return None

    # 撤回通知：标记原消息或落兜底灰条，本身不作为消息入库
    if fields["revoke"]:
        return revoke.apply_revoke(openid, fields, revokes)

    # 去重：middle_msg_id 已存在就整条跳过（含已软删的，重推不复活）
    if fields["middle_msg_id"]:
        exists = Message.query.filter_by(
            middle_msg_id=fields["middle_msg_id"]
        ).first()
        if exists is not None:
            return None

    if fields["noise"]:
        # 噪音：会话不存在就不建不存（杜绝"自己跟自己"的同步垃圾会话）
        conv = conversation_service.get_or_create(
            openid, fields["peer_wxid"], fields["chat_type"], create=False
        )
        if conv is None:
            return None
        db.session.add(_build_message(fields, conv, deleted=True))
        return None  # 不广播、不刷会话摘要

    conv = conversation_service.get_or_create(openid, fields["peer_wxid"], fields["chat_type"])

    msg = _build_message(fields, conv)
    db.session.add(msg)

    # 维护会话：最后一条消息冗余；只有收到的才计未读
    if fields["direction"] == Message.DIR_IN:
        conv.unread_count = (conv.unread_count or 0) + 1
    conv.last_msg = conversation_service.short_summary(
        fields["msg_type"], fields["content"]
    )
    conv.last_msg_at = fields["create_time"]

    return {
        "message_id": msg.id,
        "conversation_id": conv.id,
        "direction": fields["direction"],
        "msg_type": fields["msg_type"],
        "content": fields["content"],
        "payload": fields["payload"],
        "summary": conv.last_msg,  # 后端算好的会话摘要，前端直接用（勿重复造轮子）
        "sender_wxid": fields["sender_wxid"],
        "sender_name": fields["sender_name"],
        "create_time": fields["create_time"],
    }


def _build_message(fields, conv, deleted=False):
    """fields → Message 行；noise 走软删留底（deleted_at=now）。"""
    return Message(
        conversation_id=conv.id,
        msg_type=fields["msg_type"],
        direction=fields["direction"],
        sender_wxid=fields["sender_wxid"],
        sender_name=fields["sender_name"],
        content=fields["content"],
        payload=fields["payload"],
        middle_msg_id=fields["middle_msg_id"],
        new_msg_id=fields["new_msg_id"],
        create_time=fields["create_time"],
        deleted_at=datetime.now() if deleted else None,
    )


def _normalize(item, openid=""):
    """中间方一条消息 → 入库字段（结构按 2026-10-29 联调实测）。

    方向规则见 _direction_and_sender；content 实为微信 XML 时（实测
    图片/链接/撤回都塞在 msg_type=1 里）按内容还原真实类型，撤回通知
    带出定位信息交 revoke.apply_revoke 处理，系统事件交 sysmsg.resolve。
    """
    try:
        raw = _parse_raw_json(item.get("raw_json"))
        peer_wxid, content, sender_wxid, direction = _direction_and_sender(item, raw)
        if not peer_wxid:
            return None

        # msg_type 实测是字符串 "1"，转 int 再查映射
        try:
            raw_type = int(item.get("msg_type"))
        except (TypeError, ValueError):
            raw_type = 1
        msg_type = _TYPE_MAP.get(raw_type, Message.MSG_TEXT)

        create_time = _parse_time(item.get("create_time"))
        if create_time is None:
            return None

        # 按内容还原真实类型（撤回通知单独标记，卡片类补结构化信息给前端）
        revoke = None
        sys_notice = False
        noise = False
        kind = msg_xml.classify(content)
        if kind == msg_xml.REVOKE:
            revoke = msg_xml.revoke_info(content)
        elif kind is not None:
            msg_type = _KIND_TO_TYPE[kind]
        elif raw_type == sysmsg.STATUS_NOTIFY or content.lstrip().startswith("<"):
            # 撤回之外的系统事件：能转文案的转微信同款灰条，
            # 微信不渲染的（51/游戏中心等）标噪音软删
            sys_gray, noise = sysmsg.resolve(content, raw_type, openid)
            if sys_gray:
                content = sys_gray
                sys_notice = True
        payload = dict(item)
        if sys_notice:
            payload["system"] = True
        if noise:
            payload["noise"] = True
        if kind in (msg_xml.LINK, msg_xml.FILE):
            payload["app"] = msg_xml.app_info(content)
        if kind == msg_xml.QUOTE:
            payload["quote"] = msg_xml.quote_info(content)
        if kind == msg_xml.IMAGE:
            # 缩略图宽高随消息下发：前端加载前精确占位，图片不再顶跳聊天窗
            size = msg_xml.image_size(content)
            if size:
                payload["w"], payload["h"] = size

        return {
            "direction": (
                Message.DIR_OUT if sys_notice else direction
            ),  # 系统灰条方向无意义，置出方向避免占未读数
            "peer_wxid": peer_wxid,
            "chat_type": (
                Conversation.CHAT_GROUP
                if "@chatroom" in peer_wxid
                else Conversation.CHAT_SINGLE
            ),
            "sender_wxid": sender_wxid,
            "sender_name": (
                "系统" if sys_notice else (item.get("sender_name") or sender_wxid)
            ),
            "msg_type": msg_type,
            "content": content,
            "payload": payload,
            "revoke": revoke,
            "noise": noise,
            "middle_msg_id": str(item.get("msg_id") or ""),
            "new_msg_id": str(
                item.get("new_msg_id")
                or raw.get("NewMsgId")
                or (raw.get("Data") or {}).get("NewMsgId")
                or ""
            ),
            "create_time": create_time,
        }
    except Exception:
        return None  # 单条坏数据不拖垮整轮


def _direction_and_sender(item, raw):
    """方向与发言人：from == 设备wxid（raw_json.Wxid）视为自己发出，
    对方取 to_wxid；否则为客户发来，对方取 from_wxid。
    群消息 content = "发言人wxid:\n正文"，拆出发言人。
    """
    from_wxid = item.get("from_wxid", "")
    to_wxid = item.get("to_wxid", "")
    content = item.get("content") or ""
    is_self = bool(item.get("is_sender")) or from_wxid == (raw.get("Wxid") or to_wxid)
    peer_wxid = to_wxid if is_self else from_wxid
    sender_wxid = from_wxid
    if not is_self and "@chatroom" in peer_wxid and ":\n" in content:
        head, _, rest = content.partition(":\n")
        if head and "\n" not in head:
            sender_wxid = head
            content = rest
    direction = Message.DIR_OUT if is_self else Message.DIR_IN
    return peer_wxid, content, sender_wxid, direction


def _parse_raw_json(value):
    """解析 raw_json 字符串（里面藏着设备wxid和NewMsgId），失败返回空 dict。"""
    if not value:
        return {}
    import json

    try:
        obj = json.loads(value)
        return obj if isinstance(obj, dict) else {}
    except ValueError:
        return {}


def _parse_time(value):
    """兼容三种实测/文档格式：
    - RFC 1123 "Thu, 29 Oct 2026 18:16:04 GMT"（实测：字面值即北京时间，不做时区换算）
    - "YYYY-MM-DD HH:MM:SS"
    - 秒级时间戳
    """
    from email.utils import parsedate_to_datetime

    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value)
    text = str(value)
    if text.endswith("GMT"):
        try:
            dt = parsedate_to_datetime(text)
            # 中间方的 GMT 标注不可信，按字面值取本地时间
            return datetime(
                dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second
            )
        except (ValueError, TypeError):
            return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None
