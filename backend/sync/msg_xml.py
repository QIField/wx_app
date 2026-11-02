"""微信消息 content 的 XML 解析：真实类型判定与链接卡片信息提取。

中间方把图片/链接/撤回等消息统一塞进 msg_type=1（文本）的 content 里
（2026-10-31 实测），这里按 XML 根节点与子节点把真实类型还原出来，
供收消息入库时重新分类、前端按真实消息渲染。
"""
import re
import xml.etree.ElementTree as ET

# 分类结果常量（收消息侧映射到 Message.MSG_*，前端同语义）
REVOKE = "revoke"   # <sysmsg type="revokemsg"> 撤回通知
IMAGE = "image"     # <msg><img …> 图片
VIDEO = "video"     # <msg><videomsg …> 视频
VOICE = "voice"     # <msg><voicemsg …> 语音
EMOJI = "emoji"     # <msg><emoji …> 表情
FILE = "file"       # <appmsg><type>6 文件
LINK = "link"       # <appmsg> 其余（链接/小程序/合并聊天等，按链接卡片渲染）

_APPMSG_FILE_TYPE = 6  # appmsg 子类型 6 = 文件


def _parse(content):
    """解析 content XML，失败返回 None（纯文本走不到这里）。"""
    text = (content or "").strip()
    if not text.startswith("<"):
        return None
    try:
        return ET.fromstring(text)
    except ET.ParseError:
        return None


def classify(content):
    """content XML → 分类常量；非 XML 或无法识别返回 None（按原文文本处理）。"""
    root = _parse(content)
    if root is None:
        return None
    tag = root.tag.lower()
    if tag == "sysmsg":
        return REVOKE if (root.attrib.get("type") or "") == "revokemsg" else None
    if tag != "msg":
        return None
    if root.find("img") is not None:
        return IMAGE
    if root.find("videomsg") is not None:
        return VIDEO
    if root.find("voicemsg") is not None:
        return VOICE
    if root.find("emoji") is not None:
        return EMOJI
    app = root.find("appmsg")
    if app is not None:
        try:
            sub = int((app.findtext("type") or "").strip() or 0)
        except ValueError:
            sub = 0
        return FILE if sub == _APPMSG_FILE_TYPE else LINK
    return None


def sysmsg_text(content):
    """未分类的 <sysmsg> 系统 XML → 自带的可读灰条文案；取不到返回 None。

    撤回样式文案在 <replacemsg>，部分事件在 sysmsg 直接子节点 <template>。
    注意拍一拍的 template 嵌在 <pat> 里、群事件在 content_template 里，
    分别由 pat_info/template_text 处理，这里都取不到。
    """
    root = _parse(content)
    if root is None or root.tag.lower() != "sysmsg":
        return None
    if (root.attrib.get("type") or "").lower() == "revokemsg":
        return None  # 撤回走 revoke 专门流程，不在这里转文案
    for tag in ("replacemsg", "template"):
        node = root.find(tag)
        if node is None:
            continue
        text = "".join(node.itertext()).strip()
        if text:
            return text
    return None


def pat_info(content):
    """<sysmsg type="pat"> 拍一拍 → {chatusername, fromusername,
    pattedusername, patsuffix}；非拍一拍返回空 dict。

    XML 里只有 wxid 没有昵称，昵称由 message_sync 查群成员名册补齐。
    """
    root = _parse(content)
    if root is None or (root.attrib.get("type") or "").lower() != "pat":
        return {}
    node = root.find("pat")
    if node is None:
        return {}
    pick = lambda tag: (node.findtext(tag) or "").strip()
    return {
        "chatusername": pick("chatusername"),
        "fromusername": pick("fromusername"),
        "pattedusername": pick("pattedusername"),
        "patsuffix": pick("patsuffix"),
    }


def template_text(content):
    """<sysmsg type="sysmsgtemplate"> 群事件 → 替换占位符后的可读文案。

    结构实测（2026-11-02）：<template>$name$已邀请…</template> 占位符对应
    <link_list><link name="name"><memberlist><member><nickname>；
    同名多成员用 <separator> 连接。有占位符替换不齐就返回 None（转噪音）。
    """
    root = _parse(content)
    if root is None:
        return None
    ct = root.find(".//content_template")
    if ct is None:
        return None
    tmpl = (ct.findtext("template") or "").strip()
    if not tmpl:
        return None
    values = {}
    for link in ct.findall("link_list/link"):
        name = link.attrib.get("name") or ""
        nicknames = [
            n for n in (
                (m.findtext("nickname") or "").strip()
                for m in link.findall("memberlist/member")
            ) if n
        ]
        if name and nicknames:
            sep = (link.findtext("separator") or "、").strip() or "、"
            values[name] = sep.join(nicknames)
    missing = False

    def _fill(match):
        nonlocal missing
        value = values.get(match.group(1))
        if value is None:
            missing = True
            return match.group(0)
        return value

    text = re.sub(r"\$(\w+)\$", _fill, tmpl).strip()
    if missing or not text:
        return None
    return text


def revoke_info(content):
    """撤回通知 → {msgid, newmsgid, replacemsg}；解析失败返回空 dict。"""
    root = _parse(content)
    if root is None:
        return {}
    node = root.find("revokemsg")
    if node is None:
        return {}
    return {
        "msgid": (node.findtext("msgid") or "").strip(),
        "newmsgid": (node.findtext("newmsgid") or "").strip(),
        "replacemsg": (node.findtext("replacemsg") or "").strip(),
    }


def app_info(content):
    """链接/文件卡片信息 → {title, desc, url}；非 appmsg 返回空 dict。"""
    root = _parse(content)
    if root is None:
        return {}
    app = root.find("appmsg")
    if app is None:
        return {}
    return {
        "title": (app.findtext("title") or "").strip(),
        "desc": (app.findtext("des") or "").strip(),
        "url": (app.findtext("url") or "").strip(),
    }
