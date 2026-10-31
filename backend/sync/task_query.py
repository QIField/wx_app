"""中间方任务查询共享工具：uuid 下发 → get_ 查询 → processing_result 解包。

收消息资料同步都走"uuid 下发任务 → get_xxx 查询 processing_result"套路，
本模块统一封装：按 uuid 收割任务记录、结果解包（ret==200 取 data）、
processing_result 的 dict/JSON 字符串归一，以及未知字段名的多候选取值。
供 group_profile / friend_profile 复用。
"""
import json
import time
import uuid as uuid_lib

from backend.adapter import client

QUERY_RETRY = 5         # 同步查询时的重试次数（好友列表等同步场景用；群任务两段式无需等待）
QUERY_WAIT_SECONDS = 2  # 每次重试间隔（实测约 4 秒内出结果）


def new_task_uuid():
    return str(uuid_lib.uuid4())


def query_record(module, get_action, task_uuid, openid="", retries=QUERY_RETRY):
    """查询下发结果（带间隔重试，供好友列表等同步场景用；群任务收割不用它等）。

    实测（2026-10-29）：data 是任务记录数组，每条含 uuid + processing_result；
    结果不是立即生成（约 4 秒内）。2026-10-30 补充实测：中间方走设备中转，
    结果延迟波动大（快则 3 秒，慢则 16 秒+），群资料立即补拉用更大重试预算。
    """
    for i in range(retries):
        row = query_record_once(module, get_action, task_uuid, openid)
        if row:
            return row
        if i < retries - 1:
            time.sleep(QUERY_WAIT_SECONDS)
    return None


def query_record_once(module, get_action, task_uuid, openid=""):
    """单次查询，不重试。返回本 uuid 的已完成任务记录或 None。

    2026-10-30 实测：任务记录在下发后立即出现，processing_result 要晚几秒
    才填充（群资料/好友资料同款竞态）；记录存在但结果还没生成视为未完成，
    返回 None 交由上层重试（query_record）或下轮收割（两段流水线）。
    """
    body = client.call(module, get_action, {}, uuid=task_uuid, openid=openid)
    rows = body.get("data") if isinstance(body, dict) else None
    if isinstance(rows, dict):
        rows = rows.get("list") or []
    if not isinstance(rows, list):
        return None
    for row in rows:
        if not isinstance(row, dict) or row.get("uuid") != task_uuid:
            continue
        # ret==200/500 等都是"已出结果"；没有 ret 说明中间方还没处理完
        if as_dict(row.get("processing_result")).get("ret") is None:
            continue
        return row
    return None


def unwrap_result(record):
    """任务记录 → 中间方业务数据 data（无记录或 ret != 200 返回 None）。

    2026-10-30 实测 processing_result 形如 {"ret":200, "msg":"操作成功", "data":...}。
    """
    if not record:
        return None
    result = as_dict(record.get("processing_result"))
    if result.get("ret") != 200:
        return None
    return result.get("data")


def as_dict(value):
    """processing_result 可能是 dict 或 JSON 字符串（2026-10-29 实测），统一转 dict。"""
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        try:
            obj = json.loads(value)
            return obj if isinstance(obj, dict) else {}
        except ValueError:
            return {}
    return {}


def pick(mapping, keys):
    """在未知字段名里按候选顺序取第一个非空值（联调校准点）。"""
    for key in keys:
        value = mapping.get(key)
        if value:
            return str(value)
    return None
