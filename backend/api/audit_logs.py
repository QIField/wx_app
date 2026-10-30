"""审计日志查询 + 管理后台总览统计。

日志页面仅开发者可见（管理员也不可看）；总览统计 developer/admin 都可以看。
"""
from datetime import datetime

from flask import Blueprint, jsonify, request

from backend.extensions import db
from backend.models.audit_log import AuditLog
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.models.send_task import SendTask
from backend.models.user import ROLE_ADMIN, ROLE_AGENT, ROLE_DEVELOPER, User
from backend.services.auth import require_role

bp = Blueprint("audit_logs", __name__)


@bp.get("/api/audit-logs")
@require_role(ROLE_DEVELOPER)
def list_logs():
    """全量日志，?keyword= 对 动作/对象/操作人/模块 模糊过滤，新→旧。"""
    keyword = (request.args.get("keyword") or "").strip()
    q = AuditLog.query
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(db.or_(
            AuditLog.action.ilike(like),
            AuditLog.target.ilike(like),
            AuditLog.operator_name.ilike(like),
            AuditLog.module.ilike(like),
        ))
    rows = q.order_by(AuditLog.id.desc()).limit(500).all()
    return jsonify(code=0, msg="success", data={
        "list": [l.to_json() for l in rows],
        "total": len(rows),
    })


@bp.get("/api/admin/stats")
@require_role(ROLE_DEVELOPER, ROLE_ADMIN)
def admin_stats():
    """总览页四个指标：今日消息量 / 客服账号数 / 今日新增客户 / 发送成功率。"""
    today = datetime.now().strftime("%Y-%m-%d")

    msg_today = Message.query.filter(
        Message.deleted_at.is_(None),
        db.func.date(Message.create_time) == today,
    ).count()

    agents_total = User.query.filter_by(role=ROLE_AGENT).count()
    agents_on = User.query.filter(User.role == ROLE_AGENT, User.status == 1).count()

    new_customers = Conversation.query.filter(
        Conversation.deleted_at.is_(None),
        db.func.date(Conversation.created_at) == today,
    ).count()

    total = SendTask.query.filter(SendTask.deleted_at.is_(None),
                                  SendTask.status.in_((SendTask.ST_SUCCESS, SendTask.ST_FAILED))).count()
    ok = SendTask.query.filter(SendTask.deleted_at.is_(None),
                               SendTask.status == SendTask.ST_SUCCESS).count()
    rate = round(ok * 100 / total) if total else None

    return jsonify(code=0, msg="success", data={
        "msg_today": msg_today,
        "agents_total": agents_total,
        "agents_on": agents_on,
        "new_customers": new_customers,
        "success_rate": rate,
    })
