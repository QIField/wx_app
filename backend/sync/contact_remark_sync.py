"""中间方 remark 同步到 ContactRemarkConfig：好友 scope=user，群 scope=group。

原则：只补空、不覆盖（用户手动编辑优先级最高）。
空值跳过（中间方返回 None 或 "" 都不写，避免用空串覆盖已有值）。
不触发审计日志——系统同步不是用户操作，手动编辑仍走 API 层的审计。
"""
from backend.extensions import db
from backend.models.contact_remark_config import (
    SCOPE_GROUP,
    SCOPE_USER,
    ContactRemarkConfig,
)


def upsert_remark(scope, target_wxid, remark):
    """中间方 remark → ContactRemarkConfig.remark_name。

    返回 True 表示写了（新增或补了空值），False 表示有值跳过或 remark 本身为空。
    不 commit——调用方按既有事务统一提交（好友/群资料链路都是批量 commit）。
    """
    if not remark or not str(remark).strip():
        return False
    remark = str(remark).strip()
    row = ContactRemarkConfig.query.filter_by(
        scope_type=scope, target_wxid=target_wxid
    ).first()
    if row is None:
        row = ContactRemarkConfig(scope_type=scope, target_wxid=target_wxid, remark_name=remark)
        db.session.add(row)
        return True
    # restore 已软删行（跟 API 层保持一致）
    row.restore()
    if not row.remark_name:  # 已有非空 = 用户手动编辑过，跳过
        row.remark_name = remark
        return True
    return False


def upsert_user_remark(wxid, remark):
    """好友/成员 → scope=user 备注。"""
    return upsert_remark(SCOPE_USER, wxid, remark)


def upsert_group_remark(chatroom_wxid, remark):
    """群 → scope=group 备注。"""
    return upsert_remark(SCOPE_GROUP, chatroom_wxid, remark)
