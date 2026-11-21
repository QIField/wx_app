"""文本处理工具函数 — 跨服务共用的纯函数集合。

放在独立模块避免重复代码散落各处，也方便单测覆盖。
"""
import re

# 匹配一行内空格/制表符分隔的数字片段（重复应用直到收敛）
# 只匹配「纯数字 + 空白 + 纯数字」，不会把 "宝马 530Li" 里的 530 和 3 拼起来
# （因为 530 后面是字母 L，不是空格+数字）。
_SPACED_DIGITS_RE = re.compile(r'(\d+)[ \t]+(\d+)')


def normalize_spaced_digits(text: str) -> str:
    """将每行内空格/制表符分隔的数字片段合并为连续数字。

    例如："264 200 3201" → "2642003201"
    按行处理，跨行不合并（换行符分隔的一定是不同号码）。

    Args:
        text: 原始文本，可能包含多行。

    Returns:
        归一化后的文本，每行内空格分隔的数字已合并。
    """
    result_lines = []
    for line in (text or "").splitlines():
        cleaned = line
        prev = None
        while prev != cleaned:
            prev = cleaned
            cleaned = _SPACED_DIGITS_RE.sub(r'\1\2', cleaned)
        result_lines.append(cleaned)
    return '\n'.join(result_lines)
