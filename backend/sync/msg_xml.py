"""微信消息 content 的 XML 解析：真实类型判定与链接卡片信息提取。

中间方把图片/链接/撤回等消息统一塞进 msg_type=1（文本）的 content 里
（2026-10-31 实测），这里按 XML 根节点与子节点把真实类型还原出来，
供收消息入库时重新分类、前端按真实消息渲染。
"""
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
