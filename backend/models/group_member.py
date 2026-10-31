"""群成员名册：chatroom_info.memberList 的本地镜像（昵称+头像，只读）。

消息表里 sender_name 存的是 wxid 原文（中间方不提供昵称），读取/广播时
关联本表实时解析昵称与头像——存库不回刷，成员改名立即生效。
"""
from backend.extensions import db
from backend.models.base import BigIntPK


class GroupMember(db.Model):
    __tablename__ = "group_member"

    id = db.Column(BigIntPK, primary_key=True, autoincrement=True)
    openid = db.Column(db.String(64), nullable=False, comment="中间方设备标识")
    chatroom_wxid = db.Column(db.String(64), nullable=False, comment="群ID")
    wxid = db.Column(db.String(64), nullable=False, comment="成员微信ID")
    nickname = db.Column(db.String(128), comment="成员昵称（群内显示名）")
    avatar = db.Column(db.String(512), comment="成员头像URL（brief_info 补拉）")
    updated_at = db.Column(
        db.DateTime, nullable=False, server_default=db.func.now(), onupdate=db.func.now()
    )

    __table_args__ = (
        db.UniqueConstraint("openid", "chatroom_wxid", "wxid", name="uk_group_member"),
        db.Index("idx_group_member_lookup", "openid", "chatroom_wxid"),
    )

    @property
    def display_name(self):
        return self.nickname or self.wxid
