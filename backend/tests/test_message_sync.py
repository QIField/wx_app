"""收消息轮询单测：mock 中间方 get_message，验证入库与游标。

系统灰条与噪音的用例在 test_message_sysmsg.py。
"""
import json
from datetime import datetime, timedelta

import pytest

from backend.extensions import db
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.models.sync_cursor import SyncCursor
from backend.sync import message_sync, msg_xml

from backend.tests.conftest import make_body, make_item, make_user, patch_pull


@pytest.fixture(autouse=True)
def device(app):
    """同步以绑定设备的启用账号为准：造一台 dev01 设备。"""
    return make_user(open_ids=["dev01"])


def make_real_item(**over):
    """按 2026-10-29 联调实测结构造一条群消息（RFC 1123 时间、字符串类型）。"""
    raw_json = json.dumps({
        "TypeName": "AddMsg",
        "Data": {"MsgId": 1622189713, "NewMsgId": 1920921937912189642,
                 "FromUserName": {"string": "38854524004@chatroom"},
                 "ToUserName": {"string": "wxid_yfm4es06qpzt22"},
                 "CreateTime": 1793268964},
        "Wxid": "wxid_me",
    }, ensure_ascii=False)
    item = {
        "id": 10524,
        "msg_id": "1622189713",
        "from_wxid": "38854524004@chatroom",
        "to_wxid": "wxid_me",
        "msg_type": "1",
        "content": "wxid_iobwbybwbmp622:\n11537649409=盖茨80，原厂220",
        "create_time": "Thu, 29 Oct 2026 18:16:04 GMT",
        "raw_json": raw_json,
    }
    item.update(over)
    return item


def test_sync_saves_real_structure(app, monkeypatch):
    """实测真实结构：群消息拆发言人、RFC1123 时间、字符串类型、raw_json 取 NewMsgId。"""
    patch_pull(monkeypatch, make_body([make_real_item()]))

    message_sync.sync_once(app)

    msg = Message.query.one()
    assert msg.middle_msg_id == "1622189713"
    assert msg.new_msg_id == "1920921937912189642"
    assert msg.msg_type == Message.MSG_TEXT
    assert msg.sender_wxid == "wxid_iobwbybwbmp622"  # 从 content 拆出的发言人
    assert msg.content == "11537649409=盖茨80，原厂220"
    assert msg.direction == Message.DIR_IN
    assert msg.create_time.strftime("%Y-%m-%d %H:%M:%S") == "2026-10-29 18:16:04"


def test_sync_saves_new_message(app, monkeypatch):
    """拉到 1 条新消息：入库 + 建会话 + 未读 1 + 游标推进到消息时间。"""
    patch_pull(monkeypatch, make_body([make_item()]))

    message_sync.sync_once(app)

    msg = Message.query.one()
    assert msg.content == "变速箱修好多钱"
    assert msg.direction == Message.DIR_IN
    assert msg.middle_msg_id == "m1001"

    conv = Conversation.query.one()
    assert conv.wxid == "wxid_customer"
    assert conv.chat_type == Conversation.CHAT_SINGLE
    assert conv.unread_count == 1
    assert conv.last_msg == "变速箱修好多钱"
    assert conv.last_msg_at == msg.create_time

    cursor = SyncCursor.query.one()
    assert cursor.last_sync_time == msg.create_time
    assert cursor.cursor_type == "msg"


def test_sync_dedup_skips_existing(app, monkeypatch):
    """同一 middle_msg_id 再拉到：不重复入库，未读不涨。"""
    patch_pull(monkeypatch, make_body([make_item()]))
    message_sync.sync_once(app)

    message_sync.sync_once(app)

    assert Message.query.count() == 1
    conv = Conversation.query.one()
    assert conv.unread_count == 1


def test_sync_empty_round(app, monkeypatch):
    """空轮：不入库，游标保持初始值（1 小时前）不动。"""
    patch_pull(monkeypatch, make_body([]))

    message_sync.sync_once(app)

    assert Message.query.count() == 0
    assert Conversation.query.count() == 0


def test_sync_skips_offline_device(app, monkeypatch):
    """已判定离线（online=0）的设备整轮跳过，不发 get_message；未知/在线照常轮询。"""
    from backend.models.device import Device

    captured = patch_pull(monkeypatch, make_body([make_item()]))

    # 未知（-1，刚启动还没检测过）：照常轮询
    message_sync.sync_once(app)
    assert captured["openid"] == "dev01"
    assert Message.query.count() == 1
    msg_time = SyncCursor.query.one().last_sync_time

    # 判定离线：跳过，不再发请求，游标也不动
    Device.query.filter_by(openid="dev01").update({"online": 0})
    db.session.commit()
    captured.clear()
    message_sync.sync_once(app)
    assert captured == {}
    assert SyncCursor.query.one().last_sync_time == msg_time


def test_sync_out_direction_no_unread(app, monkeypatch):
    """自己发出的消息（is_sender=1）：对方是 to_wxid，未读不涨。"""
    item = make_item(is_sender=1, from_wxid="wxid_me", to_wxid="wxid_customer")
    patch_pull(monkeypatch, make_body([item]))

    message_sync.sync_once(app)

    msg = Message.query.one()
    assert msg.direction == Message.DIR_OUT
    conv = Conversation.query.one()
    assert conv.wxid == "wxid_customer"
    assert conv.unread_count == 0


def test_sync_group_message(app, monkeypatch):
    """群消息（@chatroom 结尾）：会话类型为群聊。"""
    item = make_item(from_wxid="88888888@chatroom")
    patch_pull(monkeypatch, make_body([item]))

    message_sync.sync_once(app)

    conv = Conversation.query.one()
    assert conv.wxid == "88888888@chatroom"
    assert conv.chat_type == Conversation.CHAT_GROUP


def test_sync_broadcast_masks_wxid(app, monkeypatch):
    """脱敏契约：WS new_message 推送不含 wxid 原文；无昵称发言人回退匿名编码。"""
    from backend.ws import hub

    broadcasts = []
    monkeypatch.setattr(hub, "broadcast", lambda event, data: broadcasts.append((event, data)))
    patch_pull(monkeypatch, make_body([make_item()]))
    message_sync.sync_once(app)

    events = [d for e, d in broadcasts if e == "new_message"]
    assert events, "应有 new_message 推送"
    ev = events[0]
    assert "sender_wxid" not in ev
    assert ev["sender_name"].startswith("匿名 ")  # 存库快照是 wxid 原文，推送前必须匿名化
    assert ev["sender_avatar"] is None            # 无昵称 → 头像一并匿名
    assert ev["sender_alias"]


def test_sync_broadcast_carries_summary(app, monkeypatch):
    """推送契约：new_message 带 summary（后端算好的会话摘要），前端列表直接用。"""
    from backend.ws import hub

    broadcasts = []
    monkeypatch.setattr(hub, "broadcast", lambda event, data: broadcasts.append((event, data)))
    patch_pull(monkeypatch, make_body([make_item()]))
    message_sync.sync_once(app)

    events = [d for e, d in broadcasts if e == "new_message"]
    assert events and events[0]["summary"] == "变速箱修好多钱"


def test_sync_pull_error_silent(app, monkeypatch):
    """拉取失败：不崩、游标不动，下一轮重来。"""
    from backend.adapter.client import MiddleApiError

    def boom(action, params=None, uuid=None, openid=""):
        raise MiddleApiError("设备离线")

    monkeypatch.setattr(message_sync.middle_client, "call", boom)

    message_sync.sync_once(app)  # 不应抛异常

    assert Message.query.count() == 0
    assert SyncCursor.query.count() == 0  # 游标行都没建，等下一轮


def test_sync_pull_params(app, monkeypatch):
    """拉取参数：带 start_create_time 和分页，且带设备 openid。"""
    captured = patch_pull(monkeypatch, make_body([]))

    message_sync.sync_once(app)

    assert captured["module"] == "messag_api"
    assert captured["action"] == "get_message"
    assert "start_create_time" in captured["params"]
    assert captured["params"]["page_size"] == 100
    assert captured["openid"] == "dev01"


def test_sync_multi_device_isolated(app, monkeypatch):
    """多设备：两台设备各拉各的游标，会话互不串。"""
    make_user(username="cs02", name="客服02", open_ids=["dev02"])
    bodies = {"dev01": make_body([make_item(msg_id="m1")]),
              "dev02": make_body([make_item(msg_id="m2", from_wxid="wxid_02")])}
    calls = []

    def fake_call(module, action, params=None, uuid=None, openid=""):
        calls.append(openid)
        return bodies[openid]

    monkeypatch.setattr(message_sync.middle_client, "call", fake_call)

    message_sync.sync_once(app)

    assert sorted(calls) == ["dev01", "dev02"]
    assert Conversation.query.filter_by(openid="dev01", wxid="wxid_customer").count() == 1
    assert Conversation.query.filter_by(openid="dev02", wxid="wxid_02").count() == 1
    assert SyncCursor.query.count() == 2  # 两台设备各一条游标


def test_sync_triggers_profile_refresh(app, monkeypatch):
    """新消息入库后触发资料补拉：带本轮会话 id（覆盖 conftest 的全局 mock）。"""
    from backend.sync import profile_sync

    got = []
    monkeypatch.setattr(profile_sync, "refresh_missing_profiles",
                        lambda openid, ids: got.append((openid, list(ids))))
    patch_pull(monkeypatch, make_body([make_item()]))

    message_sync.sync_once(app)

    assert len(got) == 1
    openid, ids = got[0]
    assert openid == "dev01"
    assert ids == [Conversation.query.one().id]


def test_sync_disabled_user_not_polled(app, device, monkeypatch):
    """停用账号或未绑定设备的账号不参与同步。"""
    device.status = 0
    db.session.commit()
    calls = []

    def fake_call(module, action, params=None, uuid=None, openid=""):
        calls.append(openid)
        return make_body([])

    monkeypatch.setattr(message_sync.middle_client, "call", fake_call)

    message_sync.sync_once(app)

    assert calls == []


def test_sync_voice_and_emoji_mapping(app, monkeypatch):
    """微信 34语音 / 47表情 映射到业务端 6/7（只收不发，V2 文档）。"""
    items = [
        make_item(msg_id="m1", msg_type=34,
                  content='<msg><voicemsg voicelength="3000" aeskey="k" /></msg>'),
        make_item(msg_id="m2", msg_type=47,
                  content='<msg><emoji md5="abc123" len="12345" /></msg>'),
    ]
    patch_pull(monkeypatch, make_body(items))

    message_sync.sync_once(app)

    types = [m.msg_type for m in Message.query.order_by(Message.id)]
    assert types == [Message.MSG_VOICE, Message.MSG_EMOJI]
    conv = Conversation.query.one()
    assert conv.last_msg == "[表情]"  # 会话摘要显示标签


# ---------- msg_type=1 里塞 XML 的内容重分类（2026-10-31 实测） ----------

IMG_XML = ('<msg><img aeskey="k1" encryver="1" cdnthumbaeskey="k1" '
           'cdnthumburl="http://img.example/1" cdnthumbwidth="180" cdnthumbheight="84" '
           'length="12345" /></msg>')
LINK_XML = ('<msg><appmsg appid="" sdkver="0"><title>活动报名</title>'
            '<des>点击查看详情</des><type>5</type>'
            '<url>https://mp.weixin.qq.com/s/abc</url></appmsg></msg>')
FILE_XML = ('<msg><appmsg appid="" sdkver="0"><title>报价单.pdf</title>'
            '<des></des><type>6</type>'
            '<url>https://file.example/pdf</url></appmsg></msg>')
REVOKE_TMPL = ('<sysmsg type="revokemsg"><revokemsg><msgid>0</msgid>'
               '<newmsgid>{newmsgid}</newmsgid>'
               '<replacemsg><![CDATA[{text}]]></replacemsg>'
               '</revokemsg></sysmsg>')


def test_sync_image_xml_reclassified(app, monkeypatch):
    """msg_type=1 但 content 是图片 XML：还原为图片消息。"""
    patch_pull(monkeypatch, make_body([make_item(msg_id="mi", new_msg_id="ni", content=IMG_XML)]))

    message_sync.sync_once(app)

    msg = Message.query.one()
    assert msg.msg_type == Message.MSG_IMAGE


def test_sync_link_appmsg_reclassified(app, monkeypatch):
    """msg_type=1 但 content 是链接 appmsg：还原为链接消息并解析卡片信息。"""
    patch_pull(monkeypatch, make_body([make_item(msg_id="ml", new_msg_id="nl", content=LINK_XML)]))

    message_sync.sync_once(app)

    msg = Message.query.one()
    assert msg.msg_type == Message.MSG_LINK
    assert msg.payload["app"] == {
        "title": "活动报名", "desc": "点击查看详情", "url": "https://mp.weixin.qq.com/s/abc",
    }


def test_sync_file_appmsg_reclassified(app, monkeypatch):
    """msg_type=1 但 content 是文件 appmsg（type=6）：还原为文件消息。"""
    patch_pull(monkeypatch, make_body([make_item(msg_id="mf", new_msg_id="nf", content=FILE_XML)]))

    message_sync.sync_once(app)

    msg = Message.query.one()
    assert msg.msg_type == Message.MSG_FILE
    assert msg.payload["app"]["title"] == "报价单.pdf"


# ---------- 引用消息（appmsg type=57 带 refermsg，2026-11-04 实测） ----------

QUOTE_XML = ('<msg><appmsg appid="" sdkver="0"><title>对</title><des />'
             '<type>57</type><url />'
             '<refermsg><type>1</type><svrid>3846952813383849708</svrid>'
             '<fromusr>25303420694@chatroom</fromusr><chatusr>wxid_tang</chatusr>'
             '<displayname>唐秋琪</displayname><content>现在送吗</content>'
             '<createtime>1793442615</createtime></refermsg></appmsg></msg>')
QUOTE_CDATA_XML = ('<msg><appmsg><title><![CDATA[@佛山巴博瑞 没有啊]]></title>'
                   '<des /><type>57</type>'
                   '<refermsg><type>1</type>'
                   '<svrid><![CDATA[3547892121131514259]]></svrid>'
                   '<displayname><![CDATA[佛山巴博瑞 啊洪]]></displayname>'
                   '<content><![CDATA[有没有安装注意事项]]></content></refermsg>'
                   '</appmsg></msg>')


def test_sync_quote_appmsg_reclassified(app, monkeypatch):
    """msg_type=49 的引用 appmsg（type=57）：还原为引用消息并提取引用信息。"""
    patch_pull(monkeypatch, make_body([make_item(
        msg_id="mq", new_msg_id="nq", msg_type="49", content=QUOTE_XML)]))

    message_sync.sync_once(app)

    msg = Message.query.one()
    assert msg.msg_type == Message.MSG_QUOTE
    assert msg.payload["quote"] == {"reply": "对", "name": "唐秋琪", "text": "现在送吗"}
    conv = Conversation.query.one()
    assert conv.last_msg == "[引用] 对"


def test_sync_quote_appmsg_cdata(app, monkeypatch):
    """CDATA 风格的引用 XML（部分设备实测）：同样识别为引用消息。"""
    patch_pull(monkeypatch, make_body([make_item(
        msg_id="mq2", new_msg_id="nq2", msg_type="49", content=QUOTE_CDATA_XML)]))

    message_sync.sync_once(app)

    msg = Message.query.one()
    assert msg.msg_type == Message.MSG_QUOTE
    assert msg.payload["quote"] == {
        "reply": "@佛山巴博瑞 没有啊", "name": "佛山巴博瑞 啊洪", "text": "有没有安装注意事项",
    }


def test_quote_info_media_refer_as_label():
    """引用的是图片等媒体消息：refermsg.content 是 XML，转 [图片] 标签展示。"""
    from xml.sax.saxutils import escape

    media_quote = ('<msg><appmsg><title>收到</title><type>57</type>'
                   '<refermsg><type>3</type><displayname>李工</displayname>'
                   f'<content>{escape(IMG_XML)}</content></refermsg></appmsg></msg>')
    assert msg_xml.classify(QUOTE_XML) == msg_xml.QUOTE
    assert msg_xml.quote_info(media_quote) == {
        "reply": "收到", "name": "李工", "text": "[图片]",
    }
    # 部分渠道引用内容带发送者前缀（实测 "wxid_xxx:\n<msg>..."）：同样转标签
    prefixed_quote = ('<msg><appmsg><title>收到</title><type>57</type>'
                      '<refermsg><type>3</type><displayname>李工</displayname>'
                      f'<content>wxid_abc123:{escape(IMG_XML)}</content></refermsg></appmsg></msg>')
    assert msg_xml.quote_info(prefixed_quote) == {
        "reply": "收到", "name": "李工", "text": "[图片]",
    }
    assert msg_xml.quote_info(LINK_XML) == {}  # 非引用 appmsg 返回空


def test_quote_refer_svrid():
    """提取 refermsg svrid（原消息 new_msg_id）；无 refermsg / 无 svrid 返回 None。

    是否为图片不在 XML 层判定（企微客服引用 content 为空），由 quote_media
    按库内原消息 msg_type 判定。
    """
    from xml.sax.saxutils import escape

    media_quote = ('<msg><appmsg><title>收到</title><type>57</type>'
                   '<refermsg><type>3</type><svrid>9001</svrid><displayname>李工</displayname>'
                   f'<content>{escape(IMG_XML)}</content></refermsg></appmsg></msg>')
    assert msg_xml.quote_refer_svrid(media_quote) == "9001"
    # 企微客服（openim）引用：type=0、content 为空、svrid 带 CDATA
    openim_quote = ('<msg><appmsg><title>安排了吧</title><type>57</type><refermsg>'
                    '<type>0</type><svrid><![CDATA[1007512725332289483]]></svrid>'
                    '<content /><ref_msg_text><![CDATA["小贺：\n[图片]"]]></ref_msg_text>'
                    '</refermsg></appmsg></msg>')
    assert msg_xml.quote_refer_svrid(openim_quote) == "1007512725332289483"
    assert msg_xml.quote_refer_svrid("不是xml") is None


def test_sync_image_payload_carries_size(app, monkeypatch):
    """图片 XML 自带缩略图宽高：随 payload 下发（前端精确占位）；缺失则不带。"""
    from backend.ws import hub

    broadcasts = []
    monkeypatch.setattr(hub, "broadcast", lambda event, data: broadcasts.append((event, data)))

    patch_pull(monkeypatch, make_body([make_item(
        msg_id="mi2", new_msg_id="img-nid2", msg_type="1", content=IMG_XML)]))
    message_sync.sync_once(app)

    saved = Message.query.filter_by(new_msg_id="img-nid2").one()
    assert saved.payload.get("w") == 180
    assert saved.payload.get("h") == 84

    no_size_xml = '<msg><img aeskey="k2" cdnthumburl="http://img.example/2" /></msg>'
    patch_pull(monkeypatch, make_body([make_item(
        msg_id="mi3", new_msg_id="img-nid3", msg_type="1", content=no_size_xml)]))
    message_sync.sync_once(app)
    saved = Message.query.filter_by(new_msg_id="img-nid3").one()
    assert "w" not in saved.payload


def test_sync_quote_image_broadcast_carries_media_id(app, monkeypatch):
    """引用图片且 svrid 对上库里原图消息：广播 payload.quote 带 media_id（前端渲染缩略图）。"""
    from xml.sax.saxutils import escape

    from backend.ws import hub

    broadcasts = []
    monkeypatch.setattr(hub, "broadcast", lambda event, data: broadcasts.append((event, data)))

    patch_pull(monkeypatch, make_body([make_item(
        msg_id="mi", new_msg_id="img-nid", msg_type="1", content=IMG_XML)]))
    message_sync.sync_once(app)
    media_quote = ('<msg><appmsg><title>收到</title><type>57</type>'
                   '<refermsg><type>3</type><svrid>img-nid</svrid><displayname>李工</displayname>'
                   f'<content>{escape(IMG_XML)}</content></refermsg></appmsg></msg>')
    patch_pull(monkeypatch, make_body([make_item(
        msg_id="mq3", new_msg_id="nq3", msg_type="49", content=media_quote)]))
    message_sync.sync_once(app)

    image_id = Message.query.filter_by(new_msg_id="img-nid").one().id
    payload = broadcasts[-1][1]["payload"]
    assert payload["quote"]["media_id"] == image_id
    assert payload["quote"]["text"] == "[图片]"
    assert payload["quote"]["w"] == 180  # 引用缩略图同样带原消息宽高，精确占位
    assert payload["quote"]["h"] == 84


def test_sync_quote_openim_empty_content_gets_media_id(app, monkeypatch):
    """企微客服引用（type=0、content 为空、svrid 带 CDATA）：按库内原图消息判定并注入。"""
    from backend.ws import hub

    broadcasts = []
    monkeypatch.setattr(hub, "broadcast", lambda event, data: broadcasts.append((event, data)))

    patch_pull(monkeypatch, make_body([make_item(
        msg_id="mo", new_msg_id="om-nid", msg_type="1", content=IMG_XML)]))
    message_sync.sync_once(app)
    openim_quote = ('<msg><appmsg><title>安排了吧</title><type>57</type><refermsg>'
                    '<type>0</type><svrid><![CDATA[om-nid]]></svrid>'
                    '<content /><ref_msg_text><![CDATA["小贺：\n[图片]"]]></ref_msg_text>'
                    '</refermsg></appmsg></msg>')
    patch_pull(monkeypatch, make_body([make_item(
        msg_id="mq4", new_msg_id="nq4", msg_type="49", content=openim_quote)]))
    message_sync.sync_once(app)

    image_id = Message.query.filter_by(new_msg_id="om-nid").one().id
    payload = broadcasts[-1][1]["payload"]
    assert payload["quote"]["media_id"] == image_id
    assert payload["quote"]["text"] == "[图片]"  # content 为空，展示文本也补上


def test_quote_media_fallback_no_origin(app):
    """svrid 对不上库内消息 / 原消息不是图片：不注入 media_id，前端回退标签。"""
    from xml.sax.saxutils import escape

    from backend.services.quote_media import with_media_id

    payload = {"quote": {"reply": "收到", "name": "李工", "text": "[图片]"}}
    media_quote = ('<msg><appmsg><title>收到</title><type>57</type>'
                   '<refermsg><type>3</type><svrid>ghost</svrid><displayname>李工</displayname>'
                   f'<content>{escape(IMG_XML)}</content></refermsg></appmsg></msg>')
    out = with_media_id(payload, media_quote)
    assert "media_id" not in out["quote"]

    # svrid 对上了但原消息是文本：同样不注入
    text_msg_quote = ('<msg><appmsg><title>好的</title><type>57</type>'
                      '<refermsg><type>1</type><svrid>txt-nid</svrid><displayname>唐</displayname>'
                      '<content>现在送吗</content></refermsg></appmsg></msg>')
    conv = Conversation(openid="dev01", wxid="room1", name="群一")
    db.session.add(conv)
    db.session.commit()
    db.session.add(Message(conversation_id=conv.id, msg_type=Message.MSG_TEXT,
                           direction=1, new_msg_id="txt-nid", content="现在送吗"))
    db.session.commit()
    out = with_media_id({"quote": {"reply": "好的", "name": "唐", "text": "现在送吗"}},
                        text_msg_quote)
    assert "media_id" not in out["quote"]

    # 引用纯文本 / 无 quote 的 payload：原样返回
    assert with_media_id({"quote": {"reply": "对", "name": "唐", "text": "好"}}, QUOTE_XML) == {
        "quote": {"reply": "对", "name": "唐", "text": "好"}
    }
    assert with_media_id(None, QUOTE_XML) is None


def test_sync_revoke_marks_original(app, monkeypatch):
    """客户撤回：通知本身不入库，按 newmsgid 定位原消息打 revoked 标记并广播。"""
    patch_pull(monkeypatch, make_body([make_item(msg_id="m1", new_msg_id="n1")]))
    message_sync.sync_once(app)

    from backend.ws import hub
    broadcasts = []
    monkeypatch.setattr(hub, "broadcast", lambda event, data: broadcasts.append((event, data)))
    patch_pull(monkeypatch, make_body([
        make_item(msg_id="mr", new_msg_id="nr",
                  content=REVOKE_TMPL.format(newmsgid="n1", text="你撤回了一条消息")),
    ]))
    message_sync.sync_once(app)

    assert Message.query.count() == 1  # 撤回通知没有作为新消息入库
    msg = Message.query.one()
    assert msg.payload["revoked"] is True
    conv = Conversation.query.one()
    assert conv.last_msg == "对方撤回了一条消息"  # 客户撤回，不能照抄 replacemsg 的"你撤回了"
    assert broadcasts == [("message_revoked", {"message_id": msg.id, "conversation_id": conv.id,
                                               "direction": Message.DIR_IN, "openid": "dev01"})]


def test_sync_self_revoke_marks_original(app, monkeypatch):
    """自己撤回：原消息（direction=2）打 revoked 标记，前端据此提供重新编辑。"""
    patch_pull(monkeypatch, make_body([make_item(
        is_sender=1, from_wxid="wxid_me", to_wxid="wxid_customer",
        msg_id="m1", new_msg_id="n1")]))
    message_sync.sync_once(app)

    patch_pull(monkeypatch, make_body([make_item(
        is_sender=1, from_wxid="wxid_me", to_wxid="wxid_customer",
        msg_id="mr", new_msg_id="nr",
        content=REVOKE_TMPL.format(newmsgid="n1", text="你撤回了一条消息"))]))
    message_sync.sync_once(app)

    msg = Message.query.one()
    assert msg.direction == Message.DIR_OUT
    assert msg.payload["revoked"] is True


def test_sync_revoke_miss_falls_back(app, monkeypatch):
    """原消息不在库里：撤回通知落一条系统灰条兜底，通知重推不重复落行。"""
    patch_pull(monkeypatch, make_body([
        make_item(msg_id="mr", new_msg_id="nr",
                  content=REVOKE_TMPL.format(newmsgid="n404", text="你撤回了一条消息")),
    ]))
    message_sync.sync_once(app)

    rows = Message.query.all()
    assert len(rows) == 1
    assert rows[0].payload == {"system": True}
    # replacemsg 按设备主人视角写"你撤回了"，客户撤回必须重写为"对方"
    assert rows[0].content == "对方撤回了一条消息"
    assert rows[0].sender_name == "系统"

    # 同一条通知重推（中间方重发）：middle_msg_id 去重
    message_sync.sync_once(app)
    assert Message.query.count() == 1


def test_sync_group_revoke_keeps_nickname(app, monkeypatch):
    """群聊撤回：replacemsg 自带发言人昵称，兜底灰条直接引用。"""
    patch_pull(monkeypatch, make_body([
        make_item(from_wxid="88888888@chatroom", msg_id="mgr", new_msg_id="ngr",
                  content=REVOKE_TMPL.format(
                      newmsgid="n404", text='"佛山巴博瑞 啊圣" 撤回了一条消息')),
    ]))
    message_sync.sync_once(app)

    row = Message.query.one()
    assert row.content == '"佛山巴博瑞 啊圣" 撤回了一条消息'
    conv = Conversation.query.one()
    assert conv.chat_type == Conversation.CHAT_GROUP
    assert conv.last_msg == '"佛山巴博瑞 啊圣" 撤回了一条消息'
