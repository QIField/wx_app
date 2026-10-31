"""中间方 HTTP 客户端：所有对中间方的请求都从这里出。

统一规则（见 docs/api.md 附录）：
- 全部 POST，application/x-www-form-urlencoded
- 公共参数：openid（设备标识，多设备后由调用方按账号绑定传入）、uuid（本次调用唯一标识）
- 返回统一 {"code": 0, "msg": "success"}，查询接口多一个 data 字段
"""
import uuid as uuid_lib

import requests

from backend.config import MIDDLE_BASE_URL

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
    """
    url = f"{MIDDLE_BASE_URL.rstrip('/')}/wx_app/{module.strip('/')}/{action.strip('/')}"
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
            data = [{
                "uuid": form["uuid"],
                "processing_result": '{"ret": 200, "msg": "操作成功"}',
            }]
            return {"code": 0, "msg": "success (demo)", "data": data}
        return {"code": 0, "msg": "success (demo)"}

    try:
        resp = requests.post(url, data=form, timeout=TIMEOUT)
        resp.raise_for_status()
        body = resp.json()
    except requests.RequestException as exc:
        raise MiddleApiError(f"请求中间方失败：{exc}") from exc
    except ValueError as exc:
        raise MiddleApiError(f"中间方返回不是合法 JSON：{exc}") from exc

    if body.get("code") != 0:
        raise MiddleApiError(body.get("msg", "unknown error"), body.get("code"))
    return body


def call_download(module, action, params=None, openid=""):
    """调中间方媒体下载接口（get_download_xxx）：返回 (文件字节, Content-Type)。

    实测两步流程（见 docs/api.md 附录「联调实测记录」，与 V2 文档描述不同）：
    1. POST 返回 JSON（不是文件本身），文件地址在 data.data.fileUrl，表情接口是 data.data.url
    2. 拿到 CDN 预签名地址后再普通 GET 拉回文件字节
    返回的 Content-Type 不可信（实测恒为 application/octet-stream），调用方应按魔数判断真实类型。
    演示模式返回占位字节，便于无中间方时调通前端。
    """
    if DEMO_MODE:
        return _DEMO_MEDIA.get(action, (b"", "application/octet-stream"))

    url = f"{MIDDLE_BASE_URL.rstrip('/')}/wx_app/{module.strip('/')}/{action.strip('/')}"
    form = {"openid": openid or ""}
    if params:
        form.update(params)
    try:
        resp = requests.post(url, data=form, timeout=DOWNLOAD_TIMEOUT)
        resp.raise_for_status()
        body = resp.json()
    except requests.RequestException as exc:
        raise MiddleApiError(f"请求中间方下载接口失败：{exc}") from exc
    except ValueError as exc:
        raise MiddleApiError(f"下载接口返回不是合法 JSON：{exc}") from exc

    if body.get("code") != 0:
        raise MiddleApiError(body.get("msg", "unknown error"), body.get("code"))
    inner = body.get("data") or {}
    if isinstance(inner, dict) and inner.get("ret") not in (None, 200):
        raise MiddleApiError(inner.get("msg") or "下载失败", inner.get("ret"))
    inner_data = inner.get("data") if isinstance(inner, dict) else None
    file_url = ""
    if isinstance(inner_data, dict):
        file_url = inner_data.get("fileUrl") or inner_data.get("url") or ""
    if not file_url:
        raise MiddleApiError("下载接口未返回文件地址")

    try:
        file_resp = requests.get(file_url, timeout=DOWNLOAD_TIMEOUT)
        file_resp.raise_for_status()
    except requests.RequestException as exc:
        raise MiddleApiError(f"拉取媒体文件失败：{exc}") from exc
    content_type = (file_resp.headers.get("Content-Type") or "application/octet-stream").split(";")[0].strip()
    return file_resp.content, content_type
