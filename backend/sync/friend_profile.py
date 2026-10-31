"""好友资料解析：逐设备拉好友列表 → 对"已建单聊会话且缺资料"的好友批量查 brief_info。

兜底扫描（30 分钟一轮）与消息触发的立即补拉共用同一套取数与更新逻辑
（apply_friend_info 统一收口，原先两处各写了一遍）。
"""
from backend.adapter import client
from backend.extensions import db
from backend.models.conversation import Conversation
from backend.services.audit import AuditLog, AuditModule, log_action
from backend.services.devices import active_bound_devices
from backend.sync.task_query import (
    as_dict,
    new_task_uuid,
    pick,
    query_record,
    unwrap_result,
)
from backend.ws.hub import broadcast

FRIEND_BATCH = 20  # brief_info 单次最多 20 个 wxid（文档约定）


def sync_friend_profiles():
    """兜底扫描：逐设备拉好友列表并补资料，任一设备失败不影响其他设备。"""
    for openid in active_bound_devices():
        sync_friend_profiles_of_device(openid)


def sync_friend_profiles_of_device(openid):
    """单台设备的好友资料解析；任一步失败不影响其他设备。"""
    try:
        friend_wxids = fetch_friend_wxids(openid)
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        log_action(AuditModule.SYNC, "好友资料解析", f"设备 {openid}",
                   result=AuditLog.RESULT_FAIL, detail=str(exc)[:255])
        return
    if not friend_wxids:
        return
    targets = (
        Conversation.query.filter(
            Conversation.deleted_at.is_(None),
            Conversation.openid == openid,
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
    infos = query_brief_infos([c.wxid for c in targets], openid)
    for conv in targets:
        info = infos.get(conv.wxid)
        if not info:
            continue
        apply_friend_info(conv, info)


def refresh_singles_now(openid, singles):
    """立即补拉好友资料：批量 brief_info（≤ FRIEND_BATCH/次），逐个更新广播。"""
    if not singles:
        return
    wxids = [c.wxid for c in singles[:FRIEND_BATCH]]
    infos = query_brief_infos(wxids, openid)
    for conv in singles[:FRIEND_BATCH]:
        info = infos.get(conv.wxid)
        if not info:
            continue
        apply_friend_info(conv, info)


def apply_friend_info(conv, info):
    """brief_info → 补齐缺资料的昵称/头像；有变更才提交并广播。"""
    changed = False
    if info.get("nickname") and conv.name in (None, "", conv.wxid):
        conv.name = info["nickname"]
        changed = True
    if info.get("head_img_url") and not conv.avatar:
        conv.avatar = info["head_img_url"]
        changed = True
    if changed:
        db.session.commit()
        broadcast("conv_updated", {"conversation_id": conv.id})


def fetch_friend_wxids(openid):
    """fetch_contacts_list 下发 → 查询 → friends wxid 列表（2026-10-29 实测）。"""
    task_uuid = new_task_uuid()
    client.call("contacts_api", "fetch_contacts_list", {}, task_uuid, openid=openid)
    record = query_record("contacts_api", "get_fetch_contacts_list", task_uuid, openid)
    data_raw = unwrap_result(record)
    if data_raw is None:
        return []
    data = as_dict(data_raw)
    friends = data.get("friends") or []
    return [w for w in friends if isinstance(w, str) and w]


def query_brief_infos(wxids, openid=""):
    """brief_info 批量（≤20/次）→ {wxid: {nickname, head_img_url}}。"""
    task_uuid = new_task_uuid()
    client.call("contacts_api", "brief_info", {"wxids": ",".join(wxids)},
                task_uuid, openid=openid)
    record = query_record("contacts_api", "get_brief_info", task_uuid, openid)
    data_raw = unwrap_result(record)
    if data_raw is None:
        return {}
    rows = data_raw or []
    if isinstance(rows, dict):
        rows = rows.get("list") or rows.get("friends") or []
    infos = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        # 2026-10-30 实测真实返回行标识是驼峰 userName
        wxid = row.get("wxid") or row.get("userName") or row.get("username") or ""
        if wxid:
            infos[wxid] = {
                "nickname": pick(row, ("nickName", "nickname", "nick_name", "name")),
                "head_img_url": pick(row, ("smallHeadImgUrl", "bigHeadImgUrl", "head_img_url", "headImgUrl", "avatar")),
            }
    return infos
