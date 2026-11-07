"""通讯录同步：全量 wxid 入库（contact 表）+ 缺资料补齐。

与 profile_sync 的区别：群名/好友资料链路只给"已建会话"的联系人补资料，
本模块负责把中间方拉到的全量联系人记进名册（好友+群，公众号跳过），
否则没聊过天的联系人永远进不了通讯录。挂进 sync_profiles 兜底轮执行。

资料补齐复用现有解析：好友走 friend_profile.query_brief_infos（20/批），
群走 group_profile.query_chatroom_info（群数量少，同步等待即可）。
"""
from backend.adapter import client
from backend.extensions import db
from backend.models.contact import Contact
from backend.services.audit import AuditLog, AuditModule, log_action
from backend.services.devices import pollable_devices
from backend.sync import friend_profile, group_profile
from backend.sync.roster import reconcile
from backend.sync.task_query import as_dict, new_task_uuid, query_record, unwrap_result

FRIEND_PROFILE_BATCHES = 10  # 每轮最多补 10 批 brief_info（20/批），约 2 轮补齐 300 好友


def sync_contacts():
    """兜底轮入口：逐设备同步通讯录，任一设备失败不影响其他设备。

    已判定离线的设备跳过，等在线检测翻身自动恢复。
    """
    for openid in pollable_devices():
        try:
            sync_contacts_of_device(openid)
        except Exception as exc:  # noqa: BLE001
            db.session.rollback()
            log_action(AuditModule.SYNC, "通讯录同步", f"设备 {openid}",
                       result=AuditLog.RESULT_FAIL, detail=str(exc)[:255])


def sync_contacts_of_device(openid):
    """单台设备：拉 wxid 清单 → 入库 → 补资料。"""
    catalog = fetch_contact_wxids(openid)
    if not catalog:
        return
    upsert_contacts(openid, catalog)
    fill_missing_profiles(openid)


def fetch_contact_wxids(openid):
    """fetch_contacts_list_cache 下发 → 查询 → 好友/群 wxid 清单。

    2026-10-31 实测：friends/chatrooms 都是纯字符串数组；ghs（公众号）
    按需求不入通讯录，直接丢弃。用 cache 版减轻设备负担。
    """
    task_uuid = new_task_uuid()
    client.call("contacts_api", "fetch_contacts_list_cache", {}, task_uuid, openid=openid)
    record = query_record("contacts_api", "get_fetch_contacts_list_cache", task_uuid, openid)
    data_raw = unwrap_result(record)
    if data_raw is None:
        return {}
    data = as_dict(data_raw)
    return {
        "friends": _clean_wxids(data.get("friends")),
        "chatrooms": _clean_wxids(data.get("chatrooms")),
    }


def _clean_wxids(items):
    return [w for w in (items or []) if isinstance(w, str) and w]


def upsert_contacts(openid, catalog):
    """全量名册对齐：新增插入、重新出现复活、消失的标记 deleted_at。

    只有拿到非空清单时才做“消失”判定——中间方偶发返回空列表
    不能把整份通讯录误判为全删。
    """
    plan = [
        (Contact.TYPE_FRIEND, catalog.get("friends") or []),
        (Contact.TYPE_GROUP, catalog.get("chatrooms") or []),
    ]
    types = {wxid: ctype for ctype, wxids in plan for wxid in wxids}
    if not types:
        return
    existing = {c.wxid: c for c in Contact.query.filter_by(openid=openid).all()}
    created, changed = reconcile(existing, list(types))
    for wxid in created:
        db.session.add(Contact(openid=openid, wxid=wxid, type=types[wxid]))
    if created or changed:
        db.session.commit()


def fill_missing_profiles(openid):
    """补昵称头像：好友批量 brief_info，群逐个 chatroom_info。"""
    _fill_friends(openid)
    _fill_groups(openid)


def _fill_friends(openid):
    """缺资料好友批量补：每轮最多 FRIEND_PROFILE_BATCHES 批，剩余下轮继续。"""
    for _ in range(FRIEND_PROFILE_BATCHES):
        rows = (
            Contact.query.filter(
                Contact.openid == openid,
                Contact.type == Contact.TYPE_FRIEND,
                Contact.deleted_at.is_(None),
                db.or_(Contact.name.is_(None), Contact.name == "", Contact.avatar.is_(None)),
            )
            .limit(friend_profile.FRIEND_BATCH)
            .all()
        )
        if not rows:
            return
        infos = friend_profile.query_brief_infos([c.wxid for c in rows], openid)
        changed = False
        for c in rows:  # 不能用 any()：会短路，漏掉本批其余联系人
            if _apply_info(c, infos.get(c.wxid) or {}):
                changed = True
        if not changed:
            return  # 整批拿不到资料（如中间方失败）：别空转烧完批数
        db.session.commit()


def _fill_groups(openid):
    """缺资料群逐个补：群数量少（个位数），同步等待收割即可。"""
    rows = Contact.query.filter(
        Contact.openid == openid,
        Contact.type == Contact.TYPE_GROUP,
        Contact.deleted_at.is_(None),
        db.or_(Contact.name.is_(None), Contact.name == "", Contact.avatar.is_(None)),
    ).all()
    for c in rows:
        info = group_profile.query_chatroom_info(c.wxid, openid) or {}
        if _apply_info(c, info):
            db.session.commit()


def _apply_info(c, info):
    """昵称/头像补到联系人（头像字段兼容好友 head_img_url 与群 avatar 两种来源）。

    与 friend_profile.apply_friend_info / group_profile.apply_group_info
    同一套规则：昵称只在未解析时覆盖，头像只补不覆盖。有变更返回 True。
    """
    changed = False
    if info.get("nickname") and c.name in (None, "", c.wxid):
        c.name = info["nickname"]
        changed = True
    avatar = info.get("head_img_url") or info.get("avatar")
    if avatar and not c.avatar:
        c.avatar = avatar
        changed = True
    return changed
