"""普通识别模块（规则驱动，不调 AI）。

职责：消息窗口 → 正则/OCR 提取 → 标准场景列表（与 AI extract_parts 输出格式一致）。

流程：
  1. should_trigger(messages) → 是否需要识别（有 VIN/长数字/图片 才触发）
  2. rule_extract(messages) → 主入口，先各条单独提取，再跨行关联

输出格式（与 AI 返回对齐）：
  [{"vin": str|None, "part_name": str|None, "oem_no": str|None,
    "sender_name": str|None, "inquiry_content": str|None, ...}, ...]
"""
import logging
import re

from backend.models.message import Message
from backend.services.local_ocr import recognize_vin, VIN_CHARS
from backend.services.part_suffixes import match_part_names, has_any_part_name

log = logging.getLogger(__name__)

# ==================== 正则 ====================

# VIN：17 位，排除 O/I/Q（工业标准）
# 注意：不能用 \b，Python 3 Unicode 模式下中文也算 \w，\b 在 VIN+中文之间失效
VIN_RE = re.compile(rf'(?<![{VIN_CHARS}])[{VIN_CHARS}]{{17}}(?![{VIN_CHARS}])', re.IGNORECASE)

# 纯 VIN（整行就是 VIN）
VIN_ONLY_RE = re.compile(rf'^\s*[{VIN_CHARS}]{{17}}\s*$', re.IGNORECASE)

# 号码：连续 6 位以上纯数字（含 6 位）
# 边界：前后不能是 VIN 字符集的成员（防止 VIN 尾巴被截取）
PART_NO_DIGITS_RE = re.compile(
    rf'(?<![{VIN_CHARS}])(\d{{6,}})(?![{VIN_CHARS}])', re.IGNORECASE
)

# 带前缀的号码：1-4 位字母 + 5 位以上数字（如 LR025632、GDB12345）
# 前后边界都排除 VIN 字符集，避免从 VIN 内部截取
PART_NO_PREFIX_RE = re.compile(
    rf'(?<![{VIN_CHARS}])([A-Z]{{1,4}})(\d{{5,}})(?![{VIN_CHARS}])', re.IGNORECASE
)

# 配件名匹配已迁移至 part_suffixes 模块（两步法，绕开正则贪婪问题）。
# 直接使用：from backend.services.part_suffixes import match_part_names, has_any_part_name

# 剥序号前缀：★数字、数字、数字、
_PREFIX_RE = re.compile(r'^[\s]*[★☆]?[\s]*\d{1,2}[\s]*[、\.．]\s*')

# 括号里的号码
_BRACKET_NO_RE = re.compile(r'[（(]([^)）]+)[)）]')

# ==================== 工具函数 ====================


def _has_vin(text: str) -> bool:
    """文本里是否出现 VIN。"""
    return bool(VIN_RE.search(text or ""))


def _has_long_digits(text: str) -> bool:
    """文本里是否出现 ≥6 位连续数字（含纯数字和前缀+数字两种）。"""
    if PART_NO_DIGITS_RE.search(text or ""):
        return True
    if PART_NO_PREFIX_RE.search(text or ""):
        return True
    return False


def _is_meaningless(text: str) -> bool:
    """纯表情/标点/单字 → 不触发识别。"""
    s = (text or "").strip()
    if not s:
        return True
    # 只含标点符号（中文标点 + ASCII 标点）
    if re.fullmatch(r'[\W_]+', s, re.UNICODE):
        return True
    # 只有 1 个汉字或 1 个数字
    if len(s) <= 1:
        return True
    return False


# ==================== 触发条件 ====================


def should_trigger(messages: list[Message]) -> bool:
    """是否需要进入识别流程。

    触发（任一满足）：
      - 客户发图片消息
      - 客户文本含 VIN / ≥6位数字 / 带前缀号码
      - 客户文本含 recognizable 配件名（两步法匹配命中）
    不触发：纯表情、纯标点、纯无意义文字、极短闲聊
    """
    for m in messages:
        if m.direction != Message.DIR_IN:
            continue
        if m.msg_type == Message.MSG_IMAGE:
            return True
        if m.msg_type != Message.MSG_TEXT:
            continue
        text = m.content or ""
        if _is_meaningless(text):
            continue
        if _has_vin(text) or _has_long_digits(text):
            return True
        if has_any_part_name(text):
            return True
    return False


# ==================== 单条提取 ====================


def _extract_vin(text: str) -> str | None:
    """文本 → 第一个合法 VIN（大写）。"""
    m = VIN_RE.search(text or "")
    return m.group().upper() if m else None


def _extract_part_numbers(text: str) -> list[str]:
    """文本 → 号码列表（去重、按原顺序）。

    处理顺序：括号里的号码 → 带前缀的号码 → 纯数字 ≥6 位。
    括号内容可能嵌 VIN，已被跳过。
    """
    found = []
    seen = set()

    def _add(token: str):
        token = token.strip().upper()
        if token and token not in seen and not VIN_RE.fullmatch(token):
            seen.add(token)
            found.append(token)

    # 1. 括号里的号码（如 (LR025632)、(1234567)）
    for m in _BRACKET_NO_RE.finditer(text or ""):
        token = m.group(1).strip()
        if PART_NO_PREFIX_RE.fullmatch(token):
            _add(token)
        elif len(re.sub(r'\D', '', token)) >= 6:
            _add(re.sub(r'\D', '', token))  # 只保留数字部分

    # 2. 带前缀的号码（LR025632）
    for m in PART_NO_PREFIX_RE.finditer(text or ""):
        _add(m.group(1) + m.group(2))

    # 3. 纯数字 ≥6 位
    for m in PART_NO_DIGITS_RE.finditer(text or ""):
        _add(m.group(1))

    return found


def _extract_part_names(text: str) -> list[str]:
    """文本 → 配件名列表。

    处理流程：剥序号前缀 → 正则匹配中文配件名 → 去重。
    """
    names = []
    seen = set()

    for line in (text or "").splitlines():
        # 剥序号前缀：★2、 右正时链板 → 右正时链板
        line = _PREFIX_RE.sub('', line).strip()
        if not line:
            continue
        for name in match_part_names(line):
            if name not in seen:
                seen.add(name)
                names.append(name)

    return names


# ==================== 单条消息 → 场景 ====================


def _extract_from_text_message(msg: Message) -> list[dict]:
    """一条客户文本消息 → 场景列表。

    一条消息可能含：
    - VIN + 配件名 + 号码（最理想）→ 一条场景
    - VIN alone → 只有 VIN 的场景
    - 配件名 + 号码 → 无 VIN 的场景
    - 多条配件/号码 → 按 (vin + parts_group) 拆
    """
    text = msg.content or ""
    vin = _extract_vin(text)
    part_names = _extract_part_names(text)
    part_nos = _extract_part_numbers(text)

    # 如果完全没东西，跳过
    if not vin and not part_names and not part_nos:
        return []

    return [{
        "vin": vin,
        "part_name": ",".join(part_names) if part_names else None,
        "oem_no": ",".join(part_nos) if part_nos else None,
        "sender_name": msg.sender_name,
        "inquiry_content": text[:200],
    }]


def _extract_vin_only_from_message(msg: Message) -> str | None:
    """只提取 VIN（用于跨消息关联，不受 focus 限制）。"""
    if msg.msg_type != Message.MSG_TEXT:
        return None
    return _extract_vin(msg.content or "")


def _extract_from_image_message(msg: Message, all_messages: list[Message], idx: int) -> list[dict]:
    """图片消息 → 场景列表。

    逻辑：
    1. OCR 图片识别 VIN
    2. 向后找最近 3 条客户文本消息，提取配件名和号码
    3. 遇到客服消息停止（窗口里客服已回复就不再关联后续客户消息）
    """
    img_url = (msg.payload or {}).get("img_url") if msg.payload else None
    vin = recognize_vin(img_url) if img_url else None

    part_names = []
    part_nos = []
    sender_name = msg.sender_name

    for j in range(idx + 1, min(idx + 4, len(all_messages))):
        next_msg = all_messages[j]
        if next_msg.direction != Message.DIR_IN:
            break  # 遇到客服消息停止
        if next_msg.msg_type == Message.MSG_TEXT:
            sender_name = sender_name or next_msg.sender_name
            part_names.extend(_extract_part_names(next_msg.content or ""))
            part_nos.extend(_extract_part_numbers(next_msg.content or ""))

    if not vin and not part_names and not part_nos:
        return []

    return [{
        "vin": vin,
        "part_name": ",".join(part_names) if part_names else None,
        "oem_no": ",".join(part_nos) if part_nos else None,
        "sender_name": sender_name,
        "inquiry_content": f"[图片]{img_url and img_url[:60] or ''}",
    }]


# ==================== 跨行关联 ====================


def _cross_link_scenes(raw_scenes: list[dict]) -> list[dict]:
    """多条消息各自提取出的场景 → 跨行合并。

    规则：
    - 同 sender 的场景，如果 A 有 VIN 但没配件，B 有配件但没 VIN → 合并
    - 同 sender 的场景，如果 A 有 VIN+配件，B 有 VIN（相同）+配件 → 合并配件
    - 不同 sender 不合并
    """
    if len(raw_scenes) <= 1:
        return raw_scenes

    groups: dict[str, list[dict]] = {}
    for s in raw_scenes:
        key = (s.get("sender_name") or "") + "|" + (s.get("vin") or "NO_VIN")
        groups.setdefault(key, []).append(s)

    merged = []
    for key, group in groups.items():
        if len(group) == 1:
            merged.append(group[0])
            continue
        # 合并同 VIN 同 sender 的多条
        vins = {s.get("vin") for s in group if s.get("vin")}
        parts = []
        nos = []
        seen_parts = set()
        seen_nos = set()
        for s in group:
            for p in (s.get("part_name") or "").split(","):
                p = p.strip()
                if p and p not in seen_parts:
                    seen_parts.add(p)
                    parts.append(p)
            for n in (s.get("oem_no") or "").split(","):
                n = n.strip()
                if n and n not in seen_nos:
                    seen_nos.add(n)
                    nos.append(n)
        merged.append({
            "vin": vins.pop() if vins else None,
            "part_name": ",".join(parts) if parts else None,
            "oem_no": ",".join(nos) if nos else None,
            "sender_name": group[0].get("sender_name"),
            "inquiry_content": group[0].get("inquiry_content"),
        })

    return merged


# ==================== 主入口 ====================


def rule_extract(messages: list[Message], focus_msg_ids: set[int] | None = None) -> list[dict]:
    """普通识别主入口：消息列表 → 标准场景列表。

    focus_msg_ids 增量分析时传入：
    - VIN 可以从全部消息提取（历史里的 VIN 用于关联新询价）
    - 配件名和号码只从 focus 消息（新询价）里提取，历史里的一律忽略
    - focus_msg_ids=None 表示全部消息都是新的（首次分析 / 旧调用兼容）

    返回空列表表示普通识别完全没提取到东西，调用方应走 AI 兜底。
    """
    focus = focus_msg_ids  # None → 全算 focus
    raw_scenes: list[dict] = []

    # 全窗口扫描 VIN（用于跨消息关联，不受 focus 限制）
    all_vins: list[str] = []
    for m in messages:
        v = _extract_vin_only_from_message(m)
        if v and v not in all_vins:
            all_vins.append(v)

    for i, msg in enumerate(messages):
        if msg.direction != Message.DIR_IN:
            continue

        # 如果指定了 focus 且这条不在 focus 里 → 跳过配件/号码提取
        in_focus = (focus is None) or (msg.id in focus)

        if msg.msg_type == Message.MSG_TEXT:
            if in_focus:
                scenes = _extract_from_text_message(msg)
                raw_scenes.extend(scenes)
            # 不在 focus 的历史消息 → 跳过（VIN 已在上面的全窗口扫描里覆盖）

        elif msg.msg_type == Message.MSG_IMAGE:
            if in_focus:
                # 图片场景的后续文本关联也只在 focus 里找
                img_scenes = _extract_from_image_message_focus(msg, messages, i, focus)
                raw_scenes.extend(img_scenes)

    if not raw_scenes:
        return []

    # 跨行合并
    merged = _cross_link_scenes(raw_scenes)

    # 用全窗口 VIN 补全没 VIN 的场景（历史 VIN 关联新询价配件）
    if all_vins:
        for s in merged:
            if not s.get("vin"):
                s["vin"] = all_vins[0]  # 取第一个 VIN（通常就是客户的车）

    # 保守过滤：rule_extract 只留"能算价"的场景。
    # 能算价 = 有 VIN 或 有 ≥6 位号码（两个至少一个）。
    # 纯配件名（无 VIN 无号码）→ 交给 AI（rule_extract 没法关联车型算价）。
    # 注意：有 VIN 时不管有没有配件名都留（客户可能只发 VIN，dispatch 走 pending）。
    def _has_pricing_hint(s: dict) -> bool:
        if s.get("vin"):
            return True
        raw_no = s.get("oem_no") or ""
        return bool(PART_NO_DIGITS_RE.search(raw_no) or PART_NO_PREFIX_RE.search(raw_no))

    result = [s for s in merged if _has_pricing_hint(s)]

    if result:
        log.info("普通识别提取成功 scenes=%d", len(result))
    return result


def _extract_from_image_message_focus(
    msg: Message, all_messages: list[Message], idx: int, focus: set[int] | None,
) -> list[dict]:
    """图片消息（focus 内）→ 场景列表。

    与 _extract_from_image_message 区别：后续关联的文本消息也必须在 focus 内。
    """
    img_url = (msg.payload or {}).get("img_url") if msg.payload else None
    vin = recognize_vin(img_url) if img_url else None

    part_names = []
    part_nos = []
    sender_name = msg.sender_name

    for j in range(idx + 1, min(idx + 4, len(all_messages))):
        next_msg = all_messages[j]
        if next_msg.direction != Message.DIR_IN:
            break
        # focus 限制：后续关联的消息也必须在 focus 里
        if focus is not None and next_msg.id not in focus:
            continue
        if next_msg.msg_type == Message.MSG_TEXT:
            sender_name = sender_name or next_msg.sender_name
            part_names.extend(_extract_part_names(next_msg.content or ""))
            part_nos.extend(_extract_part_numbers(next_msg.content or ""))

    if not vin and not part_names and not part_nos:
        return []

    return [{
        "vin": vin,
        "part_name": ",".join(part_names) if part_names else None,
        "oem_no": ",".join(part_nos) if part_nos else None,
        "sender_name": sender_name,
        "inquiry_content": f"[图片]{img_url and img_url[:60] or ''}",
    }]
