"""中间方 HTTP 客户端：所有对中间方的请求都从这里出。

统一规则（见 docs/api.md 附录）：
- 全部 POST，application/x-www-form-urlencoded
- 公共参数：openid（设备标识）、uuid（本次调用唯一标识）
- 返回统一 {"code": 0, "msg": "success"}，查询接口多一个 data 字段
"""
import uuid as uuid_lib

import requests

from backend.config import MIDDLE_BASE_URL, MIDDLE_OPENID

TIMEOUT = 10  # 秒

# 演示模式：没配中间方地址时，所有请求直接返回模拟成功。
# 配置了 MIDDLE_BASE_URL 后自动走真实接口，代码无需改动。
DEMO_MODE = not MIDDLE_BASE_URL


class MiddleApiError(Exception):
    """中间方返回 code != 0，或网络请求本身失败。"""

    def __init__(self, msg, code=None):
        super().__init__(msg)
        self.code = code
        self.msg = msg


def call(module, action, params=None, uuid=None):
    """调中间方接口：拼公共参数、发 POST、统一解析返回。

    - module：接口模块段（send_api / messag_api / login_api / group_api / contacts_api）
    - action：模块下方法名，形如 post_text_message / get_post_text_message
    - 真实 URL 三段式：{BASE}/wx_app/{module}/{action}
    - uuid 由调用方传入（发送闭环里下发和确认用同一个）；不传则自动生成
    """
    url = f"{MIDDLE_BASE_URL.rstrip('/')}/wx_app/{module.strip('/')}/{action.strip('/')}"
    form = {
        "openid": MIDDLE_OPENID,
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
