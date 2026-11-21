"""通讯录 API：好友/群列表（contact 表全量同步 ∪ 历史会话，排除软删除）。

多设备：列表按 ?openid=（默认第一个绑定设备）过滤，跨账号不可见。
"""
from flask import Blueprint, g, jsonify, request

from backend.extensions import db
from backend.models.contact import Contact
from backend.models.contact_remark_config import (
    SCOPE_GROUP,
    SCOPE_USER,
    ContactRemarkConfig,
)
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
    # remarks = {(scope_type, wxid): remark_name}，搜索 + 展示复用同一份
    all_wxids = [c.wxid for c in contacts]
    # 通讯录列表要混合查补集会话（没进 contact 表的老会话），先取 contact 行的 wxid
    remarks = _batch_remarks(all_wxids)

    if keyword:
        kw = keyword.lower()
        # 关键词搜索按 scope 取对应 wxid 的 remark（好友列表只看 user，群列表只看 group）
        scope = Contact.TYPE_GROUP if contact_type == Contact.TYPE_GROUP else "user"
        contacts = [
            c for c in contacts
            if _name_kw_hit(
                c.name, c.wxid, _remark_of(remarks, scope, c.wxid), kw
            )
        ]

    # 本设备该类型的全部会话：按 wxid 挂未读/摘要；找不到会话的联系人补集用
    convs = Conversation.query.filter(
        Conversation.deleted_at.is_(None),
        Conversation.openid == openid,
        Conversation.chat_type == chat_type,
    ).all()
    conv_by_wxid = {c.wxid: c for c in convs}

    items = [_contact_json(c, conv_by_wxid.get(c.wxid), remarks) for c in contacts]

    # 补集：会话里有、通讯录还没同步到的老会话（关键词只按昵称过滤）
    known = {c.wxid for c in contacts}
    deleted_wxids = {
        c.wxid
        for c in Contact.query.filter(
            Contact.openid == openid,
            Contact.deleted_at.isnot(None),
        ).all()
    }
    # 补集会话的 remark 也要查（没进 contact 表的老会话）
    extra_wxids = [c.wxid for c in convs if c.wxid not in known and c.wxid not in deleted_wxids]
    remarks.update(_batch_remarks(extra_wxids))
    scope = Contact.TYPE_GROUP if contact_type == Contact.TYPE_GROUP else "user"
    kw = keyword.lower()
    extras = [
        c for c in convs
        if c.wxid not in known
        and c.wxid not in deleted_wxids
        and (not kw or _name_kw_hit(
            c.name, c.wxid, _remark_of(remarks, scope, c.wxid), kw
        ))
    ]
    items.extend(_conv_contact_json(c, remarks) for c in extras)

    # 字母升序、# 排最后；同字母内按名字
    items.sort(key=lambda x: (x["letter"] == "#", x["letter"], (x["name"] or "").lower()))
    return jsonify(code=0, msg="success", data={"list": items, "total": len(items)})


def _batch_remarks(wxids):
    """批量查 ContactRemarkConfig → {(scope_type, wxid): remark_name}。"""
    if not wxids:
        return {}
    rows = ContactRemarkConfig.query.filter(
        ContactRemarkConfig.target_wxid.in_(wxids),
        ContactRemarkConfig.deleted_at.is_(None),
    ).all()
    return {(rc.scope_type, rc.target_wxid): (rc.remark_name or "") for rc in rows}


def _remark_of(remarks, scope, wxid):
    """从批量查询结果里按 scope 取备注，取不到或为空返回空串。"""
    return (remarks.get((scope, wxid)) or "").strip()


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


def _contact_json(c, conv, remarks):
    """contact 行 → 通讯录条目；contact 缺资料时回退用会话里已解析的昵称/头像。

    展示优先级：ContactRemarkConfig.remark_name > 中间方昵称 > 匿名标识。
    """
    chat_type = conv.chat_type if conv else _roster_chat_type(c)
    scope = SCOPE_GROUP if chat_type == Conversation.CHAT_GROUP else SCOPE_USER
    remark_name = _remark_of(remarks, scope, c.wxid)
    if remark_name:
        name = remark_name
    else:
        name = anonymize.resolved_name(c.name, c.wxid) or anonymize.resolved_name(
            conv.name if conv else None, c.wxid)
    return _item_json(
        row_id=c.id, wxid=c.wxid, chat_type=chat_type, name=name,
        avatar=c.avatar or (conv.avatar if conv else None), conv=conv,
    )


def _conv_contact_json(c, remarks):
    """历史会话行 → 通讯录条目（通讯录未同步到时的补集形态）。

    row_id 取负值：contact 表与会话表是两套自增 id，直接用正数会与
    contact 行撞号（前端渲染 key 冲突出"幽灵重复行"，档案/发消息也会
    解析到同号的另一个联系人），负号跨表隔离命名空间。
    """
    scope = SCOPE_GROUP if c.chat_type == Conversation.CHAT_GROUP else SCOPE_USER
    remark_name = _remark_of(remarks, scope, c.wxid)
    if remark_name:
        name = remark_name
    else:
        name = anonymize.resolved_name(c.name, c.wxid)
    return _item_json(
        row_id=-c.id, wxid=c.wxid, chat_type=c.chat_type,
        name=name, avatar=c.avatar, conv=c,
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

