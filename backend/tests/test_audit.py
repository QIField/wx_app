"""审计日志服务单测：唯一入口、系统兜底、fail 兜底、清理。"""
from datetime import datetime, timedelta

from backend.extensions import db
from backend.models.audit_log import AuditLog
from backend.services.audit import AuditModule, clean_expired_logs, log_action

from backend.tests.conftest import make_user


def test_log_action_defaults_to_current_user(app):
    """请求上下文里缺省取当前登录人（require_role 挂到 request 上）。"""
    from flask import request

    user = make_user(name="张客服")
    with app.test_request_context():
        request.current_user = user
        log_action(AuditModule.ACCOUNT, "新增账号", "cs09 · 李四")

    log = AuditLog.query.one()
    assert log.operator_id == str(user.id)
    assert log.operator_name == "张客服"
    assert log.role == "agent"
    assert log.result == "success"
    assert log.detail is None
    assert log.org_name is None  # 未分配组织：快照为空


def test_log_action_captures_org_snapshot(app):
    """姓名+组织快照规范：写入那一刻抄录登录人所属组织，不搞关联。"""
    from flask import request

    from backend.models.org import Org

    org = Org.query.filter_by(name="佛山").first() or Org(name="佛山")
    db.session.add(org)
    db.session.commit()
    user = make_user(name="张客服", org_id=org.id)
    with app.test_request_context():
        request.current_user = user
        log_action(AuditModule.ACCOUNT, "编辑账号", "cs02 · 王五")

    log = AuditLog.query.one()
    assert log.operator_name == "张客服"
    assert log.org_name == "佛山"


def test_log_action_system_when_no_request(app):
    """无请求上下文（定时任务）：记「系统」。"""
    with app.app_context():
        log_action(AuditModule.SYNC, "消息同步", "设备 dev01",
                   result=AuditLog.RESULT_FAIL, detail="设备离线")

    log = AuditLog.query.one()
    assert log.operator_name == "系统"
    assert log.role == "system"
    assert log.ip == "127.0.0.1"


def test_log_action_fail_requires_detail(app):
    """fail 没有 detail：兜底补「未记录失败原因」。"""
    with app.app_context():
        log_action(AuditModule.ACCOUNT, "停用账号", "cs01 · 张三",
                   result=AuditLog.RESULT_FAIL)

    log = AuditLog.query.one()
    assert log.detail == "未记录失败原因"


def test_log_action_truncates_long_fields(app):
    """超长字段截断，不让脏数据打爆建表长度。"""
    with app.app_context():
        log_action(AuditModule.AUTH, "登录" * 40, "t" * 300,
                   detail="d" * 500)

    log = AuditLog.query.one()
    assert len(log.action) <= 64
    assert len(log.target) <= 128
    assert len(log.detail) <= 255


def test_clean_expired_logs(app):
    """清理任务只删超过保留期的日志。"""
    with app.app_context():
        old = AuditLog(operator_id=None, operator_name="系统", role="system",
                       module="认证", action="登录", target="t", result="success",
                       created_at=datetime.now() - timedelta(days=181))
        fresh = AuditLog(operator_id=None, operator_name="系统", role="system",
                         module="认证", action="登录", target="t", result="success")
        db.session.add_all([old, fresh])
        db.session.commit()

        deleted = clean_expired_logs(days=180)

        assert deleted == 1
        assert AuditLog.query.count() == 1
