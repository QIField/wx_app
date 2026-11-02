"""系统灰条与噪音单测：拍一拍/群事件转灰条、51 状态同步等噪音软删。

2026-11-02 实测：微信把系统事件也塞在 msg_type=1 的 content XML 里，
能转可读文案的按微信同款灰条入库，微信不渲染的（51/游戏中心等）
软删留底（不建会话、不广播、不占未读、不刷摘要）。
"""
import pytest

from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.sync import message_sync, msg_xml, sysmsg

from backend.tests.conftest import make_body, make_item, make_user, patch_pull


@pytest.fixture(autouse=True)
def device(app):
    """同步以绑定设备的启用账号为准：造一台 dev01 设备。"""
    return make_user(open_ids=["dev01"])


# 实测拍一拍：template 嵌在 <pat> 子节点里，正文是 ${wxid} 占位符
PAT_XML = ('<sysmsg type="pat"><pat>'
           '<fromusername>wxid_customer</fromusername>'
           '<chatusername>88888888@chatroom</chatusername>'
           '<pattedusername>wxid_me</pattedusername>'
           '<patsuffix><![CDATA[]]></patsuffix>'
           '<template><![CDATA["${wxid_customer}" 拍了拍 "${wxid_me}"]]></template>'
           '</pat></sysmsg>')
# 实测群事件：占位符 $ownername$ 由 link_list 里的昵称替换
TEMPLATE_XML = ('<sysmsg type="sysmsgtemplate"><sysmsgtemplate>'
                '<content_template type="tmpl_type_profile">'
                '<plain><![CDATA[]]></plain>'
                '<template><![CDATA[$ownername$已成为新群主]]></template>'
                '<link_list><link name="ownername" type="link_profile"><memberlist>'
                '<member><username><![CDATA[wxid_vne1]]></username>'
                '<nickname><![CDATA[巴博瑞采购计划专员]]></nickname></member>'
                '</memberlist></link></link_list>'
                '</content_template></sysmsgtemplate></sysmsg>')
# 实测 51 StatusNotify：群已读指针，微信不渲染
STATUS_NOTIFY_XML = ("<msg>\n<op id='5'>\n<username>88888888@chatroom</username>\n"
                     "<name>lastMessage</name>\n</op>\n</msg>")
SYSMSG_DIRECT_TMPL = ('<sysmsg type="guide">'
                      '<template><![CDATA[欢迎加入]]></template></sysmsg>')
UNKNOWN_SYSMSG = '<sysmsg type="future-type"><foo>bar</foo></sysmsg>'


def test_sysmsg_text_extracts_direct_template():
    """sysmsg 直接子节点带 template 文案：提取为可读文本，CDATA 拍平。"""
    assert msg_xml.sysmsg_text(SYSMSG_DIRECT_TMPL) == '欢迎加入'


def test_sysmsg_text_revoke_excluded():
    """revokemsg 不在这里转文案：撤回走 revoke 专门流程。"""
    revoke = ('<sysmsg type="revokemsg"><revokemsg><msgid>0</msgid>'
              '<newmsgid>n1</newmsgid>'
              '<replacemsg><![CDATA[你撤回了一条消息]]></replacemsg>'
              '</revokemsg></sysmsg>')
    assert msg_xml.sysmsg_text(revoke) is None


def test_sysmsg_text_without_text_node():
    """sysmsg 无 replacemsg/template（新事件类型）：返回 None 走兜底。"""
    assert msg_xml.sysmsg_text(UNKNOWN_SYSMSG) is None


def test_sysmsg_text_ignores_non_sysmsg():
    """非 sysmsg 根节点（普通卡片/文本）：返回 None。"""
    link = '<msg><appmsg><title>活动报名</title><type>5</type></appmsg></msg>'
    assert msg_xml.sysmsg_text(link) is None
    assert msg_xml.sysmsg_text("普通文本") is None


def test_pat_info_parses_real_xml():
    """实测拍一拍结构：字段在 <pat> 子节点里，wxid 原文返回；非拍一拍返回空。"""
    info = msg_xml.pat_info(PAT_XML)
    assert info["fromusername"] == "wxid_customer"
    assert info["chatusername"] == "88888888@chatroom"
    assert info["pattedusername"] == "wxid_me"
    assert msg_xml.pat_info(SYSMSG_DIRECT_TMPL) == {}


def test_template_text_fills_nicknames():
    """群事件模板：占位符替换为 link_list 里的昵称。"""
    assert msg_xml.template_text(TEMPLATE_XML) == "巴博瑞采购计划专员已成为新群主"


def test_resolve_routes_gray_and_noise(app, monkeypatch):
    """resolve 分流：拍一拍出灰条，51 直接判噪音，未知 XML 判噪音记日志。"""
    from backend.sync import group_member

    monkeypatch.setattr(
        group_member, "sender_profiles",
        lambda openid, chatroom, wxids: {
            "wxid_customer": {"nickname": "客户", "avatar": ""},
            "wxid_me": {"nickname": "我", "avatar": ""}})
    gray, noise = sysmsg.resolve(PAT_XML, 1, "dev01")
    assert gray == "「客户」拍了拍「我」" and not noise

    gray, noise = sysmsg.resolve(STATUS_NOTIFY_XML, 51, "dev01")
    assert gray is None and noise

    gray, noise = sysmsg.resolve(TEMPLATE_XML, 1, "dev01")
    assert gray == "巴博瑞采购计划专员已成为新群主" and not noise

    gray, noise = sysmsg.resolve(UNKNOWN_SYSMSG, 1, "dev01")
    assert gray is None and noise

    gray, noise = sysmsg.resolve("普通文本", 1, "dev01")
    assert gray is None and not noise


def test_pat_gray_text_uses_roster(app, monkeypatch):
    """拍一拍文案：昵称查群成员名册补齐，查不到的用 wxid 兜底。"""
    from backend.sync import group_member

    monkeypatch.setattr(
        group_member, "sender_profiles",
        lambda openid, chatroom, wxids: {
            "wxid_customer": {"nickname": "客户", "avatar": ""}})
    text = sysmsg._pat_gray_text(msg_xml.pat_info(PAT_XML), "dev01")
    assert text == "「客户」拍了拍「wxid_me」"


def test_sync_pat_xml_becomes_graybar(app, monkeypatch):
    """拍一拍实测 XML：查名册转灰条文案入库，摘要可读，不占未读数。"""
    from backend.sync import group_member

    monkeypatch.setattr(
        group_member, "sender_profiles",
        lambda openid, chatroom, wxids: {
            "wxid_customer": {"nickname": "客户", "avatar": ""},
            "wxid_me": {"nickname": "我", "avatar": ""}})
    patch_pull(monkeypatch, make_body([
        make_item(from_wxid="88888888@chatroom", msg_id="mp", new_msg_id="np",
                  content=PAT_XML)]))

    message_sync.sync_once(app)

    row = Message.query.one()
    assert row.msg_type == Message.MSG_TEXT
    assert row.content == "「客户」拍了拍「我」"
    assert row.payload["system"] is True
    assert row.sender_name == "系统"
    assert row.direction == Message.DIR_OUT
    conv = Conversation.query.one()
    assert conv.last_msg == "「客户」拍了拍「我」"
    assert conv.unread_count == 0  # 系统灰条按出方向入库，不计未读


def test_sync_template_graybar(app, monkeypatch):
    """群事件 sysmsgtemplate：占位符替换为昵称后转系统灰条。"""
    patch_pull(monkeypatch, make_body([
        make_item(msg_id="mt", new_msg_id="nt", content=TEMPLATE_XML)]))

    message_sync.sync_once(app)

    row = Message.query.one()
    assert row.content == "巴博瑞采购计划专员已成为新群主"
    assert row.payload["system"] is True
    assert row.sender_name == "系统"


def test_sync_status_notify_noise_no_conversation(app, monkeypatch):
    """51 StatusNotify 协议噪音：会话不存在时不建会话不入库（杜绝垃圾会话）。"""
    patch_pull(monkeypatch, make_body([
        make_item(msg_type="51", msg_id="m51", new_msg_id="n51",
                  content=STATUS_NOTIFY_XML)]))

    message_sync.sync_once(app)

    assert Message.query.count() == 0
    assert Conversation.query.count() == 0


def test_sync_noise_soft_deleted_with_conversation(app, monkeypatch):
    """已识别协议噪音：会话已存在时软删留底，不广播、不占未读、不刷摘要。"""
    patch_pull(monkeypatch, make_body([make_item(msg_id="m1")]))
    message_sync.sync_once(app)  # 先有正常会话与消息

    patch_pull(monkeypatch, make_body([
        make_item(msg_type="51", msg_id="m51", new_msg_id="n51",
                  content=STATUS_NOTIFY_XML)]))
    message_sync.sync_once(app)

    conv = Conversation.query.one()
    assert conv.unread_count == 1
    assert conv.last_msg == "变速箱修好多钱"
    soft = Message.query.filter_by(middle_msg_id="m51").one()
    assert soft.deleted_at is not None
    assert soft.payload["noise"] is True
    visible = Message.query.filter(Message.deleted_at.is_(None)).all()
    assert [m.middle_msg_id for m in visible] == ["m1"]


def test_sync_noise_dedup_not_revived(app, monkeypatch):
    """噪音行重推（中间方重发）：middle_msg_id 去重含已软删的，不复活。"""
    patch_pull(monkeypatch, make_body([make_item(msg_id="m1")]))
    message_sync.sync_once(app)
    noise = make_item(msg_type="51", msg_id="m51", new_msg_id="n51",
                      content=STATUS_NOTIFY_XML)
    patch_pull(monkeypatch, make_body([noise]))
    message_sync.sync_once(app)
    assert Message.query.filter_by(middle_msg_id="m51").count() == 1

    patch_pull(monkeypatch, make_body([noise]))
    message_sync.sync_once(app)

    assert Message.query.filter_by(middle_msg_id="m51").count() == 1


def test_sync_unknown_sysmsg_noise(app, monkeypatch):
    """解析不出的未知系统 XML：转噪音，无会话时不建会话不入库。"""
    patch_pull(monkeypatch, make_body([
        make_item(msg_id="mu", new_msg_id="nu", content=UNKNOWN_SYSMSG)]))

    message_sync.sync_once(app)

    assert Message.query.count() == 0
    assert Conversation.query.count() == 0
