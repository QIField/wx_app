"""通讯录 API：好友/群列表（数据来自会话表，排除软删除）。"""
from flask import Blueprint, jsonify, request
from pypinyin import lazy_pinyin, Style

from backend.extensions import db
from backend.models.conversation import Conversation

bp = Blueprint("contacts", __name__)

# type 参数 → 会话类型
_TYPE_MAP = {
    "friends": Conversation.CHAT_SINGLE,
    "groups": Conversation.CHAT_GROUP,
}


@bp.get("/api/contacts")
def list_contacts():
    """通讯录列表：?type=friends|groups&keyword=，按拼音首字母分组排序。"""
    chat_type = _TYPE_MAP.get(request.args.get("type", "friends"))
    if chat_type is None:
        return jsonify(code=400, msg="type 仅支持 friends / groups"), 400

    keyword = (request.args.get("keyword") or "").strip()
    query = Conversation.query.filter(
        Conversation.deleted_at.is_(None),
        Conversation.chat_type == chat_type,
    )
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(db.or_(Conversation.name.ilike(like), Conversation.wxid.ilike(like)))

    items = [_contact_json(c) for c in query.all()]
    # 字母升序、# 排最后；同字母内按名字
    items.sort(key=lambda x: (x["letter"] == "#", x["letter"], (x["name"] or "").lower()))
    return jsonify(code=0, msg="success", data={"list": items, "total": len(items)})


def _contact_json(c):
    """会话行 → 通讯录条目；资料未解析（name 为空或还是 wxid）时用 wxid 兜底。"""
    name = c.name if c.name and c.name != c.wxid else None
    return {
        "id": c.id,
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
