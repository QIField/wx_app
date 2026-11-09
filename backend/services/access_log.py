"""入站接口日志唯一入口（规范见 docs/interface-log.md）。

由 app.py 的 Flask 钩子调用，业务代码禁止手写访问日志：
- 豁免清单不记录：/api/health、/ws、静态资源、OPTIONS 预检
- 敏感字段脱敏：password / token / authorization 类键值打码为 ***
- URL 中的 token 查询参数打码（媒体接口 token 在 URL 里）
- 写失败不阻断业务：整体 try/except，失败仅 app.logger.warning
"""
import json
import re
import time
from datetime import datetime, timedelta

from flask import current_app, g, has_request_context, request

from backend.extensions import db
from backend.models.access_log import AccessLog

# 豁免清单：健康检查、WebSocket、静态资源、预检请求
EXEMPT_PREFIXES = ("/api/health", "/ws", "/static/")
EXEMPT_METHODS = {"OPTIONS"}

# 命中任一子串的参数键做脱敏（不区分大小写）
SENSITIVE_KEYS = ("password", "token", "authorization")

# 文本列统一截断长度，避免超大载荷写库失败
MAX_TEXT = 2000

_URL_TOKEN_RE = re.compile(r"(token)=[^&]*", re.IGNORECASE)


def is_exempt(path, method):
    """豁免判定：命中清单不记入站日志（媒体接口不豁免，304 缓存命中照记）。"""
    if method.upper() in EXEMPT_METHODS:
        return True
    return path.startswith(EXEMPT_PREFIXES)


def mask_value(value):
    """递归脱敏：dict/list 里键名含敏感子串的值替换为 ***。"""
    if isinstance(value, dict):
        return {
            k: ("***" if any(s in str(k).lower() for s in SENSITIVE_KEYS) else mask_value(v))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [mask_value(v) for v in value]
    return value


def dumps_masked(payload):
    """参数转脱敏 JSON 字符串；解析失败或空返回空串。"""
    if not payload:
        return ""
    try:
        text = json.dumps(mask_value(payload), ensure_ascii=False, default=str)
    except Exception:  # noqa: BLE001 参数序列化失败不影响业务
        return ""
    return text[:MAX_TEXT]


def client_ip():
    """取客户端 IP：优先 X-Forwarded-For 第一段。

    全项目唯一的取 IP 实现（access_log / audit / risk 共用），
    无请求上下文（定时任务）时兜底 127.0.0.1。
    """
    if not has_request_context():
        return "127.0.0.1"
    forwarded = request.headers.get("X-Forwarded-For", "")
    return (forwarded.split(",")[0].strip() if forwarded else request.remote_addr) or "127.0.0.1"


def _current_user_snapshot():
    """从 request.current_user 取登录人快照；org 字段在 P2 接入后自动填充。"""
    user = getattr(request, "current_user", None)
    if user is None:
        return None, "", None, ""
    return user.id, user.name, getattr(user, "org_id", None), getattr(user, "org_name", "") or ""


def start_timer():
    """before_request 里记起点；结果挂在 g 上供 after_request 计算。"""
    g._access_log_start = datetime.now()
    g._access_log_t0 = time.perf_counter()


def _duration_ms():
    t0 = getattr(g, "_access_log_t0", None)
    return 0 if t0 is None else int((time.perf_counter() - t0) * 1000)


def record(response):
    """after_request 里记一条入站日志；豁免请求直接跳过。"""
    if not has_request_context() or is_exempt(request.path, request.method):
        return

    try:
        user_id, user_name, org_id, org_name = _current_user_snapshot()
        args = dumps_masked(request.args.to_dict(flat=True))
        form = dumps_masked(_request_payload())
        url = _URL_TOKEN_RE.sub(r"\1=***", request.url)

        db.session.add(AccessLog(
            access_time=getattr(g, "_access_log_start", None) or datetime.now(),
            user_id=user_id,
            user_name=user_name[:64],
            org_id=org_id,
            org_name=org_name[:64],
            path=request.path[:255],
            method=request.method[:16],
            url=url,
            ip=client_ip()[:64],
            user_agent=(request.headers.get("User-Agent") or "")[:MAX_TEXT],
            args=args,
            form=form,
            status_code=response.status_code,
            duration_ms=_duration_ms(),
        ))
        db.session.commit()
        g._access_logged = True
    except Exception as exc:  # noqa: BLE001 日志写失败不拖垮业务
        db.session.rollback()
        current_app.logger.warning("入站日志写入失败: %s", exc)


def record_crash(exc):
    """teardown_request 兜底：after_request 未跑（未处理异常）时补记 500。"""
    if not has_request_context() or getattr(g, "_access_logged", False):
        return
    if is_exempt(request.path, request.method):
        return
    try:
        user_id, user_name, org_id, org_name = _current_user_snapshot()
        db.session.add(AccessLog(
            access_time=getattr(g, "_access_log_start", None) or datetime.now(),
            user_id=user_id,
            user_name=user_name[:64],
            org_id=org_id,
            org_name=org_name[:64],
            path=request.path[:255],
            method=request.method[:16],
            url=_URL_TOKEN_RE.sub(r"\1=***", request.url),
            ip=client_ip()[:64],
            user_agent=(request.headers.get("User-Agent") or "")[:MAX_TEXT],
            args=dumps_masked(request.args.to_dict(flat=True)),
            form=dumps_masked(_request_payload()),
            status_code=500,
            duration_ms=_duration_ms(),
        ))
        db.session.commit()
    except Exception:  # noqa: BLE001 兜底日志自身再失败只回滚
        db.session.rollback()


def _request_payload():
    """取请求体参数：优先 JSON，其次表单；不含上传文件内容。"""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return None
    body = request.get_json(silent=True)
    if body is not None:
        return body
    return request.form.to_dict(flat=True) or None


def clean_expired(days=90):
    """删除超过保留期的入站日志（每日定时任务调用）。"""
    deadline = datetime.now() - timedelta(days=days)
    deleted = AccessLog.query.filter(AccessLog.access_time < deadline).delete()
    db.session.commit()
    return deleted
