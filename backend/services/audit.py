"""审计日志唯一入口（规范见 docs/audit-log.md）。

全项目只允许通过 log_action 写日志，禁止在接口里手写 INSERT：
- operator 缺省自动取当前登录人（flask.g，由 require_role 装饰器写入）
- 定时任务 / 系统行为在无请求上下文时自动记「系统」
- result=fail 时 detail 必填
"""
from flask import current_app, has_request_context, request

from backend.extensions import db
from backend.models.audit_log import AuditLog


class AuditModule:
    """模块枚举：新功能先来这里加常量，禁止裸字符串。"""

    AUTH = "认证"          # 登录成功 / 登录失败
    ACCOUNT = "账号管理"    # 新增 / 编辑 / 启停用 / 重置密码 / 绑定微信设备
    CONTACT = "客户资料"    # 编辑电话 / 城市 / 标签 / 备注
    SYNC = "同步任务"       # 消息同步失败 / 发送确认失败（仅 fail）
    SYSTEM = "系统设置"     # 预留：接口配置变更（该功能后做）


def _current_operator():
    """从请求上下文取当前登录人；没有（定时任务）则记系统。"""
    if has_request_context():
        user = getattr(request, "current_user", None)
        if user is not None:
            return str(user.id), user.name, user.role
    return None, "系统", "system"


def _client_ip():
    if not has_request_context():
        return "127.0.0.1"
    return request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1").split(",")[0].strip()


def log_action(module, action, target, result=AuditLog.RESULT_SUCCESS, detail="", operator=None):
    """记一条审计日志。任何异常都不影响主业务（日志失败只打 app logger）。"""
    try:
        if result == AuditLog.RESULT_FAIL and not detail:
            detail = "未记录失败原因"  # 规范兜底：fail 必须有 detail

        if operator is not None:
            op_id, op_name, op_role = str(operator.id), operator.name, operator.role
        else:
            op_id, op_name, op_role = _current_operator()

        db.session.add(AuditLog(
            operator_id=op_id,
            operator_name=op_name[:64],
            role=op_role[:32],
            module=str(module)[:32],
            action=str(action)[:64],
            target=str(target)[:128],
            result=result,
            detail=str(detail)[:255] if detail else None,
            ip=_client_ip()[:64],
        ))
        db.session.commit()
    except Exception as exc:  # noqa: BLE001 日志写失败不拖垮业务
        db.session.rollback()
        current_app.logger.warning("审计日志写入失败: %s", exc)


def clean_expired_logs(days=180):
    """删除超过保留期的日志（每日定时任务调用；audit_log 唯一的 DELETE 场景）。"""
    from datetime import datetime, timedelta

    deadline = datetime.now() - timedelta(days=days)
    deleted = AuditLog.query.filter(AuditLog.created_at < deadline).delete()
    db.session.commit()
    return deleted
