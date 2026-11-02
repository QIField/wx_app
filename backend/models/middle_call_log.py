"""middle_call_log 出站中间方调用日志表模型（规范见 docs/interface-log.md）。"""
from backend.extensions import db
from backend.models.base import BigIntPK


class MiddleCallLog(db.Model):
    """出站调用流水：adapter/client 唯一出口自动写入，业务代码禁止手写。

    uuid 与 SendTask.uuid 同源，发送闭环按 uuid 串联追踪。
    success：code=0 且非异常且 ret∈(None,200) 为 1，其余为 0。
    只插入，不更新不删除（唯一例外：过期清理任务）。
    """

    __tablename__ = "middle_call_log"

    id = db.Column(BigIntPK, primary_key=True, autoincrement=True)
    call_time = db.Column(db.DateTime, nullable=False, comment="调用时间")
    trigger_source = db.Column(
        db.String(64), nullable=False, default="",
        comment="触发来源：请求路径或定时任务job名",
    )
    user_id = db.Column(BigIntPK, comment="发起用户(请求上下文)；定时任务为空")
    module = db.Column(db.String(32), nullable=False, comment="send_api/messag_api/login_api等")
    action = db.Column(db.String(64), nullable=False, comment="如 post_text_message")
    uuid = db.Column(db.String(64), nullable=False, default="", comment="本次调用唯一标识，串联下发与确认")
    openid = db.Column(db.String(64), nullable=False, default="", comment="设备标识")
    request_params = db.Column(db.Text, comment="请求参数json(脱敏)")
    http_status = db.Column(db.SmallInteger, comment="HTTP状态码；网络异常为空")
    resp_code = db.Column(db.Integer, comment="中间方业务code")
    ret = db.Column(db.Integer, comment="processing_result.ret；仅查询类有")
    response_body = db.Column(db.Text, comment="原始响应(截断2000字符)")
    duration_ms = db.Column(db.Integer, nullable=False, default=0, comment="耗时毫秒")
    success = db.Column(db.SmallInteger, nullable=False, default=1, comment="1成功 0失败")
    error_msg = db.Column(db.String(255), comment="失败原因")
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    __table_args__ = (
        db.Index("idx_call_time", "call_time"),
        db.Index("idx_uuid", "uuid"),
        db.Index("idx_action", "module", "action"),
        db.Index("idx_success", "success"),
    )

    def to_json(self):
        return {
            "id": self.id,
            "call_time": self.call_time.strftime("%Y-%m-%d %H:%M:%S") if self.call_time else None,
            "trigger_source": self.trigger_source,
            "user_id": self.user_id,
            "module": self.module,
            "action": self.action,
            "uuid": self.uuid,
            "openid": self.openid,
            "request_params": self.request_params or "",
            "http_status": self.http_status,
            "resp_code": self.resp_code,
            "ret": self.ret,
            "response_body": self.response_body or "",
            "duration_ms": self.duration_ms,
            "success": self.success,
            "error_msg": self.error_msg or "",
        }
