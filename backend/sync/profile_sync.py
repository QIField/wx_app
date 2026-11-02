"""资料同步门面：编排通讯录入库、群资料、好友资料链路（公共入口保持稳定）。

四条链路：
- 通讯录同步（contact_sync）：全量 wxid 入 contact 表 + 缺资料补齐，
  通讯录列表（没聊过天的联系人）就靠它进库；
- 兜底扫描（30 分钟一轮）：sync_profiles 全量找缺资料的会话补拉；
- 登录触发（sync_device_full）：对登录账号绑定的设备执行一次全量四步，
  与兜底轮共用同一队列，按设备串行，不会并发；
- 立即补拉（refresh_missing_profiles）：收消息轮询发现新消息涉及的会话
  缺资料时当场同步拉取，前端几秒内就能看到名称头像，不用等兜底轮。

实现拆分：contact_sync.py（通讯录名册）、group_profile.py（群名/群头像，
两段流水线）、friend_profile.py（好友昵称/头像，批量 brief_info）、
task_query.py（uuid 下发/查询/结果解包共享工具）。
"""
from backend.extensions import db
from backend.models.conversation import Conversation
from backend.services.audit import AuditLog, AuditModule, log_action
from backend.sync import contact_sync, friend_profile, group_member, group_profile
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
        try:
            refresh_group_member_avatars(app)
        except Exception as exc:  # noqa: BLE001
            app.logger.warning("群成员头像补拉失败: %s", exc)


def refresh_group_member_avatars(app):
    """群成员头像兜底补拉：逐设备补缺额，有更新就广播前端刷新。"""
    from backend.services.devices import active_bound_devices
    from backend.sync import group_member

    for openid in active_bound_devices():
        try:
            if group_member.refresh_avatars_of_device(openid):
                db.session.commit()
                from backend.ws import hub

                hub.broadcast("conv_updated", {"reason": "group_member_avatars"})
        except Exception as exc:  # noqa: BLE001 单设备失败不影响其他设备
            db.session.rollback()
            app.logger.warning("群成员头像补拉失败(设备 %s): %s", openid, exc)


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


def sync_device_full(openid):
    """登录触发的单设备全量资料同步：复刻 30 分钟兜底轮四条链路，只作用于该设备。

    顺序：通讯录全量入库+补资料 → 群资料收割+补发 → 好友列表+补资料 → 群成员头像补额。
    单步失败只记审计，不阻断后续步骤；与兜底轮共用同一队列，不会并发。
    """
    _safe_step(openid, "通讯录同步",
               lambda: contact_sync.sync_contacts_of_device(openid))
    _safe_step(openid, "群资料解析", lambda: _sync_device_groups(openid))
    _safe_step(openid, "好友资料解析",
               lambda: friend_profile.sync_friend_profiles_of_device(openid))
    _safe_step(openid, "群成员头像补拉",
               lambda: _refresh_device_member_avatars(openid))


def _sync_device_groups(openid):
    """单设备群资料：收割该设备上轮结果 + 补发该设备缺失群（结果下轮收割）。"""
    group_profile.collect_group_results(openid=openid)
    group_profile.dispatch_group_tasks(openid=openid)


def _refresh_device_member_avatars(openid):
    """补该设备缺头像的群成员；有更新才提交并广播。"""
    if group_member.refresh_avatars_of_device(openid):
        db.session.commit()
        from backend.ws import hub

        hub.broadcast("conv_updated", {"reason": "group_member_avatars"})


def _safe_step(openid, action, fn):
    """单设备链路单步容错：失败回滚并记审计，后续步骤继续。"""
    from flask import current_app

    current_app.logger.info("资料同步步骤: %s (设备 %s)", action, openid)
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        log_action(AuditModule.SYNC, action, f"设备 {openid}",
                   result=AuditLog.RESULT_FAIL, detail=str(exc)[:255])
