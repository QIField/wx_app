"""联系人业务档案：备注/标签。

业务自建数据（与微信侧只读数据分离），按 wxid 关联，好友与群通用；
仅存本系统数据库，不写回微信。
"""
from backend.extensions import db


class ContactProfile(db.Model):
    __tablename__ = "contact_profile"

    # 业务约束（接口层据此校验）
    MAX_REMARK_LEN = 100
    MAX_TAGS = 10
    MAX_TAG_LEN = 12

    id = db.Column(db.Integer, primary_key=True)
    wxid = db.Column(db.String(64), unique=True, nullable=False, index=True)
    remark = db.Column(db.String(100), nullable=False, default="")
    tags = db.Column(db.JSON, nullable=False, default=list)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    def to_json(self):
        return {"remark": self.remark or "", "tags": list(self.tags or [])}
