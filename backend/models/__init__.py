"""数据库模型统一导出：方便 import，也让 create_all 能发现所有表。"""
from backend.models.base import SoftDeleteMixin
from backend.models.contact_profile import ContactProfile
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.models.send_task import SendTask
from backend.models.sync_cursor import SyncCursor

__all__ = ["SoftDeleteMixin", "ContactProfile", "Conversation", "Message", "SendTask", "SyncCursor"]
