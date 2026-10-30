"""audit_log 操作日志表模型（规范见 docs/audit-log.md）。"""
from backend.extensions import db
from backend.models.base import BigIntPK


class AuditLog(db.Model):
    """审计日志：只插入，不更新不删除（唯一例外：过期清理任务）。

    operator_name / role 存快照而非外键——账号停用后历史仍可读。
    """

    RESULT_SUCCESS = "success"
    RESULT_FAIL = "fail"

    __tablename__ = "audit_log"

    id = db.Column(BigIntPK, primary_key=True, autoincrement=True)
    operator_id = db.Column(db.String(64), comment="操作人账号 id；空 = 系统自动任务")
    operator_name = db.Column(db.String(64), nullable=False, comment="操作时姓名快照")
    role = db.Column(db.String(32), nullable=False, comment="操作时角色快照 developer/admin/agent/system")
    module = db.Column(db.String(32), nullable=False, comment="模块枚举，见 services/audit.py")
    action = db.Column(db.String(64), nullable=False, comment="动宾结构，如「重置密码」")
    target = db.Column(db.String(128), nullable=False, comment="能唯一定位对象，如「cs05 · 吴桐」")
    result = db.Column(db.String(16), nullable=False, default=RESULT_SUCCESS, comment="success/fail")
    detail = db.Column(db.String(255), comment="失败原因或补充信息；result=fail 时必填")
    ip = db.Column(db.String(64), comment="来源 IP；系统任务记 127.0.0.1")
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    __table_args__ = (
        db.Index("idx_created_at", "created_at"),
        db.Index("idx_module", "module"),
    )

    def to_json(self):
        return {
            "id": self.id,
            "operator_name": self.operator_name,
            "role": self.role,
            "module": self.module,
            "action": self.action,
            "target": self.target,
            "result": self.result,
            "detail": self.detail or "",
            "ip": self.ip or "",
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }
