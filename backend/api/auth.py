"""认证 API：登录 + 当前用户信息 + 自助修改密码。"""
from flask import Blueprint, current_app, g, jsonify, request

from backend.models.audit_log import AuditLog
from backend.services.audit import AuditModule, log_action
from backend.services.auth import (
    change_password,
    create_token,
    login_user,
    require_role,
)

bp = Blueprint("auth", __name__)

_CHANGE_ACTIONS = {
    "旧密码错误": "旧密码错误",
    "新密码至少 6 位": "新密码不合规（不足 6 位）",
    "新密码不能与旧密码相同": "新密码与旧密码相同",
}


@bp.post("/api/auth/login")
def login():
    """登录：三连校验（存在→密码→启用）都在 login_user 里完成并记审计日志。"""
    body = request.get_json(silent=True) or {}
    username = str(body.get("username") or "").strip()
    password = str(body.get("password") or "")
    if not username or not password:
        return jsonify(code=400, msg="请输入账号和密码"), 400

    user, err = login_user(username, password)
    if err:
        return jsonify(code=401, msg=err), 401

    token, expires_in = create_token(user)

    # 已绑定设备则异步投递一次增量资料同步；入队失败不影响登录
    from backend.sync import profile_jobs

    try:
        profile_jobs.enqueue_login_sync(current_app._get_current_object(), user)
    except Exception:  # noqa: BLE001
        current_app.logger.warning("登录资料同步入队失败", exc_info=True)

    return jsonify(code=0, msg="success", data={
        "token": token,
        "expires_in": expires_in,
        "user": user.to_json(with_openid=True),
    })


@bp.get("/api/auth/me")
@require_role(allow_must_change=True)
def me():
    """当前登录人：前端刷新页面时用它恢复会话。"""
    return jsonify(code=0, msg="success", data=g.current_user.to_json(with_openid=True))


@bp.put("/api/auth/password")
@require_role(allow_must_change=True)
def change_my_password():
    """自助修改密码：旧密码 + 新密码；强制改密期唯一放行的业务接口。"""
    body = request.get_json(silent=True) or {}
    old_password = str(body.get("old_password") or "")
    new_password = str(body.get("new_password") or "")

    user = g.current_user
    target = f"账号 {user.username} · {user.name}"
    err = change_password(user, old_password, new_password)
    if err:
        log_action(AuditModule.AUTH, "修改密码", target,
                   result=AuditLog.RESULT_FAIL, detail=_CHANGE_ACTIONS.get(err, err))
        return jsonify(code=400, msg=err), 400

    log_action(AuditModule.AUTH, "修改密码", target)
    return jsonify(code=0, msg="success", data=user.to_json(with_openid=True))
