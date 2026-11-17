"""统一备注配置 API（contact_remark_config：用户级全局生效 / 群级）。

- GET/PUT /api/contacts/{contact_id}/remark-config：好友→用户级，群→群级（自动判定）。
- GET/PUT /api/groups/{contact_id}/members/{member_alias}/remark-config：
  群成员入口 → 写用户级行（私聊/其他群同源，全局生效）。
- contact_id 允许负数（补集会话条目，出参约定 -conv.id），复用通讯录解析规则。
- 脱敏契约：入参只收条目 id 与 alias 短码；alias 不可逆，按群名册重算匹配。
- 存量 contact_profile 数据已由 db_migrate 一次性搬入新表，新表是唯一事实源。
"""
from flask import Blueprint, g, jsonify, request

from backend.extensions import db
from backend.models.contact import Contact
from backend.models.contact_remark_config import SCOPE_GROUP, SCOPE_USER, ContactRemarkConfig
from backend.models.conversation import Conversation
from backend.models.group_member import GroupMember
from backend.services import anonymize
from backend.services.audit import AuditModule, log_action
from backend.services.auth import require_role
from backend.services.devices import user_openids

bp = Blueprint("remark_config", __name__)


# ---------- 条目解析 ----------


def _parse_target(resolver, contact_id):
    """条目 id 解析公共样板：id 转换失败或解析不到 → None（端点统一回 404）。"""
    try:
        return resolver(int(contact_id))
    except ValueError:
        return None


def _config_target(contact_id):
    """条目 id → (wxid, scope_type)。群条目 → group 级，其余 → user 级。

    正数 = contact 行；负数 = 补集会话行（-conv.id），两套 id 不混查。
    """
    openids = user_openids(g.current_user.id)
    if not openids:
        return None
    conv_filter = (
        Conversation.openid.in_(openids),
        Conversation.deleted_at.is_(None),
    )
    if contact_id < 0:
        conv = Conversation.query.filter(Conversation.id == -contact_id, *conv_filter).first()
        if not conv:
            return None
        scope = SCOPE_GROUP if conv.chat_type == Conversation.CHAT_GROUP else SCOPE_USER
        return conv.wxid, scope
    c = Contact.query.filter(
        Contact.id == contact_id,
        Contact.openid.in_(openids),
        Contact.deleted_at.is_(None),
    ).first()
    if c:
        scope = SCOPE_GROUP if c.type == Contact.TYPE_GROUP else SCOPE_USER
        return c.wxid, scope
    conv = Conversation.query.filter(Conversation.id == contact_id, *conv_filter).first()
    if not conv:
        return None
    scope = SCOPE_GROUP if conv.chat_type == Conversation.CHAT_GROUP else SCOPE_USER
    return conv.wxid, scope


def _group_target(contact_id):
    """群条目 id → (openid, 群wxid)（仅群聊条目，供成员名册定位）。"""
    openids = user_openids(g.current_user.id)
    if not openids:
        return None
    if contact_id < 0:
        conv = Conversation.query.filter(
            Conversation.id == -contact_id,
            Conversation.openid.in_(openids),
            Conversation.chat_type == Conversation.CHAT_GROUP,
            Conversation.deleted_at.is_(None),
        ).first()
        return (conv.openid, conv.wxid) if conv else None
    c = Contact.query.filter(
        Contact.id == contact_id,
        Contact.openid.in_(openids),
        Contact.type == Contact.TYPE_GROUP,
        Contact.deleted_at.is_(None),
    ).first()
    return (c.openid, c.wxid) if c else None


def _member_wxid_by_alias(openid, chatroom_wxid, member_alias):
    """群成员 alias → wxid（alias 为 HMAC 短码不可逆，按名册重算匹配）。"""
    rows = GroupMember.query.filter_by(
        openid=openid, chatroom_wxid=chatroom_wxid, deleted_at=None,
    ).all()
    for m in rows:
        if anonymize.alias_of(m.wxid) == member_alias:
            return m.wxid
    return None


def _member_wxid(contact_id, member_alias):
    """群成员入口公共解析：群条目 → 名册 alias 反查 wxid；任一步失败返回 None。"""
    target = _parse_target(_group_target, contact_id)
    if not target:
        return None
    openid, chatroom_wxid = target
    return _member_wxid_by_alias(openid, chatroom_wxid, member_alias)


# ---------- 读取 / 保存 ----------


def _config_data(scope, wxid):
    """读取配置；无记录返回空默认值。"""
    cfg = ContactRemarkConfig.query.filter_by(
        scope_type=scope, target_wxid=wxid, deleted_at=None,
    ).first()
    if cfg:
        return cfg.to_json()
    return {
        "scope_type": scope, "remark_name": "", "auto_quote_enabled": False,
        "level": ContactRemarkConfig.LEVEL_NORMAL, "tags": [],
    }


def _validated_payload(body):
    """校验并归一请求体 → (payload, None) 或 (None, 错误消息)。remark 兼容旧字段名。

    level 为增量语义：请求体显式带 level 才校验覆盖（None=不变更），
    避免备注面板等旧调用方不带该字段时误重置客户等级。
    """
    raw = body.get("remark_name")
    if raw is None:
        raw = body.get("remark", "")
    remark = str(raw).strip()
    if len(remark) > ContactRemarkConfig.MAX_REMARK_LEN:
        return None, f"备注不能超过 {ContactRemarkConfig.MAX_REMARK_LEN} 字"
    tags = []
    for t in body.get("tags") if isinstance(body.get("tags"), list) else []:
        t = str(t).strip()
        if t and t not in tags:
            tags.append(t)
    if len(tags) > ContactRemarkConfig.MAX_TAGS:
        return None, f"标签最多 {ContactRemarkConfig.MAX_TAGS} 个"
    if any(len(t) > ContactRemarkConfig.MAX_TAG_LEN for t in tags):
        return None, f"单个标签不能超过 {ContactRemarkConfig.MAX_TAG_LEN} 字"
    level = None
    if "level" in body and body.get("level") is not None:
        level = str(body["level"]).strip()
        if level not in ContactRemarkConfig.ALLOWED_LEVELS:
            return None, "客户等级不合法（vip_a/vip_b/normal）"
    return (remark, bool(body.get("auto_quote_enabled")), tags, level), None


def _save_config(scope, wxid, body):
    """upsert 配置（含已删除行复活，唯一键不冲突）；写审计，返回 (响应, 状态码)。"""
    payload, err = _validated_payload(body)
    if err:
        return jsonify(code=400, msg=err), 400
    remark, auto_quote, tags, level = payload

    cfg = ContactRemarkConfig.query.filter_by(scope_type=scope, target_wxid=wxid).first()
    if cfg is None:
        cfg = ContactRemarkConfig(scope_type=scope, target_wxid=wxid)
        db.session.add(cfg)
    else:
        cfg.restore()

    diff = []
    if (cfg.remark_name or "") != remark:
        diff.append(f"备注[{cfg.remark_name or ''}]→[{remark}]")
    if bool(cfg.auto_quote_enabled) != auto_quote:
        diff.append("自动报价关→开" if auto_quote else "自动报价开→关")
    if level is not None and (cfg.level or ContactRemarkConfig.LEVEL_NORMAL) != level:
        diff.append(f"等级[{cfg.level}]→[{level}]")
    if list(cfg.tags or []) != tags:
        diff.append(f"标签{list(cfg.tags or [])}→{tags}")
    cfg.remark_name = remark
    cfg.auto_quote_enabled = auto_quote
    if level is not None:
        cfg.level = level
    cfg.tags = tags
    db.session.commit()
    log_action(
        AuditModule.CONTACT, "保存备注设置",
        f"{'用户' if scope == SCOPE_USER else '群'} {anonymize.alias_of(wxid)}",
        detail=("；".join(diff) or "无变更")[:200],
    )
    return jsonify(code=0, msg="success", data=cfg.to_json()), 200


# ---------- 联系人入口（好友→用户级 / 群→群级） ----------


@bp.get("/api/contacts/<contact_id>/remark-config")
@require_role()
def get_remark_config(contact_id):
    """统一备注配置；前端只传条目 id（不传 wxid——脱敏契约）。"""
    target = _parse_target(_config_target, contact_id)
    if not target:
        return jsonify(code=404, msg="联系人不存在"), 404
    wxid, scope = target
    return jsonify(code=0, msg="success", data=_config_data(scope, wxid))


@bp.put("/api/contacts/<contact_id>/remark-config")
@require_role()
def put_remark_config(contact_id):
    """保存统一备注配置（备注名称 / 自动报价 / 标签）。"""
    target = _parse_target(_config_target, contact_id)
    if not target:
        return jsonify(code=404, msg="联系人不存在"), 404
    wxid, scope = target
    resp, status = _save_config(scope, wxid, request.get_json(silent=True) or {})
    return resp, status


# ---------- 群成员入口（写用户级行，全局生效） ----------


@bp.get("/api/groups/<contact_id>/members/<member_alias>/remark-config")
@require_role()
def get_member_remark_config(contact_id, member_alias):
    """群成员备注设置：定位用户级配置（与私聊/其他群同源）。"""
    wxid = _member_wxid(contact_id, member_alias)
    if not wxid:
        return jsonify(code=404, msg="群成员不存在"), 404
    return jsonify(code=0, msg="success", data=_config_data(SCOPE_USER, wxid))


@bp.put("/api/groups/<contact_id>/members/<member_alias>/remark-config")
@require_role()
def put_member_remark_config(contact_id, member_alias):
    """保存群成员备注设置：写入该成员的用户级行，私聊与所有群聊同步生效。"""
    wxid = _member_wxid(contact_id, member_alias)
    if not wxid:
        return jsonify(code=404, msg="群成员不存在"), 404
    resp, status = _save_config(SCOPE_USER, wxid, request.get_json(silent=True) or {})
    return resp, status
