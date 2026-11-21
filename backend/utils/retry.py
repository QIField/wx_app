"""通用短退避重试工具：只帮调用方挡住瞬时 5xx / 网络抖动，不掩盖业务错误。

与 media_fetch._call_download_retried 保持同一风格：
  - 首呼 + N 次重试（默认 2 次），退避间隔固定
  - 重试条件由调用方传 retryable_check(exc) → bool 判定
  - 每次尝试失败前调 log.warning 记流水，便于事后排查
"""
import logging
import time

log = logging.getLogger(__name__)

# 首呼 + 2 次重试的退避秒数（= 1.5s、3.0s 后各再试一次）
DEFAULT_DELAYS = (1.5, 3.0)


def call_with_retry(fn, retryable_check, delays=None, *args, **kwargs):
    """带短退避重试的通用调用。

    fn: 要调用的函数（任何签名都行，通过 *args/**kwargs 透传）
    retryable_check(exc) → bool: 判断这个异常是否值得重试
    delays: 退避秒数元组，默认 (1.5, 3.0)；首呼不算 delay
    返回 fn 的正常返回值，或在最后一次失败时 raise 原异常。
    """
    if delays is None:
        delays = DEFAULT_DELAYS
    total = len(delays) + 1  # 首呼 + 重试次数
    last_exc = None
    for attempt, delay in enumerate((0,) + delays):
        if delay:
            time.sleep(delay)
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 先抓上来让 retryable_check 判
            last_exc = exc
            if not retryable_check(exc) or attempt >= len(delays):
                raise
            log.warning(
                "重试 %d/%d fn=%s err=%s",
                attempt + 1, total, getattr(fn, "__name__", str(fn)), exc,
            )
    # 理论上到不了这里（最后一次 raise 已跳出），保险起见再抛一次
    raise last_exc  # noqa: ER013
