"""认证与鉴权：登录令牌签发/校验 + require_role 接口装饰器。

令牌用 itsdangerous 签名（Flask 自带，无新依赖），载荷只放 user_id，
每次校验都回库取最新状态——停用/改密即时生效，不需要黑名单。
"""
from functools import wraps

from flask import g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from backend.config import SECRET_KEY, TOKEN_EXPIRE_HOURS
from backend.extensions import db
from backend.models.user import User

_TOKEN_SALT = "auth"


def _serializer():
    return URLSafeTimedSerializer(SECRET_KEY, salt=_TOKEN_SALT)


def create_token(user):
    """签发令牌：载荷只有 user_id，有效期见 config.TOKEN_EXPIRE_HOURS。"""
    return _serializer().dumps({"uid": user.id}), TOKEN_EXPIRE_HOURS * 3600


def _load_token_user(token):
    """令牌 → 用户；无效/过期/已停用都返回 None。"""
    try:
        payload = _serializer().loads(token, max_age=TOKEN_EXPIRE_HOURS * 3600)
    except (BadSignature, SignatureExpired):
        return None
    user = db.session.get(User, payload.get("uid"))
    if user is None or not user.enabled:
        return None
    return user


def bearer_token():
    """从请求头取 Bearer 令牌，没有返回空串。"""
    header = request.headers.get("Authorization", "")
    return header[7:] if header.startswith("Bearer ") else ""


def request_user():
    """当前请求的登录人；未登录/令牌无效返回 None（供不便加装饰器的接口用）。"""
    token = bearer_token()
    return _load_token_user(token) if token else None


def user_from_token(token):
    """令牌 → 用户：给 <img>/<audio>/<video> 等带不了请求头的资源地址用 ?token= 校验。

    只应在媒体这类资源端点里兜底使用；令牌会出现在 URL 里，注意别记进日志。
    """
    return _load_token_user(token) if token else None


def must_change_guard(user):
    """初始密码强制改密门控：未改密返回拦截响应，已改密返回 None。

    前端凭 err=PASSWORD_CHANGE_REQUIRED 弹强制改密窗，防止绕过前端直接调业务接口。
    """
    if user is not None and user.must_change_password:
        return jsonify(code=403, msg="请先修改初始密码再使用系统",
                       err="PASSWORD_CHANGE_REQUIRED"), 403
    return None


def change_password(user, old_password, new_password):
    """自助修改密码：校验旧密码与新密码规则，成功清除强制改密标记。

    返回 None 表示成功；失败返回原因文案（调用方负责记审计日志）。
    """
    from werkzeug.security import check_password_hash, generate_password_hash

    if not check_password_hash(user.password_hash, old_password or ""):
        return "旧密码错误"
    if len(new_password or "") < 6:
        return "新密码至少 6 位"
    if new_password == old_password:
        return "新密码不能与旧密码相同"

    user.password_hash = generate_password_hash(new_password)
    user.must_change_password = 0
    db.session.commit()
    return None


def login_user(username, password):
    """登录三连校验：存在 → 密码 → 启用。返回 (user, 失败原因)；成功原因为 None。"""
    from werkzeug.security import check_password_hash

    from backend.models.audit_log import AuditLog
    from backend.services.audit import AuditModule, log_action

    user = User.query.filter_by(username=username).first()
    if user is None:
        log_action(AuditModule.AUTH, "登录", f"账号 {username}",
                   result=AuditLog.RESULT_FAIL, detail="账号不存在")
        return None, "账号或密码错误"
    if not check_password_hash(user.password_hash, password or ""):
        log_action(AuditModule.AUTH, "登录", f"账号 {username} · {user.name}",
                   result=AuditLog.RESULT_FAIL, detail="密码错误", operator=user)
        return None, "账号或密码错误"
    if not user.enabled:
        log_action(AuditModule.AUTH, "登录", f"账号 {username} · {user.name}",
                   result=AuditLog.RESULT_FAIL, detail="账号已停用", operator=user)
        return None, "账号已停用，请联系管理员"

    from datetime import datetime

    user.last_login_at = datetime.now()
    db.session.commit()
    log_action(AuditModule.AUTH, "登录", f"账号 {username} · {user.name}", operator=user)
    return user, None


def require_role(*roles, allow_must_change=False):
    """接口鉴权：Authorization: Bearer <token>。

    - 令牌无效/过期/已停用 → 401
    - 角色不在白名单 → 403
    - 仍是初始密码且 allow_must_change=False → 403 强制改密拦截
    - 通过后挂 g.current_user 和 request.current_user（审计日志取操作人用）
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            header = request.headers.get("Authorization", "")
            token = header[7:] if header.startswith("Bearer ") else ""
            user = _load_token_user(token) if token else None
            if user is None:
                return jsonify(code=401, msg="登录已失效，请重新登录"), 401
            if roles and user.role not in roles:
                return jsonify(code=403, msg="没有权限执行此操作"), 403
            blocked = must_change_guard(user)
            if blocked is not None and not allow_must_change:
                return blocked
            g.current_user = user
            request.current_user = user
            return fn(*args, **kwargs)
        return wrapper
    return decorator
