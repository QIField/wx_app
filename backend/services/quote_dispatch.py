"""询价分流：AI extract 结果解析 → 契约 B 状态机落表。

守门顺序（docs/auto-quote-plan.md 阶段 3 语义，本阶段落表、阶段 4 才消费 pending）：
  0. 空场景过滤（vin/part/oem 全 None 直接丢弃，不入表）
  1. 配件命中黑名单（精确相等或包含）→ blocked
  2. quoted=true（跟进旧报价/二次议价）→ review
  3. is_replied=true（窗口里能看到客服发过报价）→ review
  4. vin / part_name / oem_no 全缺（识别不完整）→ review
  5. 其余 → pending（全新询价，待自动报价）

防重兜底（与上游增量分析协同）：
  - 上游 analyze_conversation 已按 last_analyzed_msg_id 做增量切分
  - 这里再加一层落表查重：同 conv_id + 同 (vin, part, oem) 已有 sent 记录 → 跳过
  - pending/review 不挡（允许多 pending 共存，客户反复问是合法业务）
"""
import logging
import re

from backend.extensions import db
from backend.models.quote_inquiry import QuoteInquiry
from backend.ws.hub import broadcast

log = logging.getLogger(__name__)


def _truthy(v):
    """AI 返回的 quoted/is_replied 形态不定：bool / "true" / 1 都按真处理。"""
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes", "y")
    return bool(v)


def parse_scenarios(data):
    """extract_parts_demand 返回 → 场景 list。兼容 list 或 {list:[...]} 两种形态。"""
    if isinstance(data, list):
        return [s for s in data if isinstance(s, dict)]
    if isinstance(data, dict):
        inner = data.get("list") or data.get("data") or []
        return [s for s in inner if isinstance(s, dict)] if isinstance(inner, list) else []
    return []


def _hit_blacklist(part_name, blacklist):
    """黑名单匹配：场景配件名与黑名单词双向包含即命中（"前保险杠" 命中 "保险杠"）。"""
    if not part_name:
        return False
    return any(w in part_name or part_name in w for w in blacklist if w)


def _status_of(scene, blacklist):
    part = (scene.get("part_name") or "").strip()
    oem = (scene.get("oem_no") or "").strip()
    vin = (scene.get("vin") or "").strip()
    if _hit_blacklist(part, blacklist):
        return QuoteInquiry.ST_BLOCKED
    if _truthy(scene.get("quoted")):
        return QuoteInquiry.ST_REVIEW
    if _truthy(scene.get("is_replied")):
        return QuoteInquiry.ST_REVIEW
    if not vin and not part and not oem:
        return QuoteInquiry.ST_REVIEW
    return QuoteInquiry.ST_PENDING


def notify_inquiry(rows, created=False):
    """询价落库/状态变更 → WS 广播（拓展栏自动报价 feed 的静默 refresh 信号）。

    rows: QuoteInquiry 行列表；created=True 表示新询价落库。空列表不广播。
    """
    if not rows:
        return
    broadcast("quote_inquiry_changed", {
        "created": created,
        "ids": [r.id for r in rows],
        "statuses": [r.status for r in rows],
        "conversation_id": rows[0].conversation_id,
    })


def _name_of(s):
    """AI 输出的发送者署名：空与「未知」都归 None，不落未知进卡片。"""
    name = (s.get("sender_name") or "").strip()
    return None if name in ("", "未知") else name


def _norm_key(text) -> str:
    """归一化：去空白 + 大写；None → 空串。"""
    if not text:
        return ""
    return re.sub(r"\s+", "", str(text)).upper()


def _dedup_key(conv_id, scene) -> str:
    """4 元组归一化 key（查重用）。"""
    vin = _norm_key(scene.get("vin"))
    part = _norm_key(scene.get("part_name"))
    # oem_no 多值按分隔符拆 → set 去重 → 排序后拼
    raw_oem = scene.get("oem_no") or ""
    oems = sorted(set(
        _norm_key(x) for x in re.split(r"[\n,，]", raw_oem) if _norm_key(x)
    ))
    return f"{conv_id}|{vin}|{part}|{'|'.join(oems)}"


def _fetch_sent_keys(conv_id) -> set[str]:
    """本会话已有 sent 记录的查重 key 集合（落表前查重）。"""
    rows = (
        QuoteInquiry.query.filter(
            QuoteInquiry.conversation_id == conv_id,
            QuoteInquiry.status == QuoteInquiry.ST_SENT,
            QuoteInquiry.deleted_at.is_(None),
        )
        .with_entities(QuoteInquiry.vin, QuoteInquiry.part_name, QuoteInquiry.oem_no)
        .all()
    )
    return {
        _dedup_key(conv_id, {"vin": vin, "part_name": part, "oem_no": oem})
        for vin, part, oem in rows
    }


def dispatch(conversation_id, scenarios, blacklist):
    """场景落表（同一 conversation 可多条），返回写入行 list。

    - 空场景（vin/part/oem 全 None）直接丢弃，不入表
    - 同 conv_id + 同 key 已有 sent 记录 → 跳过（防重兜底）
    - 同 key 的 pending/review 不挡（允许多 pending 共存，客户反复问是合法业务）
    """
    # 先查一次已报价记录的 key，本次分析全程复用
    sent_keys = _fetch_sent_keys(conversation_id)

    rows = []
    skipped_dup = 0
    skipped_empty = 0

    for s in scenarios:
        # 空场景过滤：vin/part/oem 全 None → 不入表
        if not any([s.get("vin"), s.get("part_name"), s.get("oem_no")]):
            skipped_empty += 1
            continue

        # 落表查重兜底：同 key 已有 sent → 跳过
        key = _dedup_key(conversation_id, s)
        if key in sent_keys:
            skipped_dup += 1
            log.info(
                "dispatch 跳过已报价 conv=%s key=%s", conversation_id, key,
            )
            continue

        row = QuoteInquiry(
            conversation_id=conversation_id,
            sender_name=_name_of(s),
            vin=(s.get("vin") or None),
            part_name=(s.get("part_name") or None),
            oem_no=(s.get("oem_no") or None),
            quoted=_truthy(s.get("quoted")),
            inquiry_time=s.get("inquiry_time"),
            inquiry_content=s.get("inquiry_content"),
            status=_status_of(s, blacklist),
        )
        db.session.add(row)
        rows.append(row)

    if skipped_empty or skipped_dup:
        log.info(
            "dispatch conv=%s 跳过 empty=%d dup=%d",
            conversation_id, skipped_empty, skipped_dup,
        )

    if rows:
        db.session.commit()
        notify_inquiry(rows, created=True)
    return rows
