"""通讯录拉取独立入口：好友简要资料 + 群信息（含成员）。

给兜底轮 / 登录触发 / 手动刷新 / 新功能接入提供统一调中间方的门面，
内部复用 contact_sync / friend_profile / group_profile 的取数逻辑，
不重复造轮子。

两个函数的链路：
  fetch_friends  → fetch_contacts_list_cache 拿 wxid 名册
                 → brief_info 批量补昵称头像备注（20/批）
  fetch_groups   → fetch_contacts_list_cache 拿 wxid 名册
                 → chatroom_info 同步查每个群的群名头像
                 → chatroom_member_list 补成员头像（内置在 query_chatroom_info）
"""
from backend.sync import contact_sync, friend_profile, group_profile


def fetch_friends(openid: str, max_per_batch: int = friend_profile.FRIEND_BATCH) -> list[dict]:
    """拉全量好友简要资料（名册 → 批量补资料 → 一次返回）。

    返回 [{userName, nickName, bigHeadImgUrl, smallHeadImgUrl, remark}]

    批次上限按中间方 brief_info 单次 ≤20 约定，默认 FRIEND_BATCH=20。
    好友数量大时自动分批；某 wxid 查不到资料（非好友、中间方失败等）会跳过。
    """
    catalog = contact_sync.fetch_contact_wxids(openid)
    friends = catalog.get("friends") or []
    if not friends:
        return []

    # 分批查 brief_info：中间方文档约定单次 ≤20 个 wxid
    all_infos: dict[str, dict] = {}
    for i in range(0, len(friends), max_per_batch):
        chunk = friends[i : i + max_per_batch]
        all_infos.update(friend_profile.query_brief_infos(chunk, openid))

    result = []
    for wxid in friends:
        info = all_infos.get(wxid)
        if not info:
            continue
        result.append({
            "userName": info.get("userName") or wxid,
            "nickName": info.get("nickName") or info.get("nickname"),
            "bigHeadImgUrl": info.get("head_img_url"),
            "smallHeadImgUrl": info.get("smallHeadImgUrl") or info.get("head_img_url"),
            "remark": info.get("remark"),
        })
    return result


def fetch_groups(openid: str, include_members: bool = False) -> list[dict]:
    """拉全量群信息（名册 → 逐个同步查 chatroom_info + chatroom_member_list）。

    成员头像已内置补拉（query_chatroom_info 自动调 chatroom_member_list）。

    返回 [{chatroomId, nickName, remark, smallHeadImgUrl, memberList?}]
    memberList 里成员结构：{wxid, nickname, avatar, member_remark}
    """
    catalog = contact_sync.fetch_contact_wxids(openid)
    chatrooms = catalog.get("chatrooms") or []
    if not chatrooms:
        return []

    result = []
    for wxid in chatrooms:
        info = group_profile.query_chatroom_info(wxid, openid)
        if not info:
            continue
        group_item = {
            "chatroomId": wxid,
            "nickName": info.get("nickname"),
            "remark": info.get("remark"),
            "smallHeadImgUrl": info.get("avatar"),
        }
        if include_members:
            group_item["memberList"] = info.get("members") or []
        result.append(group_item)
    return result
