"""询价分流：AI extract 结果解析 → 契约 B 状态机落表。

守门顺序（docs/auto-quote-plan.md 阶段 3 语义，本阶段落表、阶段 4 才消费 pending）：
  1. 配件命中黑名单（精确相等或包含）→ blocked
  2. quoted=true（跟进旧报价/二次议价）→ review（quoted=false 闸门挡重复报价）
  3. vin 与 part_name 全缺（识别不完整）→ review
  4. 其余 → pending（待报价）
"""
from backend.extensions import db
from backend.models.quote_inquiry import QuoteInquiry


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
    if _hit_blacklist(part, blacklist):
        return QuoteInquiry.ST_BLOCKED
    if _truthy(scene.get("quoted")):
        return QuoteInquiry.ST_REVIEW
    if not (scene.get("vin") or "").strip() and not part:
        return QuoteInquiry.ST_REVIEW
    return QuoteInquiry.ST_PENDING


def dispatch(conversation_id, scenarios, blacklist):
    """场景落表（同一 conversation 可多条），返回写入行 list。空场景不落。"""
    rows = []
    for s in scenarios:
        row = QuoteInquiry(
            conversation_id=conversation_id,
            sender_name=(s.get("sender_name") or None),
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
    if rows:
        db.session.commit()
    return rows
