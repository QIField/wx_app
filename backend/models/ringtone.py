"""user_ringtone 用户自定义铃声：上传文件与账号关联，软删除。

展示名默认取原始文件主名；stored_name 是 uuid4 hex + 白名单扩展名，
播放走 /media/ringtones/<stored_name>（不鉴权，uuid 不可猜测）。
删除只打 deleted_at 标记，磁盘文件保留（软删除约定）。
"""
from backend.extensions import db
from backend.models.base import BigIntPK, SoftDeleteMixin


class UserRingtone(SoftDeleteMixin, db.Model):
    """用户上传的自定义提示音铃声。"""

    __tablename__ = "user_ringtone"

    id = db.Column(BigIntPK, primary_key=True, autoincrement=True)
    user_id = db.Column(BigIntPK, nullable=False, index=True, comment="归属系统账号")
    name = db.Column(db.String(64), nullable=False, comment="展示名（默认文件主名）")
    file_name = db.Column(db.String(255), nullable=False, comment="原始文件名")
    stored_name = db.Column(db.String(64), nullable=False, unique=True, comment="落盘文件名 uuidhex.ext")
    size = db.Column(db.Integer, nullable=False, comment="文件字节数")
    fmt = db.Column(db.String(10), nullable=False, comment="格式 mp3/m4a/wav/ogg")
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    def to_json(self):
        return {
            "id": self.id,
            "name": self.name,
            "file_name": self.file_name,
            "url": f"/media/ringtones/{self.stored_name}",
            "size": self.size,
            "fmt": self.fmt,
            "created_at": (
                self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None
            ),
        }
