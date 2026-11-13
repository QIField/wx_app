"""会话与聊天记录 API：给前端读库（都过滤软删除）。

多设备：工作台一次只看一个聊天账号——列表类接口按 ?openid=（默认第一个
绑定设备）过滤；归属校验按"当前登录人全部绑定设备"（同账号数据互通，
跨账号严格隔离）。未绑定设备的账号看到的列表为空。
"""
import time

from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy import select

from backend.extensions import db
from backend.models.contact import Contact
from backend.models.conversation import Conversation
from backend.models.group_member import GroupMember
from backend.models.message import Message
from backend.services import anonymize, conversations as conversation_service
from backend.services.auth import require_role
from backend.services.devices import active_openid_for, user_openids
from backend.services.pinyin import (
    full_pinyin,
    initials as pinyin_initials,
    pinyin_tokens,
)
from backend.services.quote_media import with_media_id
from backend.sync import group_member

bp = Blueprint("conversations", __name__)

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


def _my_openids():
    """当前登录人绑定的全部设备标识；未绑定为空列表。"""
    return user_openids(g.current_user.id)


def _active_openid():
    """?openid= 选当前设备；未传默认第一个绑定。返回 (openid, 错误响应)。"""
    openid, err = active_openid_for(g.current_user, request.args.get("openid"))
    if err:
        msg, status = err
        return None, (jsonify(code=status, msg=msg), status)
    return openid, None


def _my_conversation(conversation_id):
    """取属于当前登录人任一绑定设备的会话；跨账号/已删除的会话当不存在。"""
    openids = _my_openids()
    if not openids:
        return None
    return (
        Conversation.query.filter(
            Conversation.id == conversation_id,
            Conversation.deleted_at.is_(None),
            Conversation.openid.in_(openids),
        ).first()
    )


@bp.get("/api/conversations")
@require_role()
def list_conversations():
    """会话列表：当前设备内 置顶优先，其余按最后消息时间倒序（NULL 排最后）。"""
    if not _my_openids():
        return jsonify(code=0, msg="success", data=[])
    openid, err = _active_openid()
    if err:
        return err

    rows = (
        Conversation.query.filter(
            Conversation.deleted_at.is_(None),
            Conversation.openid == openid,
        )
        .order_by(
            Conversation.pinned.desc(),
            Conversation.last_msg_at.is_(None).asc(),  # 兼容 MySQL 5.7（无 NULLS LAST）
            Conversation.last_msg_at.desc(),
        )
        .all()
    )
    return jsonify(code=0, msg="success", data=[_conv_json(c) for c in rows])


@bp.post("/api/conversations")
@require_role()
def open_conversation():
    """主动发起会话：按 contact_id 建/取会话（前端不传 wxid——脱敏契约）。

    body: {"contact_id": 123, "chat_type": 1|2}；?openid= 选设备，默认第一个绑定。
    contact_id 是通讯录条目的 id（Contact 行号）；通讯录未同步到的老会话补集，
    该 id 是会话行号，回退按会话反查。已存在直接返回，没有则新建。
    """
    if not _my_openids():
        return jsonify(code=400, msg="当前账号未绑定微信设备"), 400
    openid, err = _active_openid()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    contact_id = body.get("contact_id")
    try:
        chat_type = int(body.get("chat_type"))
    except (TypeError, ValueError):
        chat_type = 0
    if not contact_id or chat_type not in (Conversation.CHAT_SINGLE, Conversation.CHAT_GROUP):
        return jsonify(code=400, msg="contact_id 与 chat_type（1单聊/2群聊）必填且合法"), 400

    wxid = _resolve_contact_wxid(contact_id, openid, chat_type)
    if not wxid:
        return jsonify(code=404, msg="通讯录中没有该联系人"), 404

    conv = conversation_service.get_or_create(openid, wxid, chat_type)
    db.session.commit()
    return jsonify(code=0, msg="success", data=_conv_json(conv))


def _resolve_contact_wxid(contact_id, openid, chat_type):
    """条目 id → wxid：正数 Contact 行优先，负数（补集）按 -id 反查会话行（均限当前设备）。

    负号约定见 contacts._conv_contact_json：两套自增 id 靠符号隔离，
    否则 conv id 撞 contact id 时会发错人。
    """
    if contact_id < 0:
        conv = Conversation.query.filter(
            Conversation.id == -contact_id,
            Conversation.openid == openid,
            Conversation.chat_type == chat_type,
            Conversation.deleted_at.is_(None),
        ).first()
        return conv.wxid if conv else None
    contact_type = (
        Contact.TYPE_FRIEND if chat_type == Conversation.CHAT_SINGLE else Contact.TYPE_GROUP
    )
    contact = Contact.query.filter_by(
        id=contact_id, openid=openid, type=contact_type, deleted_at=None
    ).first()
    if contact:
        return contact.wxid
    conv = Conversation.query.filter(
        Conversation.id == contact_id,
        Conversation.openid == openid,
        Conversation.chat_type == chat_type,
        Conversation.deleted_at.is_(None),
    ).first()
    return conv.wxid if conv else None


@bp.patch("/api/conversations/<int:conversation_id>")
@require_role()
def update_conversation(conversation_id):
    """会话操作：置顶 / 标为已读·未读 / 消息免打扰。

    body: {"pinned": 0|1} 和/或 {"read": true|false} 和/或 {"muted": 0|1}。
    read=true 清零未读数；read=false 标为未读（未读数记 1，微信同款）。
    未读必须落库，否则重拉列表会把旧的未读数盖回来（前端红点反复出现）。
    """
    conv = _my_conversation(conversation_id)
    if conv is None:
        return jsonify(code=404, msg="会话不存在"), 404

    body = request.get_json(silent=True) or {}
    changed = False

    def _flag(key):
        """0/1 小整型标记（pinned/muted）解析：合法返回值，非法返回 None。"""
        try:
            v = int(body[key])
        except (TypeError, ValueError):
            return None
        return v if v in (0, 1) else None

    for key in ("pinned", "muted"):
        if key in body:
            value = _flag(key)
            if value is None:
                return jsonify(code=400, msg=f"{key} 仅支持 0/1"), 400
            setattr(conv, key, value)
            changed = True

    if "read" in body:
        if not isinstance(body["read"], bool):
            return jsonify(code=400, msg="read 仅支持 true/false"), 400
        conv.unread_count = 0 if body["read"] else 1
        changed = True

    if not changed:
        return jsonify(code=400, msg="没有可更新的字段"), 400

    db.session.commit()
    return jsonify(code=0, msg="success", data=_conv_json(conv))


def _fetch_conversation_page(conversation_id, openids, page_size, before_id):
    """会话归属校验 + 消息一页合并为一次 SQL 往返（远程库每次往返 25~35ms）。

    返回 (conv, rows)；conv 为 None 表示归属未命中（跨账号/已删除/无消息兜底交给调用方）。
    """
    conv, rows = None, []
    if not openids:
        return conv, rows
    mq = (
        select(Conversation, Message)
        .join(Message, Message.conversation_id == Conversation.id)
        .where(
            Conversation.id == conversation_id,
            Conversation.deleted_at.is_(None),
            Conversation.openid.in_(openids),
            Message.deleted_at.is_(None),
        )
    )
    if before_id:
        mq = mq.where(Message.id < before_id)
    pairs = db.session.execute(mq.order_by(Message.id.desc()).limit(page_size)).all()
    if pairs:
        conv, rows = pairs[0][0], [p[1] for p in pairs]
    return conv, rows


@bp.get("/api/conversations/<int:conversation_id>/messages")
@require_role()
def list_messages(conversation_id):
    """聊天记录：时间正序，?before_id 游标翻页（拿上一页最小 id 往前翻）。

    附 [perf] 分段耗时日志（merged 合并查询 / fallback 补查 / assemble 组装）。
    """
    _t0 = time.perf_counter()
    page_size = request.args.get("page_size", DEFAULT_PAGE_SIZE, type=int)
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))
    before_id = request.args.get("before_id", type=int)

    conv, rows = _fetch_conversation_page(conversation_id, _my_openids(), page_size, before_id)
    _t1 = time.perf_counter()

    fallback_ms = 0.0
    if conv is None:
        # 无消息会话的罕见路径：单独补查归属（跨账号仍当不存在）
        _f0 = time.perf_counter()
        conv = _my_conversation(conversation_id)
        fallback_ms = (time.perf_counter() - _f0) * 1000
        if conv is None:
            return jsonify(code=404, msg="会话不存在"), 404

    rows.reverse()  # 库里倒序取最新一页，翻转成正序给前端

    # 群消息发言人资料：存库是 wxid 原文，展示时实时关联群成员名册（单聊返回空映射）
    sender_map = group_member.sender_map_for(conv, [m.sender_wxid for m in rows])

    has_more = len(rows) == page_size
    data = {
        "conversation": _conv_json(conv),
        "messages": [_msg_json(m, sender_map) for m in rows],
        "next_before_id": rows[0].id if has_more and rows else None,
    }
    _t2 = time.perf_counter()
    quotes = sum(1 for m in rows if (m.payload or {}).get("quote"))
    current_app.logger.info(
        "[perf] messages#%s merged=%.0fms fallback=%.0fms assemble=%.0fms n=%d quotes=%d",
        conversation_id,
        (_t1 - _t0) * 1000, fallback_ms, (_t2 - _t1) * 1000,
        len(rows), quotes,
    )
    return jsonify(code=0, msg="success", data=data)


@bp.get("/api/conversations/<int:conversation_id>/members")
@require_role()
def list_members(conversation_id):
    """群成员名册：输入框 @提及 选择器的数据源。

    脱敏契约：只给行号 id，不下发 wxid；全拼/首字母由后端 pypinyin 预算，
    前端一次取回即可本地过滤，打字过程中不再请求（零延迟）。
    单聊没有名册，返回空列表而不是报错，前端据此不弹选择层。
    """
    conv = _my_conversation(conversation_id)
    if conv is None:
        return jsonify(code=404, msg="会话不存在"), 404
    if conv.chat_type != Conversation.CHAT_GROUP:
        return jsonify(code=0, msg="success", data={"list": [], "total": 0})

    rows = GroupMember.query.filter_by(
        openid=conv.openid, chatroom_wxid=conv.wxid, deleted_at=None,
    ).all()
    items = [_member_json(m) for m in rows]
    # 昵称未解析（拼音为空）的排最后，其余按全拼字典序
    items.sort(key=lambda x: (not x["pinyin"], x["pinyin"] or x["alias"]))
    return jsonify(code=0, msg="success", data={"list": items, "total": len(items)})


def _member_json(m):
    """群成员出参：昵称/头像走现有脱敏规则，附全拼与首字母供 @ 搜索。"""
    name = anonymize.resolved_name(m.nickname, m.wxid)
    return {
        "id": m.id,
        "name": name,
        "avatar": anonymize.avatar_or_none(name, m.avatar),
        "alias": anonymize.alias_of(m.wxid),
        "pinyin": full_pinyin(name),
        "pinyin_toks": pinyin_tokens(name),
        "initials": pinyin_initials(name),
    }


def _conv_json(c):
    """会话出参（脱敏契约）：不含 wxid；名称未解析 → name=None + alias，头像一并匿名。

    附 pinyin/initials/pinyin_toks 供会话搜索框拼音匹配（输入 zhang/z 命中 张峰）。
    """
    name = anonymize.resolved_name(c.name, c.wxid)
    return {
        "id": c.id,
        "chat_type": c.chat_type,
        "name": name,
        "avatar": anonymize.avatar_or_none(name, c.avatar),
        "alias": anonymize.alias_of(c.wxid),
        "pinyin": full_pinyin(name),
        "pinyin_toks": pinyin_tokens(name),
        "initials": pinyin_initials(name),
        "unread_count": c.unread_count,
        "pinned": c.pinned,
        "muted": c.muted,
        "last_msg": c.last_msg,
        "last_msg_at": c.last_msg_at.strftime("%Y-%m-%d %H:%M:%S") if c.last_msg_at else None,
    }


def _msg_json(m, sender_map=None):
    """消息出参（脱敏契约）：不含 sender_wxid；发言人展示字段走
    group_member.sender_view 唯一拼装点（与 WS 广播同口径，防两处漂移）。"""
    info = (sender_map or {}).get(m.sender_wxid or "") or {}
    return {
        "id": m.id,
        "msg_type": m.msg_type,
        "direction": m.direction,
        **group_member.sender_view(m.sender_wxid, info, m.sender_name),
        "content": m.content,
        "payload": with_media_id(m.payload, m.content),  # 引用图片注入 media_id，前端渲染缩略图
        "operator_name": m.operator_name or "",  # 发出消息的操作人快照（气泡徽章）
        "create_time": m.create_time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": m.status,
    }
