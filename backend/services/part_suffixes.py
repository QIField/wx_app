"""配件名后缀表 + 两步法匹配。

设计原则
========
为什么不用正则 ``[\u4e00-\u9fa5]{2,8}(?:suffix)`` ？
  贪婪量词 ``{2,8}`` 会先吃掉尽可能多的汉字，导致 alternative 里的长后缀
  没机会匹配。比如 "点火线圈"：
    正则先让 ``{2,8}`` 吃掉 "点火"（2字），再尝试后缀 alternative。
    "点火线圈"（4字）对剩下的 "线圈" 无法匹配；但单字 "线" 能命中 → "点火线"。
  同理 "火花塞" 会被 "火" 抢走。

两步法彻底绕开这个问题：
  1. 从文本里切出所有连续中文块（2-12 字）。
  2. 对每个块，按后缀**长度从大到小**尝试 ``str.endswith``，
     命中第一个就停 → 自动选最长的正确后缀。

后缀表来源
========
后缀表已迁移至 :mod:`backend.services.part_suffix_list`。
全量配件库（~41000 条真实配件名）高频词筛选 + 手动补漏 → 去重 + 长度降序。

匹配覆盖率
========≈ 65% 的真实配件名能被匹配（剩余 35% 交给 AI extract_parts 兜底）。
rule_extract 是快速路径，覆盖不到的不会阻塞流程——AI 模式会继续尝试。
"""
from __future__ import annotations

import re
from typing import Iterable

from backend.services.part_suffix_list import _PART_SUFFIX


# 中文块里的连词/介词/助词 —— 如果块以这些开头，基本就是"连词+配件"的格式
# （比如 "的节温器"、"和正时链条"），应尝试拆成子块。
# 注意：**方位词（前/后/左/右/上/下/内/外）不在此列**，因为它们作为前缀
# 在配件名里极其常见（前杠、前刹车片、前保险杠、前减震器...）。
_BLOCK_POLLUTION_WORDS = frozenset(
    '的 和 与 到 及 或 被 也 但 为 把 让 用 以 于 由 对 向 从 '
    '在 是 有 不 没 要 来 去 这 那 我 你 他 她 它 我们 你们 他们'
    .split()
)

# 拆子块时的分隔符集合：如果一个块里含这些词，应尝试在它们之间找子块
_BLOCK_SPLIT_WORDS = frozenset(
    '的 和 与 及 或 到 被 但 也 为 把 让 用 以 由 对 向 从 在 是'
    .split()
)


# ---------------------------------------------------------------------------
# 两步法匹配：先切中文块，再按后缀表尝试 endswith
# ---------------------------------------------------------------------------

# 中文块正则（2-12 字，覆盖绝大多数配件名长度）
_CN_BLOCK_RE = re.compile(r'[\u4e00-\u9fa5]{2,12}')


def _is_polluted(block: str) -> bool:
    """判断中文块是否以连词开头（应跳过并尝试拆子块）。

    规则：块的**第一个字**是 pollution word。
    不检查中间的连词——那交给 _split_polluted_block 处理。
    """
    if block[0] in _BLOCK_POLLUTION_WORDS:
        return True
    return False


def _split_polluted_block(block: str) -> list[str]:
    """把以连词开头的污染块拆成子块，尝试在里面找配件名。

    例子："的节温器和正时链条" → ["节温器", "正时链条"]
    """
    # 把分隔词替换成空格，然后按空格拆，过滤空字符串
    pattern = '|'.join(re.escape(w) for w in sorted(_BLOCK_SPLIT_WORDS, key=len, reverse=True))
    parts = re.sub(pattern, ' ', block)
    return [p for p in parts.split() if 2 <= len(p) <= 12]


def _try_match_block(block: str) -> str | None:
    """对单个中文块尝试匹配后缀表，返回最具体的配件名。

    策略：
      1. 直接匹配原 block → 如果命中的是**多字后缀**（≥2字），
         说明原 block 本身就是干净的配件名或带修饰的完整配件名，直接返回。
      2. 如果直接命中的是**单字后缀**，说明命中可能太泛，
         尝试先 strip 干扰词再匹配，看能不能得到更具体的配件名。
      3. 如果直接没命中，也尝试 strip 干扰词后再匹配。
    """
    # 1. 直接尝试 — 找命中的后缀
    direct_suffix_hit = None
    for suffix in _PART_SUFFIX:
        if block.endswith(suffix):
            direct_suffix_hit = suffix
            break

    # 如果直接命中多字后缀（≥2字）→ 说明这个块本身就是干净的
    if direct_suffix_hit and len(direct_suffix_hit) >= 2:
        return block

    # 2. 直接命中单字后缀 或 没命中 → 尝试 strip 干扰词
    stripped = _strip_trailing_noise(block)
    if stripped and stripped != block:
        for suffix in _PART_SUFFIX:
            if stripped.endswith(suffix):
                return stripped  # strip 后命中的（即使是单字）也更靠谱

    # 3. strip 后也没命中 → 返回直接匹配的结果（可能是单字后缀命中的）
    if direct_suffix_hit:
        return block

    return None


# 尾部干扰词：客户询价时跟在配件名后面的价格/询问/量词等
# 长度从长到短排序（先尝试长的干扰词）
_TRAILING_NOISE_WORDS = tuple(sorted([
    # 价格/询问（≥2字）
    '多少钱', '给个价', '什么价', '报个价', '出个价', '有货吗', '有货没', '有吗',
    '来一个', '来一套', '来一组', '来一对',
    '换一下', '换一个', '换一下', '多少钱', '价格', '价钱', '报价', '询价', '问价',
    '贵吗', '便宜吗', '好吗', '行吗', '可以吗', '多少钱呢', '报价呢',
    '怎么样', '好不好', '行不行',
    # 量词（1-2字，排在长干扰词后面）
    '一个', '一件', '一套', '一组', '一对', '一只', '一条', '一副', '一片', '两个',
    '多钱', '咋卖', '怎么卖', '如何卖',
    '呢', '啊', '吧', '哦', '哈', '啦', '了', '哦',
], key=len, reverse=True))


def _strip_trailing_noise(block: str) -> str:
    """从中文块尾部去掉常见干扰词，返回更可能是纯配件名的子串。

    例："节温器多少钱" → "节温器"，"火花塞报价" → "火花塞"
    例："大灯一个多少钱" → 先切 "大灯"（匹配到 "灯" 后缀）
    """
    cur = block
    # 反复去掉尾部干扰词，直到没有可去的或剩余块太短
    while len(cur) >= 2:
        matched_noise = False
        for noise in _TRAILING_NOISE_WORDS:
            if cur.endswith(noise):
                cur = cur[: -len(noise)]
                matched_noise = True
                break
        if not matched_noise:
            break
    return cur if len(cur) >= 2 else ""


def match_part_names(text: str | None) -> list[str]:
    """文本 → 配件名列表（去重、保留首次出现顺序）。

    实现：
      1. 从文本里切出所有 2-12 字的连续中文块。
      2. 对每个块：
         - 如果以连词开头 → 尝试拆成子块分别匹配。
         - 否则直接匹配后缀表。
      3. 对每个块按后缀长度从大到小尝试 ``str.endswith``，
         命中第一个就停 → 自动选最长正确后缀。
      4. 去重、按首次出现顺序返回。

    为什么能解决贪婪匹配问题？
      正则 ``[\u4e00-\u9fa5]{2,8}`` 会先贪婪吃掉尽可能多的汉字，
      导致 "点火线圈" 被拆成 "点火" + "线"，剩下的 "线圈" 根本没机会匹配。
      两步法是 str.endswith 从**词尾**往前找，天然不被贪婪影响。

    Args:
        text: 要扫描的文本（可以是多行）。

    Returns:
        匹配到的配件名列表。如果文本为 None 或不含中文，返回空列表。
    """
    if not text:
        return []

    seen: set[str] = set()
    result: list[str] = []

    def _add(name: str):
        if name not in seen:
            seen.add(name)
            result.append(name)

    for block in _CN_BLOCK_RE.findall(text):
        if _is_polluted(block):
            # 被连词污染的块 → 拆子块分别尝试
            for sub in _split_polluted_block(block):
                hit = _try_match_block(sub)
                if hit:
                    _add(hit)
            continue

        hit = _try_match_block(block)
        if hit:
            _add(hit)

    return result


def has_any_part_name(text: str | None) -> bool:
    """判断文本里是否包含至少一个可识别的配件名（供 should_trigger 使用）。

    逻辑与 match_part_names 完全一致（包括 strip 干扰词、拆污染块等），
    只返回 True/False。
    """
    if not text:
        return False

    for block in _CN_BLOCK_RE.findall(text):
        if _is_polluted(block):
            for sub in _split_polluted_block(block):
                if _try_match_block(sub):
                    return True
            continue
        if _try_match_block(block):
            return True
    return False


# 保留 PART_NAME_RE 别名做兼容 —— rule_extract.py 之前用的是正则对象接口。
# 新代码请直接调用 match_part_names() / has_any_part_name()。
# 这个正则**不再是核心匹配逻辑**，只保留给 read_text 场景兜底。
PART_NAME_RE = re.compile(
    r"[\u4e00-\u9fa5]{2,12}(?:" + "|".join(re.escape(s) for s in _PART_SUFFIX) + r")"
)
