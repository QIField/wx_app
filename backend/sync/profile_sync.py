"""资料同步门面：编排通讯录入库、群资料、好友资料三条链路（公共入口保持稳定）。

三条链路：
- 通讯录同步（contact_sync）：全量 wxid 入 contact 表 + 缺资料补齐，
  通讯录列表（没聊过天的联系人）就靠它进库；
- 兜底扫描（30 分钟一轮）：sync_profiles 全量找缺资料的会话补拉；
- 立即补拉（refresh_missing_profiles）：收消息轮询发现新消息涉及的会话
  缺资料时当场同步拉取，前端几秒内就能看到名称头像，不用等兜底轮。

实现拆分：contact_sync.py（通讯录名册）、group_profile.py（群名/群头像，
两段流水线）、friend_profile.py（好友昵称/头像，批量 brief_info）、
task_query.py（uuid 下发/查询/结果解包共享工具）。
"""
from backend.extensions import db
from backend.models.conversation import Conversation
from backend.services.audit import AuditLog, AuditModule, log_action
from backend.sync import contact_sync, friend_profile, group_profile
from backend.sync.group_profile import missing_profile


def sync_profiles(app):
    """定时任务入口：先通讯录，再群名，再好友资料，互不影响（各自 try）。"""
    with app.app_context():
        try:
            contact_sync.sync_contacts()
        except Exception as exc:  # noqa: BLE001 一轮失败不拖垮整个调度
            app.logger.warning("通讯录同步失败: %s", exc)
        try:
            group_profile.sync_group_names()
        except Exception as exc:  # noqa: BLE001
            app.logger.warning("群名解析失败: %s", exc)
        try:
            friend_profile.sync_friend_profiles()
        except Exception as exc:  # noqa: BLE001
            app.logger.warning("好友资料解析失败: %s", exc)


def refresh_missing_profiles(openid, conv_ids):
    """收消息轮询触发：本轮新消息涉及的会话若缺资料，立即同步补拉。

    与兜底扫描同口径判定缺资料；群限 GROUP_NOW_LIMIT 个/轮、失败计数复用
    group_profile._fail_counts、已下发流水线中的群跳过。失败只记审计不抛出，
    不影响收消息。
    """
    ids = list(dict.fromkeys(conv_ids))  # 去重保序：同一会话多条消息只查一次
    if not ids:
        return
    convs = (
        Conversation.query.filter(
            Conversation.id.in_(ids),
            Conversation.openid == openid,
            Conversation.deleted_at.is_(None),
        )
        .all()
    )
    missing = [c for c in convs if missing_profile(c)]
    groups = [c for c in missing if c.chat_type == Conversation.CHAT_GROUP]
    singles = [c for c in missing if c.chat_type != Conversation.CHAT_GROUP]
    try:
        group_profile.refresh_groups_now(openid, groups)
    except Exception as exc:  # noqa: BLE001 补拉失败不影响收消息主链路
        db.session.rollback()
        log_action(AuditModule.SYNC, "群资料补拉", f"设备 {openid}",
                   result=AuditLog.RESULT_FAIL, detail=str(exc)[:255])
    try:
        friend_profile.refresh_singles_now(openid, singles)
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        log_action(AuditModule.SYNC, "好友资料补拉", f"设备 {openid}",
                   result=AuditLog.RESULT_FAIL, detail=str(exc)[:255])
