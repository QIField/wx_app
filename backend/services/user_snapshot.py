"""当前登录人快照的公共取法（姓名+组织快照规范，见 docs/audit-log.md 第六节）。

audit_log / middle_call_log / access_log 等记录「人」的服务统一从这里取，
保证「从哪拿登录人、组织怎么取」全项目只有一份。
"""
from flask import has_request_context, request


def current_user():
    """请求上下文中的当前登录人；无（定时任务/系统行为）返回 None。"""
    if has_request_context():
        return getattr(request, "current_user", None)
    return None


def org_of(user):
    """用户组织名快照；未绑组织返回 None。getattr 兼容无该属性的测试替身。"""
    return getattr(user, "org_name", None) if user is not None else None
