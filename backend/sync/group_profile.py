"""群资料解析：群名 + 群头像（两段流水线）。

本轮收割上一轮下发的结果（结果早已生成，秒级命中）+ 给缺资料的群补发
新任务，不同步等待中间方（结果约 4 秒内生成）。消息触发的立即补拉链路
（refresh_groups_now）由 profile_sync 门面编排，失败计数/流水线状态共享。
"""
from backend.adapter import client
from backend.extensions import db
from backend.models.conversation import Conversation
from backend.sync import group_member
from backend.sync.task_query import (
    as_dict,
    new_task_uuid,
    pick,
    query_record,
    query_record_once,
    unwrap_result,
)
from backend.ws.hub import broadcast

PROFILE_BATCH = 100   # 每轮最多下发 100 个群资料任务（下发很快；结果下轮收割）
MAX_FAIL_RETRY = 5    # 同一个 wxid 连续失败 5 次后放弃（进程重启清零）
GROUP_NOW_LIMIT = 3   # 消息触发的立即补拉：单轮最多同步等 3 个群（防阻塞收消息轮询）
GROUP_NOW_RETRIES = 10  # 立即补拉同步等待预算：10 次 × 2 秒 = 20 秒（实测延迟波动大）

_fail_counts = {}    # (openid, wxid) -> 连续失败次数（内存即可）
_pending = {}        # task_uuid -> (conversation_id, wxid, openid)：已下发待收割的群资料任务
_pending_fails = {}  # task_uuid -> 收割失败轮数（超 5 轮丢弃，防永久占坑）


def missing_profile(conv):
    """资料是否缺失：群名/头像缺失，或群聊的成员名册还没落库。

    成员名册（group_member）是消息发言人昵称/头像的数据源，所以
    "资料看起来齐全但名册为空"的群也要算缺资料，触发 chatroom_info 补拉。
    """
    if conv.name in (None, "", conv.wxid) or not conv.avatar:
        return True
    if conv.chat_type != Conversation.CHAT_GROUP:
        return False
    from backend.models.group_member import GroupMember

    has_members = (
        db.session.query(GroupMember.id)
        .filter_by(openid=conv.openid, chatroom_wxid=conv.wxid)
        .first()
        is not None
    )
    return not has_members


def sync_group_names():
    collect_group_results()
    dispatch_group_tasks()


def collect_group_results(openid=None):
    """收割上一轮下发的任务：结果早已生成，单次查询即命中。

    openid 传入时只收割该设备的任务（登录增量路径），缺省收割全部。
    """
    done = []
    for task_uuid, (conv_id, wxid, dev_openid) in _pending.items():
        if openid and dev_openid != openid:
            continue
        record = query_record_once("group_api", "get_chatroom_info", task_uuid, dev_openid)
        if not record:
            _pending_fails[task_uuid] = _pending_fails.get(task_uuid, 0) + 1
            if _pending_fails[task_uuid] >= 5:
                # 连续 5 轮没收割到：放弃并计入群失败数（限流，防止重复下发死循环）
                _fail_counts[(dev_openid, wxid)] = _fail_counts.get((dev_openid, wxid), 0) + 1
                done.append(task_uuid)
            continue
        done.append(task_uuid)
        info = parse_group_info(record)
        if info:
            apply_group_info(conv_id, wxid, info)
    for task_uuid in done:
        _pending.pop(task_uuid, None)
        _pending_fails.pop(task_uuid, None)


def dispatch_group_tasks(openid=None):
    """给缺资料且未在下发中的群补发 chatroom_info 任务（按会话所属设备下发）。

    openid 传入时只处理该设备的群（登录全量路径），缺省处理全部。
    """
    pending_wxids = {(dev_openid, wxid) for _, wxid, dev_openid in _pending.values()}
    slots = PROFILE_BATCH - len(_pending)
    if slots <= 0:
        return
    for conv in unnamed_groups(limit=slots, openid=openid):
        key = (conv.openid, conv.wxid)
        if key in pending_wxids:
            continue
        if _fail_counts.get(key, 0) >= MAX_FAIL_RETRY:
            continue
        task_uuid = new_task_uuid()
        client.call("group_api", "chatroom_info", {"chatroom_id": conv.wxid},
                    task_uuid, openid=conv.openid or "")
        _pending[task_uuid] = (conv.id, conv.wxid, conv.openid)


def unnamed_groups(limit, openid=None):
    """需要补群资料的会话：缺名称/头像，或群成员名册还没落库（两来源合并去重）。"""
    rooms = []
    seen = set()

    def _collect(rows):
        for conv in rows:
            if conv.id not in seen:
                seen.add(conv.id)
                rooms.append(conv)

    _collect(_name_missing_groups(limit, openid))
    if len(rooms) < limit:
        _collect(_members_missing_groups(limit - len(rooms), openid))
    return rooms[:limit]


def _name_missing_groups(limit, openid=None):
    """没有名字的群会话（name 为空或还显示着 wxid 原始编号）。"""
    query = Conversation.query.filter(
        Conversation.deleted_at.is_(None),
        Conversation.chat_type == Conversation.CHAT_GROUP,
        db.or_(Conversation.name.is_(None), Conversation.name == Conversation.wxid),
    )
    if openid:
        query = query.filter(Conversation.openid == openid)
    return (
        query
        # MySQL 5.7 不支持 NULLS LAST，用 IS NULL 布尔排序两端方言通吃（空值排最后）
        .order_by(
            Conversation.last_msg_at.is_(None),
            Conversation.last_msg_at.desc(),
            Conversation.id,
        )
        .limit(limit)
        .all()
    )


def _members_missing_groups(limit, openid=None):
    """成员名册为空的群会话（发言人昵称/头像的数据源）。"""
    from backend.models.group_member import GroupMember

    filters = [
        Conversation.deleted_at.is_(None),
        Conversation.chat_type == Conversation.CHAT_GROUP,
        GroupMember.id.is_(None),
    ]
    if openid:
        filters.append(Conversation.openid == openid)
    return (
        Conversation.query.outerjoin(
            GroupMember,
            db.and_(
                GroupMember.openid == Conversation.openid,
                GroupMember.chatroom_wxid == Conversation.wxid,
            ),
        )
        .filter(*filters)
        .order_by(
            Conversation.last_msg_at.is_(None),
            Conversation.last_msg_at.desc(),
            Conversation.id,
        )
        .limit(limit)
        .all()
    )


def refresh_groups_now(openid, groups):
    """立即补拉群资料：同步下发 + 等待收割，单轮最多 GROUP_NOW_LIMIT 个。"""
    pending_keys = {(o, w) for _, w, o in _pending.values()}
    done = 0
    for conv in groups:
        if done >= GROUP_NOW_LIMIT:
            break  # 超出的留给 30 分钟兜底轮，避免阻塞收消息轮询
        key = (conv.openid, conv.wxid)
        if key in pending_keys or _fail_counts.get(key, 0) >= MAX_FAIL_RETRY:
            continue
        done += 1  # 按尝试次数计数：失败也占用本轮名额
        task_uuid = new_task_uuid()
        client.call("group_api", "chatroom_info", {"chatroom_id": conv.wxid},
                    task_uuid, openid=conv.openid or "")
        record = query_record("group_api", "get_chatroom_info", task_uuid, openid,
                              retries=GROUP_NOW_RETRIES)
        if record is None:
            _fail_counts[key] = _fail_counts.get(key, 0) + 1
            continue
        info = parse_group_info(record)
        if info:
            apply_group_info(conv.id, conv.wxid, info)
            _refresh_member_avatars_now(conv)  # 名册刚落，立即补头像避免等兜底轮
        else:
            # 已出结果但 ret != 200：接口真实失败，计入失败数交给限流/兜底
            _fail_counts[key] = _fail_counts.get(key, 0) + 1


def _refresh_member_avatars_now(conv):
    """消息触发路径：收割完单群名册后立即补该群成员头像（一次批量约 4 秒）。

    每群最多 20 人/次，超出的与失败都留给 30 分钟兜底轮，不阻塞收消息。
    """
    try:
        if group_member.refresh_avatars_of_device(conv.openid, chatroom_wxid=conv.wxid):
            db.session.commit()
            broadcast("conv_updated", {"conversation_id": conv.id})
    except Exception:  # noqa: BLE001 补头像失败不影响收消息主链路
        db.session.rollback()


def apply_group_info(conv_id, wxid, info):
    conv = db.session.get(Conversation, conv_id)
    if not conv:
        return
    changed = False
    if info.get("nickname"):
        conv.name = info["nickname"]
        changed = True
    if info.get("avatar") and not conv.avatar:
        conv.avatar = info["avatar"]
        changed = True
    # memberList 顺带落群成员名册（消息展示靠它解析发言人昵称）
    if info.get("members") and group_member.save_members(conv.openid, wxid, info["members"]):
        changed = True
    if changed:
        db.session.commit()
        _fail_counts.pop((conv.openid, conv.wxid), None)
        broadcast("conv_updated", {"conversation_id": conv.id})


def parse_group_info(record):
    """任务记录 → {nickname, avatar, members}。

    2026-10-30 实测 processing_result.data：
    nickName=群名, smallHeadImgUrl=群头像,
    memberList=成员（wxid+nickName；头像为空，走 brief_info 补拉）。
    """
    data_raw = unwrap_result(record)
    if data_raw is None:
        return None
    data = as_dict(data_raw)
    members = []
    for row in data.get("memberList") or []:
        if isinstance(row, dict) and row.get("wxid"):
            members.append({"wxid": row["wxid"], "nickname": pick(row, ("nickName", "nickname", "displayName"))})
    return {
        "nickname": pick(data, ("nickName", "nickname", "chatroom_name", "name")),
        "avatar": pick(data, ("smallHeadImgUrl", "bigHeadImgUrl", "head_img_url", "avatar")),
        "members": members,
    }


def query_chatroom_info(chatroom_id, openid=""):
    """同步取单个群资料（仅临时调试用；正式链路走两段流水线）。"""
    task_uuid = new_task_uuid()
    client.call("group_api", "chatroom_info", {"chatroom_id": chatroom_id},
                task_uuid, openid=openid)
    record = query_record("group_api", "get_chatroom_info", task_uuid, openid)
    return parse_group_info(record)
