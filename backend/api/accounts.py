"""账号管理 API：列表 / 新增 / 编辑 / 启停用 / 重置密码。

权限规则（已确认）：
- developer：全部操作，含微信设备绑定（多设备）与创建任意角色
- admin：可管理账号，但不可操作 developer 行、不可创建 developer、不可绑定设备
- 所有写操作记审计日志，业务规则拒绝也记 fail
"""
from flask import Blueprint, g, jsonify, request
from werkzeug.security import generate_password_hash

from backend.extensions import db
from backend.models.user import (
    MANAGE_ROLES,
    ROLE_ADMIN,
    ROLE_AGENT,
    ROLE_DEVELOPER,
    STATUS_OFF,
    STATUS_ON,
    User,
)
from backend.models.user_device import UserDevice
from backend.services.audit import AuditLog, AuditModule, log_action
from backend.services.auth import require_role
from backend.services.devices import user_devices, user_openids

bp = Blueprint("accounts", __name__)

INITIAL_PASSWORD = "123456"  # 新增/重置的初始密码
_MAX_DEVICES = 20  # 单账号绑定设备上限，防误传超大列表


def _target(user):
    """审计日志的对象格式：账号 · 姓名（能唯一定位）。"""
    return f"{user.username} · {user.name}"


def _manageable(me, target_user):
    """admin 不可操作 developer 行。"""
    return me.role == ROLE_DEVELOPER or target_user.role != ROLE_DEVELOPER


def _resolve_org(org_id, target_role):
    """校验组织归属：agent/admin 必选；developer 可空（跨组织）。

    返回 (Org, None) 或 (None, (响应, 状态码))；组织是账号必填属性（方案 A）。
    """
    from backend.models.org import Org

    if not org_id:
        if target_role == ROLE_DEVELOPER:
            return None, None  # 开发者账号不绑组织
        return None, (jsonify(code=400, msg="请选择所属组织"), 400)
    try:
        org = db.session.get(Org, int(org_id))
    except (TypeError, ValueError):
        return None, (jsonify(code=400, msg="组织参数不合法"), 400)
    if org is None or org.status != 1:
        return None, (jsonify(code=400, msg="组织不存在或已停用"), 400)
    return org, None


@bp.get("/api/accounts")
@require_role(*MANAGE_ROLES)
def list_accounts():
    rows = User.query.order_by(User.role.desc(), User.id).all()
    return jsonify(code=0, msg="success", data=[u.to_json(with_devices=True) for u in rows])


@bp.post("/api/accounts")
@require_role(*MANAGE_ROLES)
def create_account():
    from flask import request

    body = request.get_json(silent=True) or {}
    username = str(body.get("username") or "").strip()
    name = str(body.get("name") or "").strip()
    role = body.get("role") or ROLE_AGENT

    if not username or not name:
        return jsonify(code=400, msg="请填写登录账号与姓名"), 400
    if role not in (ROLE_DEVELOPER, ROLE_ADMIN, ROLE_AGENT):
        return jsonify(code=400, msg="角色不合法"), 400
    if role == ROLE_DEVELOPER and request.current_user.role != ROLE_DEVELOPER:
        return jsonify(code=403, msg="管理员不可创建开发者账号"), 403

    me = request.current_user
    if User.query.filter_by(username=username).first() is not None:
        log_action(AuditModule.ACCOUNT, "新增账号", f"账号 {username} · {name}",
                   result=AuditLog.RESULT_FAIL, detail="登录账号已存在")
        return jsonify(code=400, msg=f"登录账号 {username} 已存在"), 400

    org, err = _resolve_org(body.get("org_id"), role)
    if err:
        return err

    user = User(username=username, name=name, role=role,
                org_id=org.id if org else None,
                password_hash=generate_password_hash(INITIAL_PASSWORD),
                must_change_password=1)  # 初始密码，登录后强制改密
    db.session.add(user)
    db.session.flush()  # 先拿 id，绑定设备失败时好回滚整笔

    err = _sync_devices(user, body, me)
    if err:
        db.session.rollback()
        return err

    db.session.commit()
    detail = f"角色 {role}" + (f" · 组织 {org.name}" if org else "")
    log_action(AuditModule.ACCOUNT, "新增账号", _target(user), detail=detail)
    return jsonify(code=0, msg="success", data=user.to_json(with_devices=True))


@bp.put("/api/accounts/<int:user_id>")
@require_role(*MANAGE_ROLES)
def update_account(user_id):
    """编辑：姓名（developer/admin 都可以）；设备绑定仅 developer。"""
    from flask import request

    user = db.session.get(User, user_id)
    if user is None:
        return jsonify(code=404, msg="账号不存在"), 404

    me = request.current_user
    if not _manageable(me, user):
        log_action(AuditModule.ACCOUNT, "编辑账号", _target(user),
                   result=AuditLog.RESULT_FAIL, detail="管理员无权操作开发者账号")
        return jsonify(code=403, msg="管理员无权操作开发者账号"), 403

    body = request.get_json(silent=True) or {}
    name = str(body.get("name") or "").strip()
    if not name:
        return jsonify(code=400, msg="请填写姓名"), 400

    changed = []
    if name != user.name:
        user.name = name
        changed.append("姓名")

    if "org_id" in body:  # 编辑可改组织；未提供则保持不变
        org, err = _resolve_org(body.get("org_id"), user.role)
        if err:
            return err
        new_org_id = org.id if org else None
        if new_org_id != user.org_id:
            user.org_id = new_org_id
            changed.append("组织")

    err = _sync_devices(user, body, me)
    if err:
        db.session.rollback()
        return err

    db.session.commit()
    log_action(AuditModule.ACCOUNT, "编辑账号", _target(user),
               detail="、".join(changed) or "无变更")
    return jsonify(code=0, msg="success", data=user.to_json(with_devices=True))


@bp.put("/api/accounts/<int:user_id>/status")
@require_role(*MANAGE_ROLES)
def toggle_status(user_id):
    """启用 / 停用。不能停用自己；admin 不能操作 developer 行。"""
    from flask import request

    user = db.session.get(User, user_id)
    if user is None:
        return jsonify(code=404, msg="账号不存在"), 404

    me = request.current_user
    if user.id == me.id:
        log_action(AuditModule.ACCOUNT, "变更账号状态", _target(user),
                   result=AuditLog.RESULT_FAIL, detail="不能停用当前登录账号")
        return jsonify(code=400, msg="不能停用当前登录账号"), 400
    if not _manageable(me, user):
        log_action(AuditModule.ACCOUNT, "变更账号状态", _target(user),
                   result=AuditLog.RESULT_FAIL, detail="管理员无权操作开发者账号")
        return jsonify(code=403, msg="管理员无权操作开发者账号"), 403

    body = request.get_json(silent=True) or {}
    status = body.get("status")
    if status not in (STATUS_ON, STATUS_OFF):
        return jsonify(code=400, msg="status 仅支持 1启用 / 0停用"), 400

    user.status = status
    db.session.commit()
    log_action(AuditModule.ACCOUNT, "启用账号" if status == STATUS_ON else "停用账号", _target(user))
    return jsonify(code=0, msg="success", data=user.to_json(with_devices=True))


@bp.put("/api/accounts/<int:user_id>/password")
@require_role(*MANAGE_ROLES)
def reset_password(user_id):
    """重置为初始密码。"""
    from flask import request

    user = db.session.get(User, user_id)
    if user is None:
        return jsonify(code=404, msg="账号不存在"), 404

    me = request.current_user
    if not _manageable(me, user):
        log_action(AuditModule.ACCOUNT, "重置密码", _target(user),
                   result=AuditLog.RESULT_FAIL, detail="管理员无权操作开发者账号")
        return jsonify(code=403, msg="管理员无权操作开发者账号"), 403

    user.password_hash = generate_password_hash(INITIAL_PASSWORD)
    user.must_change_password = 1  # 重置回初始密码，下次登录强制改密
    db.session.commit()
    log_action(AuditModule.ACCOUNT, "重置密码", _target(user))
    return jsonify(code=0, msg="success")


def _parse_devices(body):
    """解析 body.devices → [(openid, remark), ...]；格式非法返回 None。

    兼容两种写法：["openid", ...] 或 [{"openid": "...", "remark": "..."}, ...]。
    """
    raw = body.get("devices")
    if raw is None:
        return []
    if not isinstance(raw, list) or len(raw) > _MAX_DEVICES:
        return None
    parsed = []
    for item in raw:
        if isinstance(item, str):
            openid, remark = item, ""
        elif isinstance(item, dict):
            openid, remark = str(item.get("openid") or "").strip(), str(item.get("remark") or "").strip()
        else:
            return None
        if not openid or len(openid) > 64 or len(remark) > 64:
            return None
        parsed.append((openid, remark))
    return parsed


def _sync_devices(user, body, me):
    """同步绑定设备列表（仅 developer 可配置）；body 无 devices 字段=不动绑定。

    规则：openid 全局唯一（别的账号绑了就拒）、单次列表内不重复；
    已有绑定保持原 id（绑定顺序不变），新设备按传入顺序追加，删除不在列表里的。
    成功返回 None，失败返回 (json, code)。
    """
    parsed = _parse_devices(body)
    if parsed is None:
        return jsonify(code=400, msg=f"devices 须为 openid 数组（≤{_MAX_DEVICES}台，含 64 字内备注）"), 400
    if "devices" not in body:
        return None  # 编辑姓名等场景不带 devices，不视为清空绑定

    openids = [openid for openid, _ in parsed]
    if len(set(openids)) != len(openids):
        log_action(AuditModule.ACCOUNT, "绑定微信设备", _target(user),
                   result=AuditLog.RESULT_FAIL, detail="设备列表内有重复")
        return jsonify(code=400, msg="设备列表内有重复"), 400

    if openids != user_openids(user.id) and me.role != ROLE_DEVELOPER:
        log_action(AuditModule.ACCOUNT, "绑定微信设备", _target(user),
                   result=AuditLog.RESULT_FAIL, detail="微信设备绑定仅开发者可配置")
        return jsonify(code=403, msg="微信设备绑定仅开发者可配置"), 403

    occupied = UserDevice.query.filter(
        UserDevice.openid.in_(openids), UserDevice.user_id != user.id,
    ).all()
    if occupied:
        other = occupied[0]
        other_user = db.session.get(User, other.user_id)
        log_action(AuditModule.ACCOUNT, "绑定微信设备", _target(user),
                   result=AuditLog.RESULT_FAIL, detail=f"设备 {other.openid} 已绑定 {_target(other_user)}")
        return jsonify(
            code=400, msg=f"设备 {other.openid} 已绑定 {other_user.username}（{other_user.name}）"
        ), 400

    current = {d.openid: d for d in user_devices(user.id)}
    for openid, d in current.items():
        if openid not in openids:  # 列表里没有 = 解除绑定
            db.session.delete(d)
    for openid, remark in parsed:  # 已有保持顺序，新增按传入顺序追加
        row = current.get(openid)
        if row is None:
            db.session.add(UserDevice(user_id=user.id, openid=openid, remark=remark or None))
        elif (row.remark or "") != remark:
            row.remark = remark or None
    return None
