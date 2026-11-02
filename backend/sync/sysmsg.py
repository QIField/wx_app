"""系统类消息识别：微信不渲染的协议事件与灰条文案。

msg_type=1 的 content 里除媒体/链接卡片外，还塞着微信系统事件：
51 StatusNotify（群已读指针/朋友圈状态）、拍一拍、群事件模板、
游戏中心等。收消息入库（message_sync）与存量回填
（backfill_noise_messages）共用这里的判定：
- 能转可读文案的（拍一拍/群事件/自带 template 的事件）→ 返回灰条文案；
- 微信不渲染或解析不出的 → 标噪音软删，未知样本记日志。
"""
from flask import current_app

from backend.sync import msg_xml

STATUS_NOTIFY = 51  # 微信 raw msg_type：多端状态同步，微信不渲染


def resolve(content, raw_type=0, openid=""):
    """未命中媒体/链接分类的 content → (灰条文案|None, 是否噪音)。

    灰条文案非空时由调用方置 system 标按灰条入库；噪音由调用方软删
    （会话不存在则整条丢弃，不建会话）。
    """
    if raw_type == STATUS_NOTIFY:
        return None, True
    if not (content or "").lstrip().startswith("<"):
        return None, False
    pat = msg_xml.pat_info(content)
    if pat:
        return _pat_gray_text(pat, openid), False
    gray = msg_xml.template_text(content) or msg_xml.sysmsg_text(content)
    if gray:
        return gray, False
    _log_sample(content)
    return None, True


def _pat_gray_text(pat, openid):
    """拍一拍灰条文案：查群成员名册解析昵称，查不到用 wxid 兜底。"""
    from backend.sync import group_member

    wxids = [pat["fromusername"], pat["pattedusername"]]
    profiles = group_member.sender_profiles(openid, pat["chatusername"], wxids)
    who = (profiles.get(wxids[0]) or {}).get("nickname") or wxids[0]
    whom = (profiles.get(wxids[1]) or {}).get("nickname") or wxids[1]
    suffix = (pat.get("patsuffix") or "").strip()
    return f"「{who}」拍了拍「{whom}」{suffix}".strip()


def _log_sample(content):
    """记下无法识别的系统 XML 样本（截断），联调时按样本补充解析规则。"""
    current_app.logger.info("未识别的系统XML样本: %s", content[:200])
