"""通讯录 API：好友/群列表（contact 表全量同步 ∪ 历史会话，排除软删除）。

多设备：列表按 ?openid=（默认第一个绑定设备）过滤，跨账号不可见。
"""
from flask import Blueprint, g, jsonify, request

from backend.extensions import db
from backend.models.contact import Contact
from backend.models.contact_profile import ContactProfile
from backend.models.conversation import Conversation
from backend.services import anonymize
from backend.services.auth import require_role
from backend.services.devices import active_openid_for, user_openids
from backend.services.pinyin import (
    full_pinyin,
    initials as pinyin_initials,
    letter,
    pinyin_hit,
    pinyin_tokens,
)

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
    通讯录还没同步到的作为补集拼上；关键词只匹配 昵称/备注（wxid 不参与——脱敏契约）。
    """
    mapped = _TYPE_MAP.get(request.args.get("type", "friends"))
    if mapped is None:
        return jsonify(code=400, msg="type 仅支持 friends / groups"), 400
    chat_type, contact_type = mapped
    if not user_openids(g.current_user.id):  # 未绑定设备：空列表（与旧口径一致）
        return jsonify(code=0, msg="success", data={"list": [], "total": 0})
    openid, err = active_openid_for(g.current_user, request.args.get("openid"))
    if err:
        msg, status = err
        return jsonify(code=status, msg=msg), status

    keyword = (request.args.get("keyword") or "").strip()

    # 主源：通讯录表；备注（业务自建）也参与搜索
    cq = Contact.query.filter(
        Contact.openid == openid,
        Contact.type == contact_type,
        Contact.deleted_at.is_(None),
    )
    contacts = cq.all()

    # 拼音搜索：SQL LIKE 匹配不了拼音，关键词统一回 Python 侧过滤
    # （列表本就全量取回，无额外查询成本）；备注批量取一次避免 N+1。
    if keyword:
        kw = keyword.lower()
        wxids = [c.wxid for c in contacts]
        remarks = {
            p.wxid: (p.remark or "")
            for p in ContactProfile.query.filter(
                ContactProfile.wxid.in_(wxids),
                ContactProfile.deleted_at.is_(None),
            ).all()
        } if wxids else {}
        contacts = [c for c in contacts if _name_kw_hit(c.name, c.wxid, remarks.get(c.wxid, ""), kw)]

    # 本设备该类型的全部会话：按 wxid 挂未读/摘要；找不到会话的联系人补集用
    convs = Conversation.query.filter(
        Conversation.deleted_at.is_(None),
        Conversation.openid == openid,
        Conversation.chat_type == chat_type,
    ).all()
    conv_by_wxid = {c.wxid: c for c in convs}

    items = [_contact_json(c, conv_by_wxid.get(c.wxid)) for c in contacts]

    # 补集：会话里有、通讯录还没同步到的老会话（关键词只按昵称过滤）
    known = {c.wxid for c in contacts}
    deleted_wxids = {
        c.wxid
        for c in Contact.query.filter(
            Contact.openid == openid,
            Contact.deleted_at.isnot(None),
        ).all()
    }
    kw = keyword.lower()
    extras = [
        c for c in convs
        if c.wxid not in known
        and c.wxid not in deleted_wxids
        and (not kw or _name_kw_hit(c.name, c.wxid, "", kw))
    ]
    items.extend(_conv_contact_json(c) for c in extras)

    # 字母升序、# 排最后；同字母内按名字
    items.sort(key=lambda x: (x["letter"] == "#", x["letter"], (x["name"] or "").lower()))
    return jsonify(code=0, msg="success", data={"list": items, "total": len(items)})


def _kw_in(fields, kw):
    """任一字段包含关键词（小写比较，空字段跳过）。"""
    return any(f and kw in str(f).lower() for f in fields)


def _name_kw_hit(raw_name, wxid, remark, kw):
    """联系人名关键词命中：原文昵称 / 解析名 / 备注任一包含，或拼音按字边界命中。

    拼音匹配用 token 对齐（pinyin_hit），不用全拼子串——否则
    housheng 会跨字命中 杭|州|圣|驰（hangzhou+sheng）这类误结果。
    通讯录行传备注参与匹配，补集会话行无备注传空串。
    """
    name = anonymize.resolved_name(raw_name, wxid) or ""
    return (
        _kw_in([raw_name, name, remark, pinyin_initials(name), pinyin_initials(remark)], kw)
        or pinyin_hit(pinyin_tokens(name), kw)
        or pinyin_hit(pinyin_tokens(remark), kw)
    )


def _contact_json(c, conv):
    """contact 行 → 通讯录条目；contact 缺资料时回退用会话里已解析的昵称/头像。"""
    name = anonymize.resolved_name(c.name, c.wxid) or anonymize.resolved_name(
        conv.name if conv else None, c.wxid)
    chat_type = conv.chat_type if conv else _roster_chat_type(c)
    return _item_json(
        row_id=c.id, wxid=c.wxid, chat_type=chat_type, name=name,
        avatar=c.avatar or (conv.avatar if conv else None), conv=conv,
    )


def _conv_contact_json(c):
    """历史会话行 → 通讯录条目（通讯录未同步到时的补集形态）。

    row_id 取负值：contact 表与会话表是两套自增 id，直接用正数会与
    contact 行撞号（前端渲染 key 冲突出"幽灵重复行"，档案/发消息也会
    解析到同号的另一个联系人），负号跨表隔离命名空间。
    """
    return _item_json(
        row_id=-c.id, wxid=c.wxid, chat_type=c.chat_type,
        name=anonymize.resolved_name(c.name, c.wxid), avatar=c.avatar, conv=c,
    )


def _item_json(row_id, wxid, chat_type, name, avatar, conv):
    """通讯录条目公共组装（脱敏契约）：出参不含 wxid；未解析名称保持 None + alias，
    头像随之匿名；未读/摘要等会话信息有则挂上。"""
    return {
        "id": row_id,
        "conversation_id": conv.id if conv else None,
        "chat_type": chat_type,
        "name": name,
        "avatar": anonymize.avatar_or_none(name, avatar),
        "alias": anonymize.alias_of(wxid),
        "letter": letter(name) if name else "#",
        "pinyin": full_pinyin(name),
        "pinyin_toks": pinyin_tokens(name),
        "initials": pinyin_initials(name),
        "unread_count": conv.unread_count if conv else 0,
        "pinned": conv.pinned if conv else 0,
        "last_msg": conv.last_msg if conv else None,
        "last_msg_at": conv.last_msg_at.strftime("%Y-%m-%d %H:%M:%S") if conv and conv.last_msg_at else None,
    }


def _roster_chat_type(c):
    """contact 类型 → 会话类型（无会话时前端展示用）。"""
    return Conversation.CHAT_GROUP if c.type == Contact.TYPE_GROUP else Conversation.CHAT_SINGLE


# ---------- 联系人档案（备注/标签，业务自建，不写回微信） ----------


def _profile_wxid(contact_id):
    """条目 id → wxid（限当前登录人绑定设备）。

    正数 = contact 行；负数 = 补集（会话行，出参约定取 -conv.id）。
    两套自增 id 不能混查——正负号隔离，避免解析到同号的另一个联系人。
    """
    openids = user_openids(g.current_user.id)
    if not openids:
        return None
    if contact_id < 0:
        conv = Conversation.query.filter(
            Conversation.id == -contact_id,
            Conversation.openid.in_(openids),
            Conversation.deleted_at.is_(None),
        ).first()
        return conv.wxid if conv else None
    c = Contact.query.filter(
        Contact.id == contact_id,
        Contact.openid.in_(openids),
        Contact.deleted_at.is_(None),
    ).first()
    if c:
        return c.wxid
    conv = Conversation.query.filter(
        Conversation.id == contact_id,
        Conversation.openid.in_(openids),
        Conversation.deleted_at.is_(None),
    ).first()
    return conv.wxid if conv else None


@bp.get("/api/contacts/<contact_id>/profile")
@require_role()
def get_profile(contact_id):
    """联系人档案（前端只传条目 id，不传 wxid）；无记录返回默认空值。

    id 允许负数（补集条目），int 转换失败按不存在处理。
    """
    try:
        wxid = _profile_wxid(int(contact_id))
    except ValueError:
        return jsonify(code=404, msg="联系人不存在"), 404
    if not wxid:
        return jsonify(code=404, msg="联系人不存在"), 404
    p = ContactProfile.query.filter_by(wxid=wxid, deleted_at=None).first()
    return jsonify(code=0, msg="success", data=p.to_json() if p else {"remark": "", "tags": []})


@bp.put("/api/contacts/<contact_id>/profile")
@require_role()
def put_profile(contact_id):
    """保存备注/标签（upsert）。校验超限，标签去重去空。"""
    try:
        wxid = _profile_wxid(int(contact_id))
    except ValueError:
        return jsonify(code=404, msg="联系人不存在"), 404
    if not wxid:
        return jsonify(code=404, msg="联系人不存在"), 404

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

    p = ContactProfile.query.filter_by(wxid=wxid).first()  # 含已删除：命中则复活旧行
    if p is None:
        p = ContactProfile(wxid=wxid)
        db.session.add(p)
    else:
        p.restore()
    p.remark = remark
    p.tags = tags
    db.session.commit()
    return jsonify(code=0, msg="success", data=p.to_json())
