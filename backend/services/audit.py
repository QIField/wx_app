"""审计日志唯一入口（规范见 docs/audit-log.md）。

全项目只允许通过 log_action 写日志，禁止在接口里手写 INSERT：
- operator 缺省自动取当前登录人（flask.g，由 require_role 装饰器写入）
- 定时任务 / 系统行为在无请求上下文时自动记「系统」
- result=fail 时 detail 必填
"""
from flask import current_app

from backend.extensions import db
from backend.models.audit_log import AuditLog
from backend.services.access_log import client_ip
from backend.services.user_snapshot import current_user, org_of


class AuditModule:
    """模块枚举：新功能先来这里加常量，禁止裸字符串。"""

    AUTH = "认证"          # 登录成功 / 登录失败
    ACCOUNT = "账号管理"    # 新增 / 编辑 / 启停用 / 重置密码 / 绑定微信设备
    DEVICE = "设备管理"     # 新增 / 编辑 / 删除设备字典（仅开发者）
    ORG = "组织管理"        # 新增组织 / 停用（软删除）组织 / 恢复组织
    CONTACT = "客户资料"    # 编辑电话 / 城市 / 标签 / 备注
    SYNC = "同步任务"       # 消息同步失败 / 发送确认失败（仅 fail）
    SYSTEM = "系统设置"     # 预留：接口配置变更（该功能后做）


def _current_operator():
    """当前登录人（含角色与组织快照）；没有（定时任务）则记系统。"""
    user = current_user()
    if user is not None:
        return str(user.id), user.name, user.role, org_of(user)
    return None, "系统", "system", None


def log_action(module, action, target, result=AuditLog.RESULT_SUCCESS, detail="", operator=None):
    """记一条审计日志。任何异常都不影响主业务（日志失败只打 app logger）。"""
    try:
        if result == AuditLog.RESULT_FAIL and not detail:
            detail = "未记录失败原因"  # 规范兜底：fail 必须有 detail

        if operator is not None:
            op_id = str(operator.id)
            op_name, op_role = operator.name, operator.role
            op_org = org_of(operator)
        else:
            op_id, op_name, op_role, op_org = _current_operator()

        db.session.add(AuditLog(
            operator_id=op_id,
            operator_name=op_name[:64],
            org_name=op_org[:64] if op_org else None,
            role=op_role[:32],
            module=str(module)[:32],
            action=str(action)[:64],
            target=str(target)[:128],
            result=result,
            detail=str(detail)[:255] if detail else None,
            ip=client_ip()[:64],
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
