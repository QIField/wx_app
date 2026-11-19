"""OCR VIN 识别（对接中间方快捷报价服务的两个 OCR 端点）。

降级策略：本地 OCR → 校验通过即返回 → 校验失败/异常 → 腾讯云 OCR。
只在中间方调用链里做这件事，不引入任何第三方 OCR 依赖。
"""
import logging
import re

from backend import qq_client
from backend.qq_client import QuoteApiError

log = logging.getLogger(__name__)

# VIN 合法字符集：17 位，排除 O/I/Q（工业标准）。
VIN_CHARS = r'A-HJ-NPR-Z0-9'
_VIN_VALID = re.compile(r'^[' + VIN_CHARS + r']{17}$', re.IGNORECASE)


def _normalize(raw) -> str | None:
    """中间方 OCR 返回 → 校验是否为合法 VIN。

    服务方 data 形态不定（str / dict），统一走 str 再校验。
    """
    if not raw:
        return None
    text = str(raw).strip().upper()
    # 先精确匹配；服务方可能把 VIN 嵌在句子里，再正则提取
    if _VIN_VALID.match(text):
        return text
    m = re.search(r'[' + VIN_CHARS + r']{17}', text)
    return m.group().upper() if m else None


def _try(image_url: str, prefer_tx: bool) -> str | None:
    """单次调用中间方 OCR 接口 → 校验 → 返回 VIN 或 None。"""
    try:
        raw = qq_client.ocr_vin(image_url, prefer_tx=prefer_tx)
    except QuoteApiError:
        log.warning("OCR 调用失败 prefer_tx=%s url=%s", prefer_tx, image_url[:80])
        return None
    except Exception:
        log.exception("OCR 未预期异常 prefer_tx=%s", prefer_tx)
        return None

    vin = _normalize(raw)
    if vin:
        log.info("OCR VIN=%s prefer_tx=%s url=%s", vin, prefer_tx, image_url[:80])
    else:
        log.info("OCR 返回非 17 位有效 VIN prefer_tx=%s raw=%r url=%s", prefer_tx, raw, image_url[:80])
    return vin


def recognize_vin(image_url: str) -> str | None:
    """入口：图片 URL → VIN 字符串（大写）或 None。

    降级链：本地 OCR → 腾讯云 OCR → None。
    """
    if not image_url:
        return None

    vin = _try(image_url, prefer_tx=False)
    if vin:
        return vin

    vin = _try(image_url, prefer_tx=True)
    if vin:
        return vin

    log.warning("OCR 两次均未获得有效 VIN url=%s", image_url[:80])
    return None
