"""启发式配件名 fallback 模块。

职责：当后缀表（match_part_names）没命中时，从客户消息行里
剥掉 VIN/OE/@/链接/品牌车型/数字等噪音，剩下的 2-6 字纯中文
当作"像配件名的词"塞进 part_name。

这个模块只负责"单行 → 候选配件名"的启发式抠词，不碰 VIN/OE 提取
和跨行关联——那些在 rule_extract.py 里。
"""
from __future__ import annotations

import re

from backend.services.local_ocr import VIN_CHARS

# ==================== 正则 pattern ====================

# 剥 VIN（17 位）
_FALLBACK_VIN_RE = re.compile(rf'[{VIN_CHARS}]{{17}}', re.IGNORECASE)
# 剥带前缀的号码 + 纯 6 位以上数字
_FALLBACK_OEM_RE = re.compile(r'\b[A-Z]{1,4}\d{5,}\b|\b\d{6,}\b', re.IGNORECASE)
# 剥 @xxx（@人名）
_FALLBACK_AT_RE = re.compile(r'@[\w\u4e00-\u9fa5\-]+')
# 剥 http(s) 链接
_FALLBACK_URL_RE = re.compile(r'https?://\S+')
# 剥分隔线（——————、————）
_FALLBACK_SEP_RE = re.compile(r'^[\s\-—_=·\.★☆]+$|^[\s]*——+[\s]*$')
# 剥括号里的内容（号码、备注）
_FALLBACK_BRACKET_RE = re.compile(r'[（(][^)）]*[)）]')
# 剥序号前缀：★数字、数字、数字、
_FALLBACK_PREFIX_RE = re.compile(r'^[\s]*[★☆]?[\s]*\d{1,2}[\s]*[、\.．]\s*')

# 剥完噪音后检查候选：是不是 2-6 字纯中文
_PART_CANDIDATE_CN_RE = re.compile(r'^[\u4e00-\u9fa5]{2,6}$')

# ==================== 停用词 ====================

# 明显不是配件名的中文停用词（剥完如果只剩这个就丢掉）
_NOT_PART_CN_WORDS = frozenset({
    '选购链接', '链接', '微信号', '微信', '报价', '询价', '多少钱',
    '原厂', '品牌', '货号', '号码', '价格', '备注', '客户',
    '宝马', '奔驰', '奥迪', '大众', '丰田', '保时捷', '路虎',
    '沃尔沃', '本田', '日产', '福特', '别克', '雪佛兰', '凯迪拉克',
    '雷克萨斯', '英菲尼迪', '讴歌', '马自达', '斯巴鲁', '三菱',
    '现代', '起亚', '双龙', '特斯拉', '理想', '蔚来', '小鹏', '问界',
    '年份', '排量', '手自一体', '自动', '手动', '轿车', 'SUV', '越野',
    '车架号', 'VIN', '车型', '型号', '库存', '现货', '有货', '没货',
    '缺货', '维修', '保养', '更换', '改装',
    '原厂件', '副厂', '品牌件', '拆车件', '二手', '全新',
})


# ==================== 公共函数 ====================


def is_separator_line(line: str) -> bool:
    """这行是不是纯分隔线（——————、———— 等）。调用方跳过。"""
    return bool(_FALLBACK_SEP_RE.match((line or '').strip()))


def strip_to_candidate(line: str) -> str:
    """剥一行里所有噪音，剩下的就是可能的配件名候选。

    剥掉的东西：序号前缀、@人名、链接、括号内容、VIN、OE 号码、
    零散数字、品牌车型停用词、非中文字符。
    """
    cur = line.strip()
    cur = _FALLBACK_PREFIX_RE.sub('', cur)
    cur = _FALLBACK_AT_RE.sub(' ', cur)
    cur = _FALLBACK_URL_RE.sub(' ', cur)
    cur = _FALLBACK_BRACKET_RE.sub(' ', cur)
    cur = _FALLBACK_VIN_RE.sub(' ', cur)
    cur = _FALLBACK_OEM_RE.sub(' ', cur)
    cur = re.sub(r'\d+', ' ', cur)
    for w in sorted(_NOT_PART_CN_WORDS, key=len, reverse=True):
        cur = re.sub(re.escape(w), ' ', cur)
    cur = re.sub(r'[^\u4e00-\u9fa5]', '', cur)
    return cur.strip()


def looks_like_part_name(s: str) -> bool:
    """剥完噪音后剩的是不是"像配件名"的纯中文短词。

    通过条件：2-6 字纯中文 且 不在停用词里。
    """
    if not s or not _PART_CANDIDATE_CN_RE.match(s):
        return False
    if s in _NOT_PART_CN_WORDS:
        return False
    return True


def extract_part_names_fallback(text: str) -> list[str]:
    """逐行启发式抠配件名。

    调用前提：后缀表（match_part_names）对该行没命中。
    返回：从所有没命中的行里抠出的配件名列表（去重、保序）。
    """
    from backend.services.part_suffixes import match_part_names

    names: list[str] = []
    seen: set[str] = set()

    for line in (text or "").splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue

        # 后缀表命中了 → 不用启发式
        if list(match_part_names(line_clean)):
            continue

        # 纯分隔线 → 跳过
        if is_separator_line(line_clean):
            continue

        candidate = strip_to_candidate(line_clean)
        if looks_like_part_name(candidate):
            if candidate not in seen:
                seen.add(candidate)
                names.append(candidate)

    return names
