"""统一备注配置 API（contact_remark_config：设备维度）。

设备维度（2026-11-25）：scope_type + target_wxid + openid 唯一。
同一联系人在不同设备上各有独立行，互不影响；同一设备被多账号关联时共享配置。

- GET/PUT /api/contacts/{contact_id}/remark-config：好友→用户级，群→群级（自动判定）。
- GET/PUT /api/groups/{contact_id}/members/{member_alias}/remark-config：
  群成员入口 → 写用户级行。openid 从群会话解析（群成员备注是设备内视角）。
- POST /api/remark/sync：触发中间方修改微信备注（仅好友 scope=user 生效）。
- contact_id 允许负数（补集会话条目，出参约定 -conv.id），复用通讯录解析规则。
- 脱敏契约：入参只收条目 id 与 alias 短码；alias 不可逆，按群名册重算匹配。
"""
from flask import Blueprint, g, jsonify, request
import logging

from backend.extensions import db
from backend.models.contact import Contact
from backend.models.contact_remark_config import SCOPE_GROUP, SCOPE_USER, ContactRemarkConfig
from backend.models.conversation import Conversation
from backend.models.group_member import GroupMember
from backend.services import anonymize
from backend.services.audit import AuditModule, log_action
from backend.services.auth import require_role
from backend.services.devices import active_openid_for, user_openids

logger = logging.getLogger(__name__)
bp = Blueprint("remark_config", __name__)


# ---------- 条目解析 ----------


def _parse_target(resolver, contact_id):
    """条目 id 解析公共样板：id 转换失败或解析不到 → None。"""
    try:
        return resolver(int(contact_id))
    except ValueError:
        return None


def _resolve_active_openid():
    """当前登录人选定的设备 openid（active_openid_for：请求指定优先，否则第一个绑定）。"""
    openid, err = active_openid_for(g.current_user)
    if err:
        return None
    return openid


def _config_target(contact_id):
    """条目 id → (wxid, scope_type, openid)。群条目 → group 级，其余 → user 级。

    正数 = contact 行；负数 = 补集会话行（-conv.id），两套 id 不混查。
    缺设备上下文时返回 None（active_openid_for 取不到就拒绝）。
    """
    openids = user_openids(g.current_user.id)
    if not openids:
        return None
    # 选当前活跃设备（active_openid_for 已做了：请求指定优先，否则第一个绑定）
    openid = _resolve_active_openid()
    if not openid:
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
        return conv.wxid, scope, openid
    c = Contact.query.filter(
        Contact.id == contact_id,
        Contact.openid.in_(openids),
        Contact.deleted_at.is_(None),
    ).first()
    if c:
        scope = SCOPE_GROUP if c.type == Contact.TYPE_GROUP else SCOPE_USER
        return c.wxid, scope, openid
    conv = Conversation.query.filter(Conversation.id == contact_id, *conv_filter).first()
    if not conv:
        return None
    scope = SCOPE_GROUP if conv.chat_type == Conversation.CHAT_GROUP else SCOPE_USER
    return conv.wxid, scope, openid


def _group_target(contact_id):
    """群条目 id → (openid, 群wxid)（仅群聊条目，供成员名册定位）。"""
    openids = user_openids(g.current_user.id)
    if not openids:
        return None
    openid = _resolve_active_openid()
    if not openid:
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


def _config_data(scope, wxid, openid):
    """读取配置；无记录返回空默认值。"""
    q = ContactRemarkConfig.query.filter_by(
        scope_type=scope, target_wxid=wxid, deleted_at=None,
    )
    # 有 openid 就精确命中该设备行；没 openid 时（旧接口残留）回退按 wxid+scope 查
    if openid:
        cfg = q.filter(ContactRemarkConfig.openid == openid).first()
        if cfg is None:
            cfg = q.filter(ContactRemarkConfig.openid.is_(None)).first()
    else:
        cfg = q.first()
    if cfg:
        return cfg.to_json()
    return {
        "scope_type": scope, "remark_name": "", "auto_quote_enabled": False,
        "oe_detail_enabled": False,
        "level": ContactRemarkConfig.LEVEL_NORMAL, "tags": [],
    }


def _validated_payload(body):
    """校验并归一请求体 → (payload, None) 或 (None, 错误消息)。"""
    raw = body.get("remark_name")
    if raw is None:
        raw = body.get("remark")
    remark = str(raw).strip() if raw is not None else None
    if remark is not None and len(remark) > ContactRemarkConfig.MAX_REMARK_LEN:
        return None, f"备注不能超过 {ContactRemarkConfig.MAX_REMARK_LEN} 字"

    auto_quote = None
    if "auto_quote_enabled" in body and body.get("auto_quote_enabled") is not None:
        auto_quote = bool(body.get("auto_quote_enabled"))

    tags = None
    raw_tags = body.get("tags")
    if raw_tags is not None:
        tags = []
        for t in raw_tags if isinstance(raw_tags, list) else []:
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

    oe_detail = None
    if "oe_detail_enabled" in body and body.get("oe_detail_enabled") is not None:
        oe_detail = bool(body.get("oe_detail_enabled"))

    return (remark, auto_quote, tags, level, oe_detail), None


def _compute_display_name(scope, wxid, remark_name):
    """最终展示名（remark > nickname > 匿名标识），与 contacts._contact_json 保持一致。"""
    if remark_name:
        return remark_name
    if scope == SCOPE_USER:
        from backend.models.contact import Contact
        c = Contact.query.filter_by(wxid=wxid, deleted_at=None).first()
        if c:
            return anonymize.resolved_name(c.name, wxid)
    else:
        from backend.models.conversation import Conversation
        conv = Conversation.query.filter_by(wxid=wxid, deleted_at=None).first()
        if conv:
            return anonymize.resolved_name(conv.name, wxid)
    return anonymize.resolved_name(None, wxid)


def _save_config(scope, wxid, openid, body, sync_wechat=True):
    """upsert 配置（按 scope + wxid + openid 唯一键定位）。

    payload 四字段均支持 None（增量）：None 表示请求方没带该字段，保持原值；
    带具体值才覆盖。remark 允许空串（显式清除备注）。

    空 openid 兜底：如果调用方没传 openid，尝试解析（从 token 活跃设备取）；
    仍取不到时按 (scope, wxid) 定位旧行（兼容迁移过渡）。
    """
    payload, err = _validated_payload(body)
    if err:
        return jsonify(code=400, msg=err), 400
    remark, auto_quote, tags, level, oe_detail = payload

    # 空 openid 兜底：尝试解析
    if not openid:
        openid = _resolve_active_openid()

    # 先读当前行（按 openid 优先，openid 为空兼容旧行）、算 diff
    # 注意：查旧行时不过滤 deleted_at——要能找到软删行来复活
    q = ContactRemarkConfig.query.filter_by(
        scope_type=scope, target_wxid=wxid,
    )
    cfg = q.filter(ContactRemarkConfig.openid == openid).first() if openid else None
    if cfg is None:
        cfg = q.filter(ContactRemarkConfig.openid.is_(None)).first()
    cfg_existed = cfg is not None
    old_remark = (cfg.remark_name if cfg else None) or ""

    diff = []
    remark_changed = False
    if remark is not None and old_remark != remark:
        diff.append(f"备注[{old_remark}]→[{remark}]")
        remark_changed = True

    # 先调中间方：remark 有变更且 sync_wechat=True → 成功才往下走
    if sync_wechat and remark_changed and remark is not None:
        ok, middle_error = _sync_to_wechat(wxid, remark, openid)
        if not ok:
            db.session.rollback()
            return jsonify(code=500, msg=f"微信侧备注修改失败：{middle_error}"), 500

    # upsert：找不到就新建（带 openid），找到就恢复软删行
    if cfg is None:
        cfg = ContactRemarkConfig(
            scope_type=scope, target_wxid=wxid, openid=openid,
        )
        db.session.add(cfg)
    else:
        cfg.restore()
        # 存量行 openid 可能为 NULL，当前端设备有值时补上
        if openid and not cfg.openid:
            cfg.openid = openid

    if remark is not None:
        cfg.remark_name = remark
    if auto_quote is not None:
        if bool(cfg.auto_quote_enabled) != auto_quote:
            diff.append("自动报价关→开" if auto_quote else "自动报价开→关")
        cfg.auto_quote_enabled = auto_quote
    if level is not None and (cfg.level or ContactRemarkConfig.LEVEL_NORMAL) != level:
        diff.append(f"等级[{cfg.level}]→[{level}]")
        cfg.level = level
    if tags is not None and list(cfg.tags or []) != tags:
        diff.append(f"标签{list(cfg.tags or [])}→{tags}")
        cfg.tags = tags
    if oe_detail is not None:
        if bool(cfg.oe_detail_enabled) != oe_detail:
            diff.append("OE详号关→开" if oe_detail else "OE详号开→关")
        cfg.oe_detail_enabled = oe_detail
    db.session.commit()

    # 客户等级变更 → 自动重算所有 pending/review 询价
    if any("等级" in d for d in diff):
        from backend.services.quote_pricing import recompute_pending
        recompute_pending()
    log_action(
        AuditModule.CONTACT, "保存备注设置",
        f"{'用户' if scope == SCOPE_USER else '群'} {anonymize.alias_of(wxid)}",
        detail=("；".join(diff) or "无变更")[:200],
    )
    data = cfg.to_json()
    data["synced"] = True
    data["middle_error"] = None
    data["display_name"] = _compute_display_name(scope, wxid, cfg.remark_name)
    return jsonify(code=0, msg="success", data=data), 200


# ---------- 联系人入口（好友→用户级 / 群→群级） ----------


@bp.get("/api/contacts/<contact_id>/remark-config")
@require_role()
def get_remark_config(contact_id):
    """统一备注配置；前端只传条目 id（不传 wxid/openid——脱敏契约）。"""
    target = _parse_target(_config_target, contact_id)
    if not target:
        return jsonify(code=404, msg="联系人不存在或无设备权限"), 404
    wxid, scope, openid = target
    return jsonify(code=0, msg="success", data=_config_data(scope, wxid, openid))


@bp.put("/api/contacts/<contact_id>/remark-config")
@require_role()
def put_remark_config(contact_id):
    """保存统一备注配置（备注名称 / 自动报价 / 标签）。"""
    target = _parse_target(_config_target, contact_id)
    if not target:
        return jsonify(code=404, msg="联系人不存在或无设备权限"), 404
    wxid, scope, openid = target
    resp, status = _save_config(scope, wxid, openid, request.get_json(silent=True) or {})
    return resp, status


# ---------- 群成员入口 ----------


@bp.get("/api/groups/<contact_id>/members/<member_alias>/remark-config")
@require_role()
def get_member_remark_config(contact_id, member_alias):
    """群成员备注设置：定位用户级配置（设备维度：群内视角 → 设备 openid 取群条目）。"""
    wxid = _member_wxid(contact_id, member_alias)
    target = _parse_target(_group_target, contact_id)
    if not (wxid and target):
        return jsonify(code=404, msg="群成员不存在"), 404
    openid, _ = target
    return jsonify(code=0, msg="success", data=_config_data(SCOPE_USER, wxid, openid))


@bp.put("/api/groups/<contact_id>/members/<member_alias>/remark-config")
@require_role()
def put_member_remark_config(contact_id, member_alias):
    """保存群成员备注设置：写入该成员的用户级行（设备维度 openid 取群条目）。"""
    wxid = _member_wxid(contact_id, member_alias)
    target = _parse_target(_group_target, contact_id)
    if not (wxid and target):
        return jsonify(code=404, msg="群成员不存在"), 404
    openid, _ = target
    resp, status = _save_config(SCOPE_USER, wxid, openid, request.get_json(silent=True) or {})
    return resp, status


# ---------- 触发中间方同步 ----------


def _scope_from_wxid(wxid):
    """wxid → ContactRemarkConfig scope：@chatroom 结尾 = group，否则 user。"""
    return SCOPE_GROUP if wxid.endswith("@chatroom") else SCOPE_USER


def _sync_to_wechat(target_wxid, remark, openid=None):
    """调中间方 contacts_api.setFriendRemark 修改微信侧备注（好友和群通用同一接口）。

    返回 (synced, middle_error)：
    - synced=True  → 中间方改成功 / demo 模式 / 无可用设备（跳过不阻断）
    - synced=False → 显式空串跳过 / 中间方返回非零 code
    """
    if not remark:
        return False, None  # 空串=清除备注，跳过中间方调用（本地存空串即可）

    import os as _os
    from backend.adapter.client import DEMO_MODE, call as middle_call, MiddleApiError

    # demo 模式（单测）或显式跳过 → 不碰真实中间方
    if DEMO_MODE or _os.environ.get("SKIP_MIDDLE_SYNC"):
        return True, None

    # 无可用设备 → 跳过中间方，不阻断本地保存
    try:
        if not openid:
            openids = user_openids(g.current_user.id) if getattr(g, 'current_user', None) else []
            openid = openids[0] if openids else None
    except Exception:
        openid = None
    if not openid:
        return True, None

    try:
        body = middle_call(
            "contacts_api", "setFriendRemark",
            params={"wxid": target_wxid, "remark": remark},
            uuid=False,  # 纯同步命令，文档只要求 openid + wxid + remark
            openid=openid,
        )
    except MiddleApiError as e:
        return False, str(e)
    except Exception as e:  # noqa: BLE001 网络异常兜底
        return False, f"中间方调用异常: {e}"

    if body.get("code") == 0:
        return True, None
    return False, body.get("msg") or "中间方返回非零 code"


@bp.post("/api/remark/sync")
@require_role()
def post_sync_remark():
    """触发中间方 setFriendRemark 修改微信侧备注 → 成功后写 ContactRemarkConfig。

    请求体：
      wxid: str         好友 wxid 或群 wxid（@chatroom 结尾自动判 scope=group）
      remark: str       新备注（空串或不传 = 清除备注，仅写本地）
      remark_name: str  兼容旧字段名
    """
    body = request.get_json(silent=True) or {}
    wxid = body.get("wxid")
    if not wxid:
        return jsonify(code=400, msg="缺少 wxid"), 400
    wxid = str(wxid).strip()
    if not wxid:
        return jsonify(code=400, msg="wxid 不能为空"), 400

    raw_remark = body.get("remark_name")
    if raw_remark is None:
        raw_remark = body.get("remark", "")
    remark = str(raw_remark).strip() if raw_remark is not None else ""
    if len(remark) > ContactRemarkConfig.MAX_REMARK_LEN:
        return jsonify(code=400, msg=f"备注不能超过 {ContactRemarkConfig.MAX_REMARK_LEN} 字"), 400

    scope = _scope_from_wxid(wxid)
    openid = _resolve_active_openid()

    synced, middle_error = _sync_to_wechat(wxid, remark, openid)

    save_body = {"remark_name": remark}
    resp, status = _save_config(scope, wxid, openid, save_body, sync_wechat=False)
    if status != 200:
        return resp, status

    data = resp.get_json()
    if isinstance(data.get("data"), dict):
        data["data"]["synced"] = synced
        data["data"]["middle_error"] = middle_error
    return jsonify(data), 200
