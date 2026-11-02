"""access_log 入站接口调用日志表模型（规范见 docs/interface-log.md）。"""
from backend.extensions import db
from backend.models.base import BigIntPK


class AccessLog(db.Model):
    """入站访问流水：Flask 钩子自动写入，业务代码禁止手写。

    user_name / org_name 存快照而非外键——账号停用后历史仍可读（与 audit_log 同款）。
    只插入，不更新不删除（唯一例外：过期清理任务）。
    """

    __tablename__ = "access_log"

    id = db.Column(BigIntPK, primary_key=True, autoincrement=True)
    access_time = db.Column(db.DateTime, nullable=False, comment="访问时间")
    user_id = db.Column(BigIntPK, comment="登录账号 id；空=未登录接口")
    user_name = db.Column(db.String(64), nullable=False, default="", comment="操作人姓名快照")
    org_id = db.Column(BigIntPK, comment="所属组织 id；空=未登录/开发者跨组织")
    org_name = db.Column(db.String(64), nullable=False, default="", comment="组织名快照")
    path = db.Column(db.String(255), nullable=False, comment="请求路径")
    method = db.Column(db.String(16), nullable=False, comment="请求方法 GET/POST等")
    url = db.Column(db.Text, nullable=False, comment="完整请求url（token 参数已打码）")
    ip = db.Column(db.String(64), nullable=False, comment="客户端IP")
    user_agent = db.Column(db.Text, comment="UA客户端标识")
    args = db.Column(db.Text, comment="GET参数json(脱敏)")
    form = db.Column(db.Text, comment="POST参数json(脱敏)")
    status_code = db.Column(db.SmallInteger, nullable=False, comment="响应HTTP状态码")
    duration_ms = db.Column(db.Integer, nullable=False, default=0, comment="服务端耗时毫秒")
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    __table_args__ = (
        db.Index("idx_access_time", "access_time"),
        db.Index("idx_user", "user_id"),
        db.Index("idx_org", "org_id"),
        db.Index("idx_ip", "ip"),
        db.Index("idx_path", "path"),
    )

    def to_json(self):
        return {
            "id": self.id,
            "access_time": self.access_time.strftime("%Y-%m-%d %H:%M:%S") if self.access_time else None,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "org_id": self.org_id,
            "org_name": self.org_name,
            "path": self.path,
            "method": self.method,
            "url": self.url,
            "ip": self.ip,
            "user_agent": self.user_agent or "",
            "args": self.args or "",
            "form": self.form or "",
            "status_code": self.status_code,
            "duration_ms": self.duration_ms,
        }
