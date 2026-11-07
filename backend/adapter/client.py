"""中间方 HTTP 客户端：所有对中间方的请求都从这里出。

统一规则（见 docs/api.md 附录）：
- 全部 POST，application/x-www-form-urlencoded
- 公共参数：openid（设备标识，多设备后由调用方按账号绑定传入）、uuid（本次调用唯一标识）
- 返回统一 {"code": 0, "msg": "success"}，查询接口多一个 data 字段
"""
import time
import uuid as uuid_lib

import requests

from backend.config import MIDDLE_BASE_URL
from backend.services import middle_log

TIMEOUT = 10  # 秒
DOWNLOAD_TIMEOUT = 30  # 媒体下载可能较大，超时放宽

# 演示模式下媒体下载接口的占位返回：(字节, Content-Type)
# 图片/表情给一张 1x1 PNG，其余给空字节，保证无中间方时前端能调通
_DEMO_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d4944415478da63fcffff3f030005fe02fea72d5e2b0000000049454e44ae426082"
)
_DEMO_MEDIA = {
    "get_download_image": (_DEMO_PNG, "image/png"),
    "get_download_emoji": (_DEMO_PNG, "image/gif"),
    "get_download_voice": (b"", "audio/amr"),
    "get_download_video": (b"", "video/mp4"),
    "get_download_file": (b"", "application/octet-stream"),
}

# 演示模式：没配中间方地址时，所有请求直接返回模拟成功。
# 配置了 MIDDLE_BASE_URL 后自动走真实接口，代码无需改动。
DEMO_MODE = not MIDDLE_BASE_URL


class MiddleApiError(Exception):
    """中间方返回 code != 0，或网络请求本身失败。"""

    def __init__(self, msg, code=None):
        super().__init__(msg)
        self.code = code
        self.msg = msg


def call(module, action, params=None, uuid=None, openid=""):
    """调中间方接口：拼公共参数、发 POST、统一解析返回。

    - module：接口模块段（send_api / messag_api / login_api / group_api / contacts_api）
    - action：模块下方法名，形如 post_text_message / get_post_text_message
    - 真实 URL 三段式：{BASE}/wx_app/{module}/{action}
    - openid：设备标识，多设备同步按账号绑定传入；演示模式下忽略
    - uuid 由调用方传入（发送闭环里下发和确认用同一个）；不传则自动生成
    每次调用（含四类失败场景）自动记 middle_call_log，见 services/middle_log.py。
    """
    form = {
        "openid": openid or "",
        "uuid": uuid or str(uuid_lib.uuid4()),
    }
    if params:
        form.update(params)

    if DEMO_MODE:
        # 查询接口带 data（发送确认轮询会用到），命令接口只回 code/msg。
        # demo 的查询结构对齐真实返回：任务记录列表 + processing_result。
        if action.startswith("get_"):
            body = {
                "code": 0, "msg": "success (demo)",
                "data": [{"uuid": form["uuid"], "processing_result": '{"ret": 200, "msg": "操作成功"}'}],
            }
        else:
            body = {"code": 0, "msg": "success (demo)"}
        middle_log.log_call(module, action, uuid=form["uuid"], openid=form["openid"],
                            params=params, resp_code=body.get("code"),
                            response_body=str(body), success=1)
        return body

    started = time.perf_counter()
    http_status = None
    try:
        resp = requests.post(_url(module, action), data=form, timeout=TIMEOUT)
        http_status = resp.status_code
        resp.raise_for_status()
    except requests.RequestException as exc:
        _log(module, action, form, params, started, http_status=http_status,
             success=0, error_msg=f"请求中间方失败：{exc}")
        raise MiddleApiError(f"请求中间方失败：{exc}") from exc

    raw = resp.text
    try:
        body = resp.json()
    except ValueError as exc:
        _log(module, action, form, params, started, http_status=http_status,
             success=0, response_body=raw, error_msg=f"中间方返回不是合法 JSON：{exc}")
        raise MiddleApiError(f"中间方返回不是合法 JSON：{exc}") from exc

    resp_code = body.get("code")
    result = middle_log.first_result(body)
    ret = result.get("ret") if isinstance(result, dict) else None
    success = middle_log.decide_success(resp_code, ret)
    _log(module, action, form, params, started, http_status=http_status, resp_code=resp_code,
         ret=ret, response_body=raw, success=success,
         error_msg="" if success else _fail_reason(body, result))

    if resp_code != 0:
        raise MiddleApiError(body.get("msg", "unknown error"), resp_code)
    return body


def _url(module, action):
    return f"{MIDDLE_BASE_URL.rstrip('/')}/wx_app/{module.strip('/')}/{action.strip('/')}"


def _fail_reason(body, result):
    """出站失败原因：processing_result 异常优先（如设备离线），其次业务 msg。"""
    if isinstance(result, dict) and result.get("ret") not in (None, 200):
        ret, msg = result.get("ret"), result.get("msg")
        return f"ret={ret} {msg}" if msg else f"ret={ret}"
    return str(body.get("msg") or "unknown error")


def _log(module, action, form, params, started, **kwargs):
    """出站日志统一入口：公共字段自动补齐。"""
    kwargs.setdefault("uuid", form.get("uuid", ""))
    kwargs.setdefault("openid", form.get("openid", ""))
    kwargs.setdefault("params", params)
    kwargs.setdefault("duration_ms", int((time.perf_counter() - started) * 1000))
    middle_log.log_call(module, action, **kwargs)


def call_download(module, action, params=None, openid=""):
    """调中间方媒体下载接口（get_download_xxx）：返回 (文件字节, Content-Type)。"""
    data, content_type, _ = call_download_with_url(module, action, params, openid)
    return data, content_type


def call_download_with_url(module, action, params=None, openid=""):
    """同 call_download，额外返回 CDN 预签名地址：三档 URL 相同时可只 GET 一次省流量。

    实测两步流程（见 docs/api.md 附录「联调实测记录」，与 V2 文档描述不同）：
    1. POST 返回 JSON（不是文件本身），文件地址在 data.data.fileUrl，表情接口是 data.data.url
    2. 拿到 CDN 预签名地址后再普通 GET 拉回文件字节
    返回的 Content-Type 不可信（实测恒为 application/octet-stream），调用方应按魔数判断真实类型。
    演示模式返回占位字节，便于无中间方时调通前端。
    日志：失败全落库；成功记 JSON 步骤响应 + 文件状态码/类型/字节数（媒体二进制不落库）。
    """
    if DEMO_MODE:
        middle_log.log_call(module, action, openid=openid or "", params=params,
                            resp_code=0, response_body="(demo) 占位媒体", success=1)
        return _DEMO_MEDIA.get(action, (b"", "application/octet-stream")) + ("",)

    started = time.perf_counter()
    form = {"openid": openid or ""}
    if params:
        form.update(params)

    http_status = None
    try:
        resp = requests.post(_url(module, action), data=form, timeout=DOWNLOAD_TIMEOUT)
        http_status = resp.status_code
        resp.raise_for_status()
    except requests.RequestException as exc:
        _log(module, action, form, params, started, http_status=http_status,
             success=0, error_msg=f"请求中间方下载接口失败：{exc}")
        raise MiddleApiError(f"请求中间方下载接口失败：{exc}") from exc

    raw = resp.text
    try:
        body = resp.json()
    except ValueError as exc:
        _log(module, action, form, params, started, http_status=http_status,
             success=0, response_body=raw, error_msg=f"下载接口返回不是合法 JSON：{exc}")
        raise MiddleApiError(f"下载接口返回不是合法 JSON：{exc}") from exc

    def fail(error_msg, **kw):
        """下载链路失败统一记日志后再抛错。"""
        _log(module, action, form, params, started, response_body=raw,
             success=0, error_msg=error_msg, **kw)

    resp_code = body.get("code")
    if resp_code != 0:
        fail(str(body.get("msg", "unknown error")), http_status=http_status, resp_code=resp_code)
        raise MiddleApiError(body.get("msg", "unknown error"), resp_code)
    inner = body.get("data") or {}
    ret = inner.get("ret") if isinstance(inner, dict) else None
    if ret not in (None, 200):
        fail(str(inner.get("msg") or f"processing_result.ret={ret}"),
             http_status=http_status, resp_code=resp_code, ret=ret)
        raise MiddleApiError(inner.get("msg") or "下载失败", ret)
    inner_data = inner.get("data") if isinstance(inner, dict) else None
    file_url = ""
    if isinstance(inner_data, dict):
        file_url = inner_data.get("fileUrl") or inner_data.get("url") or ""
    if not file_url:
        fail("下载接口未返回文件地址", http_status=http_status, resp_code=resp_code)
        raise MiddleApiError("下载接口未返回文件地址")

    try:
        file_resp = requests.get(file_url, timeout=DOWNLOAD_TIMEOUT)
        file_resp.raise_for_status()
    except requests.RequestException as exc:
        fail(f"拉取媒体文件失败：{exc}", http_status=http_status, resp_code=resp_code)
        raise MiddleApiError(f"拉取媒体文件失败：{exc}") from exc
    content_type = (file_resp.headers.get("Content-Type") or "application/octet-stream").split(";")[0].strip()
    file_meta = f"\n[file] status={file_resp.status_code} type={content_type} bytes={len(file_resp.content)}"
    _log(module, action, form, params, started, http_status=http_status, resp_code=resp_code,
         response_body=raw + file_meta, success=1)
    return file_resp.content, content_type, file_url
