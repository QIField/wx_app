"""群成员资料：memberList 落库、发送者资料解析、缺头像批量补拉。

昵称来自 chatroom_info.memberList（群资料收割时顺带落库）；头像该接口不返回，
对缺额成员批量调 brief_info 补齐（实测对非好友群成员有效）。
"""
from backend.extensions import db
from backend.models.conversation import Conversation
from backend.models.group_member import GroupMember
from backend.sync.friend_profile import query_brief_infos
from backend.sync.roster import reconcile

AVATAR_BATCH = 40  # 每轮最多补 40 个成员头像（brief_info 20/次，两次调用）


def save_members(openid, chatroom_wxid, members):
    """memberList 全量对齐：新增/复活成员，退群成员标记 deleted_at。

    memberList 是群的权威名册，为空时直接返回，避免接口偶发空数组
    把整群成员误标为已删除。
    """
    rows = [m for m in members or [] if isinstance(m, dict) and m.get("wxid")]
    if not rows:
        return False
    by_wxid = {m["wxid"]: m for m in rows}
    existing = {
        gm.wxid: gm
        for gm in GroupMember.query.filter_by(
            openid=openid, chatroom_wxid=chatroom_wxid
        ).all()
    }
    created, changed = reconcile(existing, list(by_wxid))
    for wxid in created:
        db.session.add(GroupMember(
            openid=openid, chatroom_wxid=chatroom_wxid,
            wxid=wxid, nickname=by_wxid[wxid].get("nickname") or None,
        ))
    for wxid, m in by_wxid.items():  # 只补空昵称，不覆盖已有值
        row = existing.get(wxid)
        if row is not None and not row.nickname and m.get("nickname"):
            row.nickname = m["nickname"]
            changed = True
    return changed or bool(created)


def sender_map_for(conv, wxids):
    """会话发言人的昵称/头像映射；单聊返回空（发言人即会话对方，走会话头像）。

    消息 API 与 WS 广播共用：存库 sender_name 是 wxid 原文，展示前统一在此解析。
    """
    if conv.chat_type != Conversation.CHAT_GROUP:
        return {}
    return sender_profiles(conv.openid, conv.wxid, wxids)


def sender_profiles(openid, chatroom_wxid, wxids):
    """批量查群成员资料 → {wxid: {nickname, avatar}}；查不到的成员不在结果里。"""
    ids = [w for w in set(wxids or []) if w]
    if not ids:
        return {}
    rows = (
        GroupMember.query.filter_by(openid=openid, chatroom_wxid=chatroom_wxid,
                                   deleted_at=None)
        .filter(GroupMember.wxid.in_(ids))
        .all()
    )
    return {
        r.wxid: {"nickname": r.nickname, "avatar": r.avatar}
        for r in rows
    }


def refresh_avatars_of_device(openid, chatroom_wxid=None, batch=AVATAR_BATCH):
    """补拉缺头像的群成员：批量 brief_info 补头像（实测对非好友有效）。

    chatroom_wxid 传入时只补该群（消息触发路径，收割后立即补），
    缺省补该设备全部缺额（30 分钟兜底轮）。返回是否有更新（供调用方广播）。
    """
    q = GroupMember.query.filter(
        GroupMember.openid == openid,
        GroupMember.deleted_at.is_(None),
        GroupMember.avatar.is_(None),
    )
    if chatroom_wxid:
        q = q.filter(GroupMember.chatroom_wxid == chatroom_wxid)
    targets = q.order_by(GroupMember.id).limit(batch).all()
    if not targets:
        return False
    infos = query_brief_infos([t.wxid for t in targets], openid)
    changed = False
    for row in targets:
        info = infos.get(row.wxid)
        if not info:
            continue
        if info.get("head_img_url") and not row.avatar:
            row.avatar = info["head_img_url"]
            changed = True
        if info.get("nickname") and not row.nickname:
            row.nickname = info["nickname"]
            changed = True
    return changed
