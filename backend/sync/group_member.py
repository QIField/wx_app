"""群成员资料：memberList 落库、发送者资料解析、缺头像批量补拉。

昵称来自 chatroom_info.memberList（群资料收割时顺带落库）；头像该接口不返回，
对缺额成员批量调 brief_info 补齐（实测对非好友群成员有效）。
"""
from backend.extensions import db
from backend.models.conversation import Conversation
from backend.models.group_member import GroupMember
from backend.services import anonymize
from backend.sync.friend_profile import query_brief_infos
from backend.sync.roster import reconcile

AVATAR_BATCH = 40    # 每轮最多补 40 个成员头像（brief_info 20/次，分两次调用）
BRIEF_BATCH = 20     # brief_info 单次 wxid 上限（中间方文档约定），补拉按此分批下发
MAX_AVATAR_FAILS = 5  # 同一成员连续拿不到头像的次数上限，达到后跳过（进程重启清零）

# (openid, wxid) -> 连续补拉失败次数（内存即可，参照 group_profile._fail_counts 同款约定）
_avatar_fails = {}


def reset_avatar_fails():
    """清空补拉失败计数（单测用；生产随进程重启自然清零）。"""
    _avatar_fails.clear()


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


def sender_view(wxid, info=None, snapshot_name=None):
    """发言人展示字段唯一拼装点（HTTP 消息 API 与 WS 广播共用，防两处口径漂移）。

    脱敏契约：出参绝不含 wxid 原文；昵称与快照都未解析才算真匿名
    （sender_anon 显式标记），@openim 等"有名字没头像"的成员不算匿名，
    前端走名称首字兜底而不是匿名图标。
    """
    nickname = anonymize.resolved_name((info or {}).get("nickname"), wxid)
    snapshot = anonymize.resolved_name(snapshot_name, wxid)
    return {
        "sender_name": nickname or snapshot or anonymize.anon_label(wxid),
        "sender_avatar": (info or {}).get("avatar") if nickname else None,
        "sender_anon": not nickname and not snapshot,
        "sender_alias": anonymize.alias_of(wxid),
    }


def refresh_avatars_of_device(openid, chatroom_wxid=None, batch=AVATAR_BATCH):
    """补拉缺头像的群成员：批量 brief_info 补头像（实测对非好友有效）。

    chatroom_wxid 传入时只补该群（消息触发路径，收割后立即补），
    缺省补该设备全部缺额（30 分钟兜底轮）。返回是否有更新（供调用方广播）。

    防队列头饥饿（2026-11-13 排查根因）：brief_info 对 @openim 企业互联账号
    等特殊成员永远不返回头像，这类行按 id 排序长期霸占批次前段——实测曾把
    每轮 40 个名额吃掉 28 个、队列头成员被重复请求 193 次。故对连续
    MAX_AVATAR_FAILS 次补不到的成员跳过，把名额让给后面补得到的成员。
    """
    q = GroupMember.query.filter(
        GroupMember.openid == openid,
        GroupMember.deleted_at.is_(None),
        GroupMember.avatar.is_(None),
    )
    if chatroom_wxid:
        q = q.filter(GroupMember.chatroom_wxid == chatroom_wxid)
    targets = []
    for row in q.order_by(GroupMember.id).all():  # 缺额千级，全量遍历成本可忽略
        if _avatar_fails.get((openid, row.wxid), 0) >= MAX_AVATAR_FAILS:
            continue  # 已判死的名额：跳过，不占本轮批次
        targets.append(row)
        if len(targets) >= batch:
            break
    if not targets:
        return False
    # brief_info 单次 ≤20 个 wxid（文档约定，超限可能被中间方截断）：按 BRIEF_BATCH 分批
    infos = {}
    for i in range(0, len(targets), BRIEF_BATCH):
        chunk = [t.wxid for t in targets[i:i + BRIEF_BATCH]]
        infos.update(query_brief_infos(chunk, openid))
    changed = False
    for row in targets:
        info = infos.get(row.wxid) or {}
        if info.get("head_img_url"):
            _avatar_fails.pop((openid, row.wxid), None)  # 成功即清零
            row.avatar = info["head_img_url"]
            changed = True
        else:
            # 中间方没返回记录或没带头像：连续失败 +1，达到上限后后续轮跳过
            key = (openid, row.wxid)
            _avatar_fails[key] = _avatar_fails.get(key, 0) + 1
        if info.get("nickname") and not row.nickname:
            row.nickname = info["nickname"]
            changed = True
    return changed
