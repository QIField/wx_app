"""微信侧通讯录：设备绑定的全量联系人（好友/群，公众号不进通讯录）。

数据来自中间方 fetch_contacts_list（wxid 清单）+ brief_info/chatroom_info
补资料，只读镜像（不写回微信）。与会话表互相独立：会话只在有消息往来时
才建，通讯录要收录没聊过天的联系人，所以单独建表。
"""
from backend.extensions import db
from backend.models.base import BigIntPK


class Contact(db.Model):
    TYPE_FRIEND = 1  # 好友
    TYPE_GROUP = 2   # 群聊
    TYPE_GH = 3      # 公众号（同步时跳过，不入库）

    __tablename__ = "contact"

    id = db.Column(BigIntPK, primary_key=True, autoincrement=True)
    openid = db.Column(db.String(64), nullable=False, comment="中间方设备标识")
    wxid = db.Column(db.String(64), nullable=False, comment="微信ID（个人或群ID）")
    type = db.Column(db.SmallInteger, nullable=False, comment="1好友 2群 3公众号")
    name = db.Column(db.String(128), comment="昵称/群名（未解析时为空，显示用 wxid 兜底）")
    avatar = db.Column(db.String(512), comment="头像URL")
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime, nullable=False, server_default=db.func.now(), onupdate=db.func.now()
    )

    __table_args__ = (
        db.UniqueConstraint("openid", "wxid", name="uk_contact_openid_wxid"),
    )
