"""出参脱敏（wxid 全链路隐藏方案的唯一守门员）。

规则（方案原型 prototypes/wxid-anonymize/index.html）：
- alias：HMAC-SHA256(wxid, SECRET_KEY) 截断 6 位大写短码——不可逆、同码同人、
  不同人互异；既是未解析名称用户的显示名，也是所有联系人的展示标识。
- 名称未解析（空 / 仍是 wxid 原文）→ 出参 name=None，前端统一拼「匿名 + 编码」。
- 名称未解析 → avatar 一并置 None（前端画匿名头像）。

wxid 只允许存在于数据库与后端内部逻辑；所有 API / WS 出参一律经此模块清洗。
"""
import hashlib
import hmac

from backend.config import SECRET_KEY

_ALIAS_LEN = 6


def alias_of(wxid):
    """wxid → 稳定匿名短码（单向，无法反推原文）。"""
    if not wxid:
        return ""
    digest = hmac.new(
        SECRET_KEY.encode("utf-8"), wxid.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return digest[:_ALIAS_LEN].upper()


def anon_label(wxid):
    """未解析名称用户的统一代称：「匿名 + 编码」。"""
    code = alias_of(wxid)
    return f"匿名 {code}" if code else "匿名"


def resolved_name(name, wxid):
    """名称是否已解析：为空或仍是 wxid 原文都算未解析，返回 None。"""
    return name if name and name != wxid else None


def avatar_or_none(name, avatar):
    """头像随名称走：名称未解析则头像一并匿名（不下发）。"""
    return avatar if name else None
