"""中间方 remark 同步到 ContactRemarkConfig：好友 scope=user，群 scope=group。

原则：只补空、不覆盖（用户手动编辑优先级最高）。
空值跳过（中间方返回 None 或 "" 都不写，避免用空串覆盖已有值）。
不触发审计日志——系统同步不是用户操作，手动编辑仍走 API 层的审计。

设备维度（2026-11-25）：同步时必须带 conv.openid 精确落到该设备的行。
同一联系人在不同设备上各有独立 ContactRemarkConfig 行，sync 不能串设备。
"""
from backend.extensions import db
from backend.models.contact_remark_config import (
    SCOPE_GROUP,
    SCOPE_USER,
    ContactRemarkConfig,
)


def upsert_remark(scope, target_wxid, remark, openid=None):
    """中间方 remark → ContactRemarkConfig.remark_name。

    返回 True 表示写了（新增或补了空值），False 表示有值跳过或 remark 本身为空。
    不 commit——调用方按既有事务统一提交（好友/群资料链路都是批量 commit）。
    """
    if not remark or not str(remark).strip():
        return False
    remark = str(remark).strip()

    # 先找 openid 精确命中的行；没找到再 fallback 旧行（openid=NULL 兼容过渡）
    q = ContactRemarkConfig.query.filter_by(scope_type=scope, target_wxid=target_wxid)
    row = q.filter(ContactRemarkConfig.openid == openid).first() if openid else None
    if row is None:
        row = q.filter(ContactRemarkConfig.openid.is_(None)).first()

    if row is None:
        row = ContactRemarkConfig(scope_type=scope, target_wxid=target_wxid, remark_name=remark, openid=openid)
        db.session.add(row)
        return True
    # restore 已软删行（跟 API 层保持一致）
    row.restore()
    # 存量行 openid 可能是 NULL（迁移前的数据），补上
    if openid and not row.openid:
        row.openid = openid
    if not row.remark_name:  # 已有非空 = 用户手动编辑过，跳过
        row.remark_name = remark
        return True
    return False


def upsert_user_remark(wxid, remark, openid=None):
    """好友/成员 → scope=user 备注。"""
    return upsert_remark(SCOPE_USER, wxid, remark, openid)


def upsert_group_remark(chatroom_wxid, remark, openid=None):
    """群 → scope=group 备注。"""
    return upsert_remark(SCOPE_GROUP, chatroom_wxid, remark, openid)
