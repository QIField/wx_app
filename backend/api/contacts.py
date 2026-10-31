"""通讯录 API：好友/群列表（contact 表全量同步 ∪ 历史会话，排除软删除）。

多设备：列表按当前登录人绑定的设备（open_id）过滤。
"""
from flask import Blueprint, g, jsonify, request
from pypinyin import lazy_pinyin, Style

from backend.extensions import db
from backend.models.contact import Contact
from backend.models.contact_profile import ContactProfile
from backend.models.conversation import Conversation
from backend.services.auth import require_role

bp = Blueprint("contacts", __name__)

# type 参数 → 会话/联系人类型
_TYPE_MAP = {
    "friends": (Conversation.CHAT_SINGLE, Contact.TYPE_FRIEND),
    "groups": (Conversation.CHAT_GROUP, Contact.TYPE_GROUP),
}


@bp.get("/api/contacts")
@require_role()
def list_contacts():
    """通讯录列表：?type=friends|groups&keyword=，按拼音首字母分组排序。

    主源是 contact 表（全量联系人，聊没聊过都在）；历史会话里有、
    通讯录还没同步到的作为补集拼上；关键词同时匹配昵称/wxid/备注。
    """
    mapped = _TYPE_MAP.get(request.args.get("type", "friends"))
    if mapped is None:
        return jsonify(code=400, msg="type 仅支持 friends / groups"), 400
    chat_type, contact_type = mapped
    openid = (g.current_user.open_id or "").strip()
    if not openid:
        return jsonify(code=0, msg="success", data={"list": [], "total": 0})

    keyword = (request.args.get("keyword") or "").strip()
    like = f"%{keyword}%"

    # 主源：通讯录表；备注（业务自建）也参与搜索
    cq = Contact.query.filter(Contact.openid == openid, Contact.type == contact_type)
    if keyword:
        cq = (
            cq.outerjoin(ContactProfile, ContactProfile.wxid == Contact.wxid)
            .filter(
                db.or_(
                    Contact.name.ilike(like),
                    Contact.wxid.ilike(like),
                    ContactProfile.remark.ilike(like),
                )
            )
        )
    contacts = cq.all()

    # 本设备该类型的全部会话：按 wxid 挂未读/摘要；找不到会话的联系人补集用
    convs = Conversation.query.filter(
        Conversation.deleted_at.is_(None),
        Conversation.openid == openid,
        Conversation.chat_type == chat_type,
    ).all()
    conv_by_wxid = {c.wxid: c for c in convs}

    items = [_contact_json(c, conv_by_wxid.get(c.wxid)) for c in contacts]

    # 补集：会话里有、通讯录还没同步到的老会话（关键词按 昵称/wxid 过滤）
    known = {c.wxid for c in contacts}
    kw = keyword.lower()
    extras = [
        c for c in convs
        if c.wxid not in known
        and (not kw or kw in (c.name or "").lower() or kw in c.wxid.lower())
    ]
    items.extend(_conv_contact_json(c) for c in extras)

    # 字母升序、# 排最后；同字母内按名字
    items.sort(key=lambda x: (x["letter"] == "#", x["letter"], (x["name"] or "").lower()))
    return jsonify(code=0, msg="success", data={"list": items, "total": len(items)})


def _contact_json(c, conv):
    """contact 行 → 通讯录条目；contact 缺资料时回退用会话里已解析的昵称/头像。"""
    name = c.name if c.name and c.name != c.wxid else None
    if not name and conv and conv.name and conv.name != c.wxid:
        name = conv.name
    avatar = c.avatar or (conv.avatar if conv else None)
    return {
        "id": c.id,
        "conversation_id": conv.id if conv else None,
        "wxid": c.wxid,
        "chat_type": conv.chat_type if conv else (Conversation.CHAT_GROUP if c.type == Contact.TYPE_GROUP else Conversation.CHAT_SINGLE),
        "name": name or c.wxid,
        "avatar": avatar,
        "letter": _letter(name or c.wxid),
        "unread_count": conv.unread_count if conv else 0,
        "pinned": conv.pinned if conv else 0,
        "last_msg": conv.last_msg if conv else None,
        "last_msg_at": conv.last_msg_at.strftime("%Y-%m-%d %H:%M:%S") if conv and conv.last_msg_at else None,
    }


def _conv_contact_json(c):
    """历史会话行 → 通讯录条目（通讯录未同步到时的补集形态）。"""
    name = c.name if c.name and c.name != c.wxid else None
    return {
        "id": c.id,
        "conversation_id": c.id,
        "wxid": c.wxid,
        "chat_type": c.chat_type,
        "name": name or c.wxid,
        "avatar": c.avatar,
        "letter": _letter(name or c.wxid),
        "unread_count": c.unread_count,
        "pinned": c.pinned,
        "last_msg": c.last_msg,
        "last_msg_at": c.last_msg_at.strftime("%Y-%m-%d %H:%M:%S") if c.last_msg_at else None,
    }


def _letter(text):
    """排序字母：中文取拼音首字母，其余取首字符；非 A-Z 归入 #。"""
    if not text:
        return "#"
    tokens = lazy_pinyin(text, style=Style.FIRST_LETTER)
    ch = (tokens[0][:1] if tokens else text[:1]).upper()
    return ch if "A" <= ch <= "Z" else "#"


# ---------- 联系人档案（备注/标签，业务自建，不写回微信） ----------


@bp.get("/api/contacts/<wxid>/profile")
@require_role()
def get_profile(wxid):
    """联系人档案；无记录返回默认空值。"""
    p = ContactProfile.query.filter_by(wxid=wxid).first()
    return jsonify(code=0, msg="success", data=p.to_json() if p else {"remark": "", "tags": []})


@bp.put("/api/contacts/<wxid>/profile")
@require_role()
def put_profile(wxid):
    """保存备注/标签（upsert）。校验超限，标签去重去空。"""
    body = request.get_json(silent=True) or {}
    remark = str(body.get("remark") or "").strip()

    if len(remark) > ContactProfile.MAX_REMARK_LEN:
        return jsonify(code=400, msg=f"备注不能超过 {ContactProfile.MAX_REMARK_LEN} 字"), 400

    tags_in = body.get("tags") if isinstance(body.get("tags"), list) else []
    tags = []
    for t in tags_in:
        t = str(t).strip()
        if t and t not in tags:
            tags.append(t)
    if len(tags) > ContactProfile.MAX_TAGS:
        return jsonify(code=400, msg=f"标签最多 {ContactProfile.MAX_TAGS} 个"), 400
    if any(len(t) > ContactProfile.MAX_TAG_LEN for t in tags):
        return jsonify(code=400, msg=f"单个标签不能超过 {ContactProfile.MAX_TAG_LEN} 字"), 400

    p = ContactProfile.query.filter_by(wxid=wxid).first()
    if p is None:
        p = ContactProfile(wxid=wxid)
        db.session.add(p)
    p.remark = remark
    p.tags = tags
    db.session.commit()
    return jsonify(code=0, msg="success", data=p.to_json())
