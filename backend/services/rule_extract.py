"""普通识别模块（规则驱动，不调 AI）。

职责：消息窗口 → 正则/OCR 提取 → 标准场景列表（与 AI extract_parts 输出格式一致）。

流程：
  1. should_trigger(messages) → 是否需要识别（有 VIN/长数字/图片 才触发）
  2. rule_extract(messages) → 主入口，先各条单独提取，再跨行关联

输出格式（与 AI 返回对齐）：
  [{"vin": str|None, "part_name": str|None, "oem_no": str|None,
    "sender_name": str|None, "inquiry_content": str|None, ...}, ...]
"""
from __future__ import annotations

import logging
import re

from backend.models.message import Message
from backend.services.local_ocr import recognize_vin, VIN_CHARS
from backend.services.part_fallback import extract_part_names_fallback
from backend.services.part_suffixes import match_part_names, has_any_part_name
from backend.services.text_utils import normalize_spaced_digits

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
    """文本里是否出现 ≥6 位连续数字（含纯数字和前缀+数字两种）。

    先做空格归一化（"264 200 3201" → "2642003201"），否则空格会打断连续数字导致漏判。
    """
    normalized = normalize_spaced_digits(text or "")
    if PART_NO_DIGITS_RE.search(normalized):
        return True
    if PART_NO_PREFIX_RE.search(normalized):
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
      - 兜底：文本长得像询价（含品牌词 + 价格/配件询问词）
            ↑ 防止后缀表漏词导致 should_trigger 过不了，连 AI 的门都没摸到
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
        # 兜底：文本像询价 → 也触发（让 AI 有机会兜底）
        if _looks_like_inquiry(text):
            return True
    return False


# 兜底触发：文本长得像询价
# =============================================
# 设计思路：
#   后缀表只有约 67% 覆盖率，剩下 33% 的真实配件名可能漏掉。
#   漏了就会导致 should_trigger 返回 False，**连 AI 的门槛都没摸到**。
#   所以加一个启发式兜底：如果文本同时含"询价场景词"和"汽车相关词"，
#   哪怕后缀表一个配件名都没匹配到，也触发流程让 AI 兜底。
#
#   条件：必须同时命中两类词（AND 关系，避免太泛）。
#     1. 询价场景词 → 说明这是个询价
#     2. 汽车相关词 → 说明和车有关（不是"多少钱"买衣服）
_INQUIRY_SCENE_WORDS = (
    '多少钱', '报个价', '什么价', '询价', '价格', '报价', '问价', '出个价',
    '有货吗', '有货没', '有吗', '库存', '现货', '没货', '缺货',
    '换一下', '换一个', '换个', '更换', '维修', '保养',
    '来一个', '来一套', '来一组', '来一对',
    '好不好', '行不行', '怎么样', '贵吗', '便宜吗', '能便宜吗',
)

_CAR_RELATED_WORDS = (
    # 品牌
    '宝马', '奔驰', '奥迪', '大众', '丰田', '保时捷', '路虎', '沃尔沃',
    '本田', '日产', '福特', '别克', '雪佛兰', '凯迪拉克', '雷克萨斯',
    '英菲尼迪', '讴歌', '马自达', '斯巴鲁', '三菱', '现代', '起亚', '双龙',
    'MINI', 'Jeep', '特斯拉', '理想', '蔚来', '小鹏', '问界', '方程豹',
    # 车型/级别
    'X1', 'X3', 'X5', 'X6', '3系', '5系', '7系', 'C级', 'E级', 'S级',
    'A4', 'A6', 'A8', 'Q3', 'Q5', 'Q7', 'Q8', '卡宴', 'Macan', '911',
    'GLC', 'GLE', 'GLS', 'GLB', 'GLA',
    '轿车', 'SUV', '越野车', 'MPV', '皮卡', '跑车', '新能源车', '电车', '混动',
    # 其他汽车强相关
    '车架号', 'VIN', '尾号', '配', '改装', '升级', '降了',
)


def _looks_like_inquiry(text: str) -> bool:
    """启发式：文本长得像汽车配件询价。

    条件（AND）：含询价场景词 + 含汽车相关词。
    注意：汽车相关词匹配做大小写不敏感（VIN、X3、A4 等常大写出现）。
    """
    text_lower = (text or "").lower()
    has_scene = any(w in text_lower for w in _INQUIRY_SCENE_WORDS)
    if not has_scene:
        return False
    has_car = any(w.lower() in text_lower for w in _CAR_RELATED_WORDS)
    return has_car


# ==================== 单条提取 ====================


def _extract_vin(text: str) -> str | None:
    """文本 → 第一个合法 VIN（大写）。"""
    m = VIN_RE.search(text or "")
    return m.group().upper() if m else None


def _extract_part_numbers(text: str) -> list[str]:
    """文本 → 号码列表（去重、按原顺序）。

    处理顺序：括号里的号码 → 带前缀的号码 → 纯数字 ≥6 位。
    括号内容可能嵌 VIN，已被跳过。

    先做空格归一化（"264 200 3201" → "2642003201"），否则空格会打断连续数字导致漏判。
    """
    normalized = normalize_spaced_digits(text or "")
    found = []
    seen = set()

    def _add(token: str):
        token = token.strip().upper()
        if token and token not in seen and not VIN_RE.fullmatch(token):
            seen.add(token)
            found.append(token)

    # 1. 括号里的号码（如 (LR025632)、(1234567)）
    for m in _BRACKET_NO_RE.finditer(normalized):
        token = m.group(1).strip()
        if PART_NO_PREFIX_RE.fullmatch(token):
            _add(token)
        elif len(re.sub(r'\D', '', token)) >= 6:
            _add(re.sub(r'\D', '', token))  # 只保留数字部分

    # 2. 带前缀的号码（LR025632）
    for m in PART_NO_PREFIX_RE.finditer(normalized):
        _add(m.group(1) + m.group(2))

    # 3. 纯数字 ≥6 位
    for m in PART_NO_DIGITS_RE.finditer(normalized):
        _add(m.group(1))

    return found


def _extract_part_names(text: str) -> list[str]:
    """文本 → 配件名列表（后缀表 + 启发式 fallback，去重保序）。

    流程：
      1. 逐行走后缀表严格匹配（match_part_names）
      2. 再调 part_fallback.extract_part_names_fallback() 抠后缀表漏的缩写
      3. 合并去重（后缀表命中优先，fallback 补充）
    """
    names: list[str] = []
    seen: set[str] = set()

    for line in (text or "").splitlines():
        line_clean = _PREFIX_RE.sub('', line).strip()
        if not line_clean:
            continue
        for name in match_part_names(line_clean):
            if name not in seen:
                seen.add(name)
                names.append(name)

    # 启发式 fallback：后缀表漏的缩写（"前减震""分配阀"等）
    for name in extract_part_names_fallback(text):
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
    """只提取 VIN（用于跨消息关联，不受 focus 限制）。

    只扫客户 IN 方向消息 — 客服 OUT 消息里可能复述客户之前的 VIN，
    如果也扫进来会导致"客户 A 的 VIN 补到客户 B 的询价"这种张冠李戴。
    """
    if msg.direction != Message.DIR_IN:
        return None
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
    # 每条记录 {vin, sender_name, msg_id} — sender 匹配 + 时序约束才能安全补全
    all_vins: list[dict] = []
    for m in messages:
        v = _extract_vin_only_from_message(m)
        if not v:
            continue
        # 去重：同一个 VIN 只收最早那条（消息 id 最小的）
        if not any(x["vin"] == v for x in all_vins):
            all_vins.append({
                "vin": v,
                "sender_name": m.sender_name,
                "msg_id": m.id,
            })

    for i, msg in enumerate(messages):
        if msg.direction != Message.DIR_IN:
            continue

        # 如果指定了 focus 且这条不在 focus 里 → 跳过配件/号码提取
        in_focus = (focus is None) or (msg.id in focus)

        if msg.msg_type == Message.MSG_TEXT:
            if in_focus:
                scenes = _extract_from_text_message(msg)
                for s in scenes:
                    s["_msg_id"] = msg.id  # 内部字段：记录 scene 来自哪条消息
                raw_scenes.extend(scenes)
            # 不在 focus 的历史消息 → 跳过（VIN 已在上面的全窗口扫描里覆盖）

        elif msg.msg_type == Message.MSG_IMAGE:
            if in_focus:
                # 图片场景的后续文本关联也只在 focus 里找
                img_scenes = _extract_from_image_message_focus(msg, messages, i, focus)
                for s in img_scenes:
                    s["_msg_id"] = msg.id
                raw_scenes.extend(img_scenes)

    if not raw_scenes:
        return []

    # 跨行合并
    merged = _cross_link_scenes(raw_scenes)

    # 用全窗口 VIN 补全没 VIN 的场景 —— 四个安全条件缺一不可：
    #   1. 方向过滤：VIN 只来自客户 IN 消息（扫的时候已经保证）
    #   2. sender 匹配：客户 A 的 VIN 只补客户 A 的询价
    #   3. 时序约束：VIN 消息 id < 询价消息 id（先发 VIN 后发询价）
    #   4. ★ 关键：scene 自己没给 OE 号 —— OE 号是自包含询价，有 OE 说明客户要独立查价，
    #      补 VIN 反而把两条独立询价绑在一起。只有"纯配件名 + 无 OE"才需要 VIN 去译码。
    if all_vins:
        for s in merged:
            if s.get("vin"):
                continue
            # 条件 4：有 OE 号（≥6 位连续数字）→ 不补，OE 自己就能查 product_list
            raw_oem = s.get("oem_no") or ""
            if raw_oem and (PART_NO_DIGITS_RE.search(raw_oem) or PART_NO_PREFIX_RE.search(raw_oem)):
                continue
            scene_sender = s.get("sender_name") or ""
            scene_msg_id = s.get("_msg_id") or 0
            for vin_info in all_vins:
                if vin_info["sender_name"] == scene_sender and vin_info["msg_id"] < scene_msg_id:
                    s["vin"] = vin_info["vin"]
                    break

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

