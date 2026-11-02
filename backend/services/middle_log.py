"""出站中间方调用日志唯一入口（规范见 docs/interface-log.md）。

由 adapter/client（全项目对中间方唯一出口）调用，业务代码禁止手写：
- 四类场景全落库：成功 / HTTP 异常 / 业务 code!=0 / 非 JSON
- ret 单独成列：查询类接口 processing_result.ret（如 500 设备已离线）
- success：code=0 且非异常且 ret∈(None,200) 为 1，其余为 0
- 写失败不阻断业务：整体 try/except，失败仅 app.logger.warning
"""
import json
from contextvars import ContextVar
from datetime import datetime, timedelta

from flask import current_app, has_app_context, has_request_context, request

from backend.extensions import db
from backend.models.middle_call_log import MiddleCallLog
from backend.services.access_log import mask_value
from backend.services.user_snapshot import current_user as _snapshot_user, org_of

MAX_TEXT = 2000

# 定时任务触发时由 sync 入口设置 job 名；请求上下文内自动改用请求路径
_job_source: ContextVar = ContextVar("middle_log_job_source", default="")


def set_job_source(name):
    """定时任务入口设置触发来源（如 confirm_worker / message_sync）。"""
    _job_source.set(name)


def _trigger_source():
    """触发来源：请求上下文取请求路径；定时任务取 job 名。"""
    if has_request_context():
        return request.path[:64]
    return _job_source.get()[:64]


def _current_user():
    """当前登录人 (id, 姓名, 组织) 快照；定时任务/无登录人返回 (None, '', None)。"""
    user = _snapshot_user()
    if user is None:
        return None, "", None
    return user.id, user.name, org_of(user)


def first_result(body):
    """查询接口 data 第一项的 processing_result（解析为 dict；没有返回 None）。"""
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, list) or not data:
        return None
    item = data[0] if isinstance(data[0], dict) else {}
    result = item.get("processing_result")
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except ValueError:
            return None
    return result if isinstance(result, dict) else None


def decide_success(resp_code, ret):
    """成功判定：code=0 且 ret∈(None,200)；ret!=200（设备离线等）算失败。"""
    if resp_code != 0:
        return 0
    return 1 if ret in (None, 200) else 0


def log_call(module, action, *, uuid="", openid="", params=None, trigger_source="",
             http_status=None, resp_code=None, ret=None, response_body="",
             duration_ms=0, success=1, error_msg=""):
    """记一条出站调用日志。任何异常都不影响主业务；无应用上下文时直接跳过。"""
    if not has_app_context():
        return
    try:
        user_id, user_name, org_name = _current_user()
        db.session.add(MiddleCallLog(
            call_time=datetime.now(),
            trigger_source=(trigger_source or _trigger_source())[:64],
            user_id=user_id,
            user_name=user_name[:64] if user_name else None,
            org_name=org_name[:64] if org_name else None,
            module=str(module)[:32],
            action=str(action)[:64],
            uuid=str(uuid or "")[:64],
            openid=str(openid or "")[:64],
            request_params=_dumps(params),
            http_status=http_status,
            resp_code=resp_code,
            ret=ret,
            response_body=str(response_body or "")[:MAX_TEXT],
            duration_ms=int(duration_ms),
            success=success,
            error_msg=str(error_msg or "")[:255] or None,
        ))
        db.session.commit()
    except Exception as exc:  # noqa: BLE001 日志写失败不拖垮业务
        db.session.rollback()
        if current_app:
            current_app.logger.warning("出站日志写入失败: %s", exc)


def _dumps(payload):
    """参数转脱敏 JSON 字符串；序列化失败兜底 repr，统一截断。"""
    if not payload:
        return ""
    try:
        text = json.dumps(mask_value(payload), ensure_ascii=False, default=str)
    except Exception:  # noqa: BLE001
        text = repr(payload)
    return text[:MAX_TEXT]


def clean_expired(days=90):
    """删除超过保留期的出站日志（每日定时任务调用）。"""
    deadline = datetime.now() - timedelta(days=days)
    deleted = MiddleCallLog.query.filter(MiddleCallLog.call_time < deadline).delete()
    db.session.commit()
    return deleted
