"""群成员资料单测：memberList 落库、发送者解析、缺头像补拉、消息 API 集成。

背景（2026-10-31 排查）：群消息 sender_name 存库是 wxid 原文（中间方
get_message 不返回昵称），前端显示 wxid、头像为首字占位。根因是
chatroom_info.memberList 从未接入，本模块的用例守住三条链路：
落库 → 读取实时关联 → 头像兜底补拉。
"""
import pytest

from backend.extensions import db
from backend.models.conversation import Conversation
from backend.models.group_member import GroupMember
from backend.models.message import Message
from backend.sync import group_member, group_profile

from backend.tests.conftest import make_user  # noqa: F401 造号工厂（集成用例走 client 夹具）


@pytest.fixture(autouse=True)
def clean_profile_state():
    """清掉群资料模块的全局任务登记，避免用例间互相污染 _pending/_fail_counts。"""
    group_profile._pending.clear()
    group_profile._fail_counts.clear()
    yield
    group_profile._pending.clear()
    group_profile._fail_counts.clear()


@pytest.fixture
def group_conv(app):
    # openid 用 dev01：API 集成用例的登录用户（client 夹具）绑定该设备
    conv = Conversation(openid="dev01", wxid="123@chatroom", chat_type=2, name="报价群")
    db.session.add(conv)
    db.session.commit()
    return conv


def _member(openid="dev01", room="123@chatroom", wxid="wxid_a", nickname="成员甲", avatar=None):
    row = GroupMember(openid=openid, chatroom_wxid=room, wxid=wxid,
                      nickname=nickname, avatar=avatar)
    db.session.add(row)
    db.session.commit()
    return row


# ---------- memberList 落库 ----------

def test_save_members_inserts(app, group_conv):
    """memberList 落库：wxid+昵称写入，返回有新增。"""
    added = group_member.save_members("o1", group_conv.wxid,
                                      [{"wxid": "wxid_a", "nickname": "成员甲"}])
    db.session.commit()

    assert added is True
    row = GroupMember.query.one()
    assert row.nickname == "成员甲"
    assert row.avatar is None


def test_save_members_marks_leaver_deleted_then_restores(app, group_conv):
    """退群：名册里消失标记 deleted_at；重新进群复活同一行。"""
    members_v1 = [{"wxid": "wxid_a", "nickname": "甲"}, {"wxid": "wxid_b", "nickname": "乙"}]
    group_member.save_members(group_conv.openid, group_conv.wxid, members_v1)
    db.session.commit()

    group_member.save_members(group_conv.openid, group_conv.wxid, members_v1[:1])
    db.session.commit()
    db.session.expire_all()
    leaver = GroupMember.query.filter_by(
        openid=group_conv.openid, chatroom_wxid=group_conv.wxid, wxid="wxid_b"
    ).one()
    assert leaver.deleted_at is not None
    assert GroupMember.query.filter_by(chatroom_wxid=group_conv.wxid).count() == 2

    group_member.save_members(group_conv.openid, group_conv.wxid, members_v1)
    db.session.commit()
    db.session.expire_all()
    back = GroupMember.query.filter_by(
        openid=group_conv.openid, chatroom_wxid=group_conv.wxid, wxid="wxid_b"
    ).one()
    assert back.deleted_at is None
    assert back.id == leaver.id


def test_save_members_upsert_keeps_avatar(app, group_conv):
    """重复收割：已有成员只补昵称，不覆盖已有头像；无新增返回 False。"""
    _member(avatar="http://a/x.jpg")

    added = group_member.save_members("dev01", group_conv.wxid,
                                      [{"wxid": "wxid_a", "nickname": "新昵称"}])
    db.session.commit()

    assert added is False
    row = GroupMember.query.one()
    assert row.avatar == "http://a/x.jpg"  # 头像不被清掉
    assert row.nickname == "成员甲"  # 已有昵称不回退


def test_save_members_skips_bad_rows(app, group_conv):
    """坏数据（无 wxid）跳过，不落库。"""
    added = group_member.save_members("o1", group_conv.wxid,
                                      [{"nickname": "没id"}, "not-a-dict", None])
    assert added is False
    assert GroupMember.query.count() == 0


# ---------- 发送者资料解析 ----------

def test_sender_profiles_returns_known_only(app, group_conv):
    """按 wxid 批量解析；表里没有的成员不在结果里（调用方用 wxid 兜底）。"""
    _member(wxid="wxid_a", nickname="成员甲", avatar="http://a/a.jpg")

    profiles = group_member.sender_profiles("dev01", group_conv.wxid, ["wxid_a", "wxid_unknown"])

    assert profiles == {"wxid_a": {"nickname": "成员甲", "avatar": "http://a/a.jpg"}}


def test_sender_profiles_empty_inputs(app):
    assert group_member.sender_profiles("o1", "123@chatroom", []) == {}
    assert group_member.sender_profiles("o1", "123@chatroom", None) == {}


# ---------- 群资料收割顺带落成员 ----------

def test_missing_profile_includes_empty_roster(app, group_conv):
    """群资料看起来齐全但成员名册为空：也算缺资料（否则名册永远没数据）。"""
    group_conv.name = "报价群"
    group_conv.avatar = "http://a/room.jpg"
    db.session.commit()

    # 名册为空 → 缺资料；落一条成员后 → 不缺
    assert group_profile.missing_profile(group_conv) is True
    _member()
    db.session.expire_all()
    assert group_profile.missing_profile(group_conv) is False


def test_fallback_scan_covers_empty_roster(app, group_conv, monkeypatch):
    """兜底轮：资料齐全但名册为空的群也会被选中下发 chatroom_info。"""
    group_conv.name = "报价群"
    group_conv.avatar = "http://a/room.jpg"
    db.session.commit()
    dispatched = []

    def fake_call(module, action, params=None, uuid=None, openid=""):
        if action == "chatroom_info":
            dispatched.append(params["chatroom_id"])
        return {}

    monkeypatch.setattr(group_profile.client, "call", fake_call)
    monkeypatch.setattr(group_profile, "query_record_once",
                        lambda module, action, u, openid="": None)

    group_profile.sync_group_names()

    assert dispatched == [group_conv.wxid]


def test_group_harvest_saves_members(app, group_conv, monkeypatch):
    """chatroom_info 收割：memberList 顺带落 group_member（真实结构 mock）。"""
    record = {
        "uuid": "u1",
        "processing_result": (
            '{"ret": 200, "msg": "操作成功", "data": {"chatroomId": "123@chatroom",'
            ' "nickName": "报价群", "smallHeadImgUrl": "http://a/room.jpg",'
            ' "memberList": [{"wxid": "wxid_a", "nickName": "成员甲"},'
            ' {"wxid": "wxid_b", "nickName": "成员乙"}]}}'
        ),
    }
    monkeypatch.setattr(group_profile, "query_record_once",
                        lambda module, action, u, openid="": record)

    info = group_profile.parse_group_info(record)
    group_profile.apply_group_info(group_conv.id, group_conv.wxid, info)
    db.session.commit()

    assert GroupMember.query.count() == 2
    assert GroupMember.query.filter_by(wxid="wxid_b").one().nickname == "成员乙"


# ---------- 缺头像补拉 ----------

def test_refresh_avatars_fills_and_keeps_nickname(app, monkeypatch):
    """缺头像成员批量 brief_info 补头像；已有昵称不被覆盖。"""
    _member(nickname="成员甲", avatar=None)
    monkeypatch.setattr(
        group_member, "query_brief_infos",
        lambda wxids, openid="": {
            "wxid_a": {"nickname": "别的名", "head_img_url": "http://a/a.jpg"},
        },
    )

    changed = group_member.refresh_avatars_of_device("dev01")
    db.session.commit()

    assert changed is True
    row = GroupMember.query.one()
    assert row.avatar == "http://a/a.jpg"
    assert row.nickname == "成员甲"


def test_refresh_avatars_no_missing_skips_query(app, monkeypatch):
    """没有缺额时不下发请求；有结果但无头像 URL 也不算变更。"""
    _member(avatar="http://a/a.jpg")
    monkeypatch.setattr(
        group_member, "query_brief_infos",
        lambda wxids, openid="": {"wxid_a": {"nickname": "x", "head_img_url": None}},
    )
    # 头像齐全：直接短路
    assert group_member.refresh_avatars_of_device("o1") is False

    # 有缺额但中间方没返回头像：无变更
    _member(wxid="wxid_b", nickname="成员乙", avatar=None)
    assert group_member.refresh_avatars_of_device("o1") is False


# ---------- 消息触发路径：收割后立即补头像 ----------

def test_refresh_groups_now_fills_avatars_immediately(app, group_conv, monkeypatch):
    """消息触发收割群资料后，立即补该群成员头像（不再等 30 分钟兜底）。"""
    record = {
        "uuid": "u1",
        "processing_result": (
            '{"ret": 200, "msg": "操作成功", "data": {"chatroomId": "123@chatroom",'
            ' "nickName": "报价群", "smallHeadImgUrl": "http://a/room.jpg",'
            ' "memberList": [{"wxid": "wxid_a", "nickName": "成员甲"}]}}'
        ),
    }
    monkeypatch.setattr(group_profile, "query_record",
                        lambda module, action, u, openid="", retries=5: record)
    monkeypatch.setattr(group_profile.client, "call", lambda *a, **k: {})
    monkeypatch.setattr(
        group_member, "query_brief_infos",
        lambda wxids, openid="": {
            "wxid_a": {"nickname": "成员甲", "head_img_url": "http://a/a.jpg"},
        },
    )

    group_profile.refresh_groups_now(group_conv.openid, [group_conv])

    row = GroupMember.query.filter_by(wxid="wxid_a").one()
    assert row.avatar == "http://a/a.jpg"


def test_refresh_groups_now_avatar_failure_not_blocking(app, group_conv, monkeypatch):
    """补头像抛异常不上抛：收消息主链路不受影响，成员昵称已落库。"""
    record = {
        "uuid": "u1",
        "processing_result": (
            '{"ret": 200, "msg": "操作成功", "data": {"chatroomId": "123@chatroom",'
            ' "nickName": "报价群", "memberList": [{"wxid": "wxid_a", "nickName": "成员甲"}]}}'
        ),
    }
    monkeypatch.setattr(group_profile, "query_record",
                        lambda module, action, u, openid="", retries=5: record)
    monkeypatch.setattr(group_profile.client, "call", lambda *a, **k: {})

    def boom(wxids, openid=""):
        raise RuntimeError("brief_info down")

    monkeypatch.setattr(group_member, "query_brief_infos", boom)

    group_profile.refresh_groups_now(group_conv.openid, [group_conv])  # 不应抛异常

    assert GroupMember.query.filter_by(wxid="wxid_a").one().nickname == "成员甲"


# ---------- 消息 API 集成 ----------

def test_group_messages_api_resolves_sender(client, app, group_conv):
    """群消息 API：sender_name/sender_avatar 实时关联群成员名册。"""
    _member(wxid="wxid_a", nickname="成员甲", avatar="http://a/a.jpg")
    db.session.add(Message(
        conversation_id=group_conv.id, msg_type=Message.MSG_TEXT,
        direction=Message.DIR_IN, sender_wxid="wxid_a", sender_name="wxid_a",
        content="各位看过来", create_time=datetime_now(),
    ))
    db.session.add(Message(
        conversation_id=group_conv.id, msg_type=Message.MSG_TEXT,
        direction=Message.DIR_IN, sender_wxid="wxid_ghost", sender_name="wxid_ghost",
        content="不在名册", create_time=datetime_now(),
    ))
    db.session.commit()

    resp = client.get(f"/api/conversations/{group_conv.id}/messages")

    assert resp.status_code == 200
    msgs = resp.get_json()["data"]["messages"]
    by_content = {m["content"]: m for m in msgs}
    known = by_content["各位看过来"]
    assert known["sender_name"] == "成员甲"      # 名册里的成员 → 昵称
    assert known["sender_avatar"] == "http://a/a.jpg"
    ghost = by_content["不在名册"]
    assert ghost["sender_name"].startswith("匿名 ")  # 不在名册 → 匿名编码兜底（脱敏契约）
    assert ghost["sender_avatar"] is None
    assert ghost["sender_alias"]


def test_single_messages_api_unaffected(client, app):
    """单聊消息不关联群成员名册：sender_avatar 为 None（头像走会话头像）。"""
    conv = Conversation(openid="dev01", wxid="wxid_customer", chat_type=1, name="张师傅")
    db.session.add(conv)
    db.session.commit()
    db.session.add(Message(
        conversation_id=conv.id, msg_type=Message.MSG_TEXT,
        direction=Message.DIR_IN, sender_wxid="wxid_customer", sender_name="wxid_customer",
        content="单聊", create_time=datetime_now(),
    ))
    db.session.commit()

    resp = client.get(f"/api/conversations/{conv.id}/messages")

    msg = resp.get_json()["data"]["messages"][0]
    assert msg["sender_name"].startswith("匿名 ")  # 快照是 wxid 原文 → 匿名编码（脱敏契约）
    assert msg["sender_avatar"] is None


def datetime_now():
    from datetime import datetime

    return datetime(2026, 10, 31, 12, 0, 0)


# ---------- @提及名册接口 ----------

def test_members_api_returns_roster_with_pinyin(client, app, group_conv):
    """名册接口：只给行号 id（脱敏契约），附全拼/首字母供前端本地检索。"""
    _member(wxid="wxid_a", nickname="张三")
    _member(wxid="wxid_b", nickname="李四")

    resp = client.get(f"/api/conversations/{group_conv.id}/members")

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["total"] == 2
    by_name = {m["name"]: m for m in data["list"]}
    assert by_name["张三"]["pinyin"] == "zhangsan"
    assert by_name["张三"]["initials"] == "zs"
    assert by_name["李四"]["pinyin"] == "lisi"
    for m in data["list"]:
        assert set(m) == {"id", "name", "avatar", "alias", "pinyin", "initials"}
        assert "wxid" not in m  # 脱敏：wxid 一律不下发
        assert m["alias"]  # 未解析/已解析都有稳定别名


def test_members_api_unresolved_name_has_empty_pinyin(client, app, group_conv):
    """昵称未解析（仍是 wxid 原文）：name=None，拼音为空，前端用别名兜底展示。"""
    _member(wxid="wxid_ghost", nickname="wxid_ghost")

    data = client.get(f"/api/conversations/{group_conv.id}/members").get_json()["data"]

    row = data["list"][0]
    assert row["name"] is None
    assert row["pinyin"] == ""
    assert row["initials"] == ""
    assert row["alias"]


def test_members_api_scoped_to_room(client, app, group_conv):
    """只返回本群、未删除的成员：跨群/软删的行不能串进来。"""
    from datetime import datetime

    _member(wxid="wxid_a", nickname="本群成员")
    _member(wxid="wxid_b", nickname="别群成员", room="456@chatroom")
    gone = _member(wxid="wxid_c", nickname="已删除")
    gone.deleted_at = datetime(2026, 10, 1, 0, 0, 0)
    db.session.commit()

    data = client.get(f"/api/conversations/{group_conv.id}/members").get_json()["data"]

    assert data["total"] == 1
    assert data["list"][0]["name"] == "本群成员"


def test_members_api_single_chat_returns_empty(client, app):
    """单聊没有名册：返回空列表而不是报错（前端据此不弹选择层）。"""
    conv = Conversation(openid="dev01", wxid="wxid_customer", chat_type=1, name="张师傅")
    db.session.add(conv)
    db.session.commit()

    data = client.get(f"/api/conversations/{conv.id}/members").get_json()["data"]

    assert data == {"list": [], "total": 0}


def test_members_api_not_found(client, app):
    """跨账号/不存在的会话：404，与消息接口口径一致。"""
    resp = client.get("/api/conversations/999/members")
    assert resp.status_code == 404
    assert resp.get_json()["code"] == 404
