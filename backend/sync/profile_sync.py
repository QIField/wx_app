"""会话资料解析：群名 + 好友昵称/头像（10 分钟一轮的低频后台任务）。

和收消息同套路：uuid 下发任务 → get_ 查询 processing_result。
字段名以防万一做成多候选取值（真实返回结构联调时校准，见 _pick）。
"""
import uuid as uuid_lib

from backend.adapter import client
from backend.extensions import db
from backend.models.conversation import Conversation
from backend.ws.hub import broadcast

PROFILE_BATCH = 100          # 每轮最多下发 100 个群资料任务（下发很快；结果下轮收割）
QUERY_RETRY = 5               # 同步查询时的重试次数（好友列表用；群任务改为两段式无需等待）
QUERY_WAIT_SECONDS = 2        # 每次重试间隔（实测约 4 秒内出结果）
MAX_FAIL_RETRY = 5            # 同一个 wxid 连续失败 5 次后放弃（进程重启清零）
FRIEND_BATCH = 20             # brief_info 单次最多 20 个 wxid（文档约定）

_fail_counts = {}    # wxid -> 连续失败次数（内存即可）
_pending = {}        # task_uuid -> (conversation_id, wxid)：已下发待收割的群资料任务
_pending_fails = {}  # task_uuid -> 收割失败轮数（超 5 轮丢弃，防永久占坑）


def sync_profiles(app):
    """定时任务入口：先群名，再好友资料，互不影响（各自 try）。

    群资料采用两段流水线：本轮收割上一轮下发的结果（秒级）+ 给缺资料的群补发新任务。
    """
    with app.app_context():
        try:
            _sync_group_names()
        except Exception as exc:  # noqa: BLE001 一轮失败不拖垮整个调度
            app.logger.warning("群名解析失败: %s", exc)
        try:
            _sync_friend_profiles()
        except Exception as exc:  # noqa: BLE001
            app.logger.warning("好友资料解析失败: %s", exc)


# ---------- 群名 ----------

def _unnamed_groups(limit):
    """没有名字的群会话（name 为空或还显示着 wxid 原始编号）。"""
    return (
        Conversation.query.filter(
            Conversation.deleted_at.is_(None),
            Conversation.chat_type == Conversation.CHAT_GROUP,
            db.or_(Conversation.name.is_(None), Conversation.name == Conversation.wxid),
        )
        # MySQL 5.7 不支持 NULLS LAST，用 IS NULL 布尔排序两端方言通吃（空值排最后）
        .order_by(
            Conversation.last_msg_at.is_(None),
            Conversation.last_msg_at.desc(),
            Conversation.id,
        )
        .limit(limit)
        .all()
    )


def _sync_group_names():
    _collect_group_results()
    _dispatch_group_tasks()


def _collect_group_results():
    """收割上一轮下发的任务：结果早已生成，单次查询即命中。"""
    done = []
    for task_uuid, (conv_id, wxid) in _pending.items():
        record = _query_record_once("group_api", "get_chatroom_info", task_uuid)
        if not record:
            _pending_fails[task_uuid] = _pending_fails.get(task_uuid, 0) + 1
            if _pending_fails[task_uuid] >= 5:
                # 连续 5 轮没收割到：放弃并计入群失败数（限流，防止重复下发死循环）
                _fail_counts[wxid] = _fail_counts.get(wxid, 0) + 1
                done.append(task_uuid)
            continue
        done.append(task_uuid)
        info = _parse_group_info(record)
        if info:
            _apply_group_info(conv_id, wxid, info)
    for task_uuid in done:
        _pending.pop(task_uuid, None)
        _pending_fails.pop(task_uuid, None)


def _dispatch_group_tasks():
    """给缺资料且未在下发中的群补发 chatroom_info 任务。"""
    pending_wxids = {wxid for _, wxid in _pending.values()}
    slots = PROFILE_BATCH - len(_pending)
    if slots <= 0:
        return
    for conv in _unnamed_groups(limit=slots):
        if conv.wxid in pending_wxids:
            continue
        if _fail_counts.get(conv.wxid, 0) >= MAX_FAIL_RETRY:
            continue
        task_uuid = _new_task_uuid()
        client.call("group_api", "chatroom_info", {"chatroom_id": conv.wxid}, task_uuid)
        _pending[task_uuid] = (conv.id, conv.wxid)


def _apply_group_info(conv_id, wxid, info):
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
    if changed:
        db.session.commit()
        _fail_counts.pop(wxid, None)
        broadcast("conv_updated", {"conversation_id": conv.id})


def _new_task_uuid():
    return str(uuid_lib.uuid4())


def _query_record(module, get_action, task_uuid):
    """查询下发结果（带间隔重试，供好友列表等同步场景用；群任务收割不用它等）。

    实测（2026-10-29）：data 是任务记录数组，每条含 uuid + processing_result；
    结果不是立即生成（约 4 秒内）。
    """
    import time

    for i in range(QUERY_RETRY):
        row = _query_record_once(module, get_action, task_uuid)
        if row:
            return row
        if i < QUERY_RETRY - 1:
            time.sleep(QUERY_WAIT_SECONDS)
    return None


def _query_record_once(module, get_action, task_uuid):
    """单次查询，不重试。返回本 uuid 的任务记录或 None。"""
    body = client.call(module, get_action, {}, uuid=task_uuid)
    rows = body.get("data") if isinstance(body, dict) else None
    if isinstance(rows, dict):
        rows = rows.get("list") or []
    if not isinstance(rows, list):
        return None
    for row in rows:
        if isinstance(row, dict) and row.get("uuid") == task_uuid:
            return row
    return None


def _parse_group_info(record):
    """任务记录 → {nickname, avatar}。

    2026-10-30 实测 processing_result.data：
    nickName=群名, smallHeadImgUrl=群头像, memberList=成员(含昵称，后续接)。
    """
    if not record:
        return None
    result = _as_dict(record.get("processing_result"))
    if result.get("ret") != 200:
        return None
    data = _as_dict(result.get("data"))
    return {
        "nickname": _pick(data, ("nickName", "nickname", "chatroom_name", "name")),
        "avatar": _pick(data, ("smallHeadImgUrl", "bigHeadImgUrl", "head_img_url", "avatar")),
    }


def _query_chatroom_info(chatroom_id):
    """同步取单个群资料（仅临时调试用；正式链路走两段流水线）。"""
    task_uuid = _new_task_uuid()
    client.call("group_api", "chatroom_info", {"chatroom_id": chatroom_id}, task_uuid)
    record = _query_record("group_api", "get_chatroom_info", task_uuid)
    return _parse_group_info(record)


# ---------- 好友昵称/头像 ----------

def _sync_friend_profiles():
    """拉好友列表 → 对"已建单聊会话且缺资料"的好友批量查 brief_info。"""
    friend_wxids = _fetch_friend_wxids()
    if not friend_wxids:
        return
    targets = (
        Conversation.query.filter(
            Conversation.deleted_at.is_(None),
            Conversation.chat_type == Conversation.CHAT_SINGLE,
            Conversation.wxid.in_(friend_wxids),
            db.or_(
                Conversation.name.is_(None),
                Conversation.name == Conversation.wxid,
                Conversation.avatar.is_(None),
            ),
        )
        .limit(FRIEND_BATCH)
        .all()
    )
    if not targets:
        return
    infos = _query_brief_infos([c.wxid for c in targets])
    for conv in targets:
        info = infos.get(conv.wxid)
        if not info:
            continue
        changed = False
        if info.get("nickname") and (conv.name in (None, conv.wxid)):
            conv.name = info["nickname"]
            changed = True
        if info.get("head_img_url") and not conv.avatar:
            conv.avatar = info["head_img_url"]
            changed = True
        if changed:
            db.session.commit()
            broadcast("conv_updated", {"conversation_id": conv.id})


def _fetch_friend_wxids():
    """fetch_contacts_list 下发 → 查询 → friends wxid 列表（2026-10-29 实测）。"""
    task_uuid = _new_task_uuid()
    client.call("contacts_api", "fetch_contacts_list", {}, task_uuid)
    record = _query_record("contacts_api", "get_fetch_contacts_list", task_uuid)
    if not record:
        return []
    result = _as_dict(record.get("processing_result"))
    if result.get("ret") != 200:
        return []
    data = _as_dict(result.get("data"))
    friends = data.get("friends") or []
    return [w for w in friends if isinstance(w, str) and w]


def _query_brief_infos(wxids):
    """brief_info 批量（≤20/次）→ {wxid: {nickname, head_img_url}}。"""
    task_uuid = _new_task_uuid()
    client.call("contacts_api", "brief_info", {"wxids": ",".join(wxids)}, task_uuid)
    record = _query_record("contacts_api", "get_brief_info", task_uuid)
    if not record:
        return {}
    result = _as_dict(record.get("processing_result"))
    if result.get("ret") != 200:
        return {}
    rows = result.get("data") or []
    if isinstance(rows, dict):
        rows = rows.get("list") or rows.get("friends") or []
    infos = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        wxid = row.get("wxid") or row.get("username") or ""
        if wxid:
            infos[wxid] = {
                "nickname": _pick(row, ("nickName", "nickname", "nick_name", "name")),
                "head_img_url": _pick(row, ("smallHeadImgUrl", "bigHeadImgUrl", "head_img_url", "headImgUrl", "avatar")),
            }
    return infos


# ---------- 小工具 ----------

def _as_dict(value):
    """processing_result 可能是 dict 或 JSON 字符串（2026-10-29 实测），统一转 dict。"""
    import json

    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        try:
            obj = json.loads(value)
            return obj if isinstance(obj, dict) else {}
        except ValueError:
            return {}
    return {}


def _pick(mapping, keys):
    """在未知字段名里按候选顺序取第一个非空值（联调校准点）。"""
    for key in keys:
        value = mapping.get(key)
        if value:
            return str(value)
    return None
