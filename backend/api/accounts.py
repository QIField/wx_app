"""账号管理 API：列表 / 新增 / 编辑 / 启停用 / 重置密码。

权限规则（已确认）：
- developer：全部操作，含微信设备绑定（open_id）与创建任意角色
- admin：可管理账号，但不可操作 developer 行、不可创建 developer、不可绑定设备
- 所有写操作记审计日志，业务规则拒绝也记 fail
"""
from flask import Blueprint, jsonify, request
from werkzeug.security import generate_password_hash

from backend.extensions import db
from backend.models.user import (
    ROLE_ADMIN,
    ROLE_AGENT,
    ROLE_DEVELOPER,
    STATUS_OFF,
    STATUS_ON,
    User,
)
from backend.services.audit import AuditLog, AuditModule, log_action
from backend.services.auth import require_role

bp = Blueprint("accounts", __name__)

INITIAL_PASSWORD = "123456"  # 新增/重置的初始密码
_MANAGE_ROLES = (ROLE_DEVELOPER, ROLE_ADMIN)


def _target(user):
    """审计日志的对象格式：账号 · 姓名（能唯一定位）。"""
    return f"{user.username} · {user.name}"


def _manageable(me, target_user):
    """admin 不可操作 developer 行。"""
    return me.role == ROLE_DEVELOPER or target_user.role != ROLE_DEVELOPER


@bp.get("/api/accounts")
@require_role(*_MANAGE_ROLES)
def list_accounts():
    rows = User.query.order_by(User.role.desc(), User.id).all()
    return jsonify(code=0, msg="success", data=[u.to_json(with_openid=True) for u in rows])


@bp.post("/api/accounts")
@require_role(*_MANAGE_ROLES)
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

    user = User(username=username, name=name, role=role,
                password_hash=generate_password_hash(INITIAL_PASSWORD),
                must_change_password=1)  # 初始密码，登录后强制改密
    db.session.add(user)
    db.session.flush()  # 先拿 id，绑定设备失败时好回滚整笔

    err = _bind_openid(user, str(body.get("open_id") or "").strip(), me)
    if err:
        db.session.rollback()
        return err

    db.session.commit()
    log_action(AuditModule.ACCOUNT, "新增账号", _target(user), detail=f"角色 {role}")
    return jsonify(code=0, msg="success", data=user.to_json(with_openid=True))


@bp.put("/api/accounts/<int:user_id>")
@require_role(*_MANAGE_ROLES)
def update_account(user_id):
    """编辑：姓名（developer/admin 都可以）；open_id 仅 developer。"""
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

    err = _bind_openid(user, str(body.get("open_id") or "").strip(), me)
    if err:
        db.session.rollback()
        return err

    db.session.commit()
    log_action(AuditModule.ACCOUNT, "编辑账号", _target(user),
               detail="、".join(changed) or "无变更")
    return jsonify(code=0, msg="success", data=user.to_json(with_openid=True))


@bp.put("/api/accounts/<int:user_id>/status")
@require_role(*_MANAGE_ROLES)
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
    return jsonify(code=0, msg="success", data=user.to_json(with_openid=True))


@bp.put("/api/accounts/<int:user_id>/password")
@require_role(*_MANAGE_ROLES)
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


def _bind_openid(user, open_id, me):
    """绑定微信设备（仅 developer 可配置）；developer 传空 = 解除绑定。

    值没变化时直接放行（管理员编辑姓名时 UI 会原样带回旧值，不算越权）。
    成功返回 None，失败返回 (json, code)。
    """
    if open_id == (user.open_id or ""):
        return None
    if me.role != ROLE_DEVELOPER:
        log_action(AuditModule.ACCOUNT, "绑定微信设备", _target(user),
                   result=AuditLog.RESULT_FAIL, detail="微信设备绑定仅开发者可配置")
        return jsonify(code=403, msg="微信设备绑定仅开发者可配置"), 403

    if not open_id:  # developer 显式清空 = 解除绑定
        user.open_id = None
        return None

    occupied = User.query.filter(User.open_id == open_id, User.id != user.id).first()
    if occupied is not None:
        log_action(AuditModule.ACCOUNT, "绑定微信设备", _target(user),
                   result=AuditLog.RESULT_FAIL, detail=f"该微信设备已绑定 {_target(occupied)}")
        return jsonify(code=400, msg=f"该微信设备已绑定 {occupied.username}（{occupied.name}）"), 400

    user.open_id = open_id
    return None
