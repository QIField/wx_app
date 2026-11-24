"""询价分流：AI extract 结果解析 → 契约 B 状态机落表。

守门顺序（docs/auto-quote-plan.md 阶段 3 语义，本阶段落表、阶段 4 才消费 pending）：
  0. 空场景过滤（vin/part/oem 全 None 直接丢弃，不入表）
  1. 配件命中黑名单（精确相等或包含）→ blocked
  2. quoted=true（跟进旧报价/二次议价）→ review
  3. is_replied=true（窗口里能看到客服发过报价）→ review
  4. vin / part_name / oem_no 全缺（识别不完整）→ review
  5. 其余 → pending（全新询价，待自动报价）

关于"防重"：
  dispatch 层不做 sent 查重——客户合法的二次询价（同一个配件问两次）应该落表。
  防重复的职责完全由上游增量分析承担：
    - last_analyzed_msg_id 进度条：标记"已分析到哪条消息"
    - focus_msg_ids：rule_extract 只从新消息提配件，历史消息里的旧配件不会被重提
    - AI prompt 里的【历史】标签 + 系统提示：AI 自己不会重复提取历史
  同一次分析里 scene 重复 → rule_extract 的 _merge_scenes 已处理。
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


def _clean(val):
    """把脏值（Python None / 字符串 'None'/'null'/'undefined' / 纯空白）归一成 None。
    上游 rule_extract 返回的 JSON 有时把 null 序列化成字符串 'None'，这里统一清洗。"""
    if val is None:
        return None
    if isinstance(val, str):
        v = val.strip()
        if not v or v.lower() in ("none", "null", "undefined", "nan"):
            return None
        return v
    return val


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


def dispatch(conversation_id, scenarios, blacklist):
    """场景落表（同一 conversation 可多条），返回写入行 list。

    只做空场景过滤（vin/part/oem 全 None 的不入表），不做 sent 查重——
    上游增量分析已负责防重复，客户合法的二次询价应该落表。
    """
    rows = []
    skipped_empty = 0

    for s in scenarios:
        # 空场景过滤：vin/part/oem 全 None → 不入表
        if not any([s.get("vin"), s.get("part_name"), s.get("oem_no")]):
            skipped_empty += 1
            continue

        row = QuoteInquiry(
            conversation_id=conversation_id,
            message_id=s.get("_msg_id") or None,
            sender_name=_name_of(s),
            vin=_clean(s.get("vin")),
            part_name=_clean(s.get("part_name")),
            oem_no=_clean(s.get("oem_no")),
            quoted=_truthy(s.get("quoted")),
            inquiry_time=s.get("inquiry_time"),
            inquiry_content=s.get("inquiry_content"),
            status=_status_of(s, blacklist),
        )
        db.session.add(row)
        rows.append(row)

    if skipped_empty:
        log.info(
            "dispatch conv=%s 跳过 empty=%d",
            conversation_id, skipped_empty,
        )

    if rows:
        db.session.commit()
        notify_inquiry(rows, created=True)
    return rows
