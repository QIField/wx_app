"""会话资料解析：群名 + 好友昵称/头像（10 分钟一轮的低频后台任务）。

和收消息同套路：uuid 下发任务 → get_ 查询 processing_result。
字段名以防万一做成多候选取值（真实返回结构联调时校准，见 _pick）。
"""
import uuid as uuid_lib

from backend.adapter import client
from backend.extensions import db
from backend.models.conversation import Conversation
from backend.ws.hub import broadcast

MAX_GROUPS_PER_ROUND = 10     # 每轮最多解析 10 个群名（10 分钟一轮，频率极低打不爆）
MAX_FAIL_RETRY = 3            # 同一个 wxid 连续失败 3 次后放弃（进程重启清零）
FRIEND_BATCH = 20             # brief_info 单次最多 20 个 wxid（文档约定）

_fail_counts = {}  # wxid -> 连续失败次数（内存即可）


def sync_profiles(app):
    """定时任务入口：先群名，再好友资料，互不影响（各自 try）。"""
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

def _unnamed_groups():
    """没有名字的群会话（name 为空或还显示着 wxid 原始编号）。"""
    return (
        Conversation.query.filter(
            Conversation.deleted_at.is_(None),
            Conversation.chat_type == Conversation.CHAT_GROUP,
            db.or_(Conversation.name.is_(None), Conversation.name == Conversation.wxid),
        )
        .order_by(Conversation.last_msg_at.desc().nullslast(), Conversation.id)
        .limit(MAX_GROUPS_PER_ROUND)
        .all()
    )


def _sync_group_names():
    for conv in _unnamed_groups():
        if _fail_counts.get(conv.wxid, 0) >= MAX_FAIL_RETRY:
            continue
        name = _query_chatroom_name(conv.wxid)
        if name:
            conv.name = name
            db.session.commit()
            _fail_counts.pop(conv.wxid, None)
            broadcast("conv_updated", {"conversation_id": conv.id})
        else:
            _fail_counts[conv.wxid] = _fail_counts.get(conv.wxid, 0) + 1


def _new_task_uuid():
    return str(uuid_lib.uuid4())


def _query_record(module, get_action, task_uuid):
    """查询下发结果，返回本 uuid 对应的任务记录（找不到返回 None）。

    实测（2026-10-29）：data 是任务记录数组，每条含 uuid + processing_result。
    """
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


def _query_chatroom_name(chatroom_id):
    """chatroom_info 下发 → 查结果 → 提取群名。拿不到返回 None。"""
    task_uuid = _new_task_uuid()
    client.call("group_api", "chatroom_info", {"chatroom_id": chatroom_id}, task_uuid)
    record = _query_record("group_api", "get_chatroom_info", task_uuid)
    if not record:
        return None
    result = record.get("processing_result")
    result = _as_dict(result)
    if result.get("ret") != 200:
        return None
    return _pick(result, ("nickname", "nick_name", "nickName", "chatroom_name", "name", "group_name"))


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
                "nickname": _pick(row, ("nickname", "nick_name", "nickName", "name")),
                "head_img_url": _pick(row, ("head_img_url", "headImgUrl", "avatar", "big_head_url")),
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
