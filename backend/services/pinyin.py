"""拼音工具：后端 pypinyin 统一预计算，前端零依赖。

所有搜索框（会话列表/通讯录/账号管理/群成员 @提及）共用，
出参统一携带 pinyin（全拼）/ initials（首字母）两个字段，
前端 matchKeyword 直接把它们当普通字段匹配即可。
"""
from pypinyin import lazy_pinyin, Style


def full_pinyin(name):
    """中文名 → 全拼小写（如 张峰 → zhangfeng）；空名/None 返回空串。

    非 ASCII 字符交给 lazy_pinyin 原样透传（英文昵称不受影响）。
    """
    if not name:
        return ""
    return "".join(lazy_pinyin(name)).lower()


def initials(name):
    """中文名 → 拼音首字母小写（如 张峰 → zf）；空名/None 返回空串。"""
    if not name:
        return ""
    return "".join(lazy_pinyin(name, style=Style.FIRST_LETTER)).lower()


def pinyin_tokens(name):
    """中文名 → 逐字拼音 token 列表（小写，如 张峰 → ['zhang','feng']）。

    供"字边界对齐"的拼音匹配用：全拼字符串直接 includes 会跨字误命中
    （hang|zhou|sheng|chi 拼接串里 housheng 跨 zhou|sheng 边界），必须按 token 校验。
    """
    if not name:
        return []
    return [t.lower() for t in lazy_pinyin(name)]


def pinyin_hit(tokens, kw):
    """拼音命中（字边界对齐）：kw 必须从某个字的拼音**开头**连续拼出。

    张峰 ['zhang','feng']：zhang / zhangfeng / feng 命中（feng 从"峰"的拼音开头起）；
    housheng 对 杭州圣驰 ['hang','zhou','sheng','chi'] 不命中（起点落在 zhou 字中间）。
    """
    if not kw or not tokens:
        return False
    n = len(kw)
    for i in range(len(tokens)):
        seg = ""
        for t in tokens[i:]:
            seg += t
            if len(seg) >= n:
                # 前缀已定：相等即命中，否则再拼也不会命中
                if seg.startswith(kw):
                    return True
                break
    return False


def letter(name):
    """排序字母：首字拼音首字母大写；非 A-Z（数字/符号/未解析）归入 #。"""
    if not name:
        return "#"
    ch = (initials(name)[:1] or name[:1]).upper()
    return ch if "A" <= ch <= "Z" else "#"
