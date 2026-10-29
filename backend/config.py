"""配置：读取 .env，按 APP_ENV 自动选择数据库。

规则：
- APP_ENV 不填默认 dev，防止误连生产库
- 改 .env 后需重启服务才生效
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# 运行环境：dev=测试库  prod=生产库
APP_ENV = os.getenv("APP_ENV", "dev").lower()


def _pick_database_url() -> str:
    """按环境选库；没配 .env 时用本地 sqlite 兜底（仅开发调试用）。"""
    key = "PROD_DATABASE_URL" if APP_ENV == "prod" else "DEV_DATABASE_URL"
    return os.getenv(key) or "sqlite:///" + str(BASE_DIR / "wx_app_dev.db")


DATABASE_URL = _pick_database_url()

# 中间方
MIDDLE_BASE_URL = os.getenv("MIDDLE_BASE_URL", "")
MIDDLE_OPENID = os.getenv("MIDDLE_OPENID", "")

# 收消息轮询间隔（秒）
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "2"))

# 发送结果确认轮询间隔（秒）
SEND_CONFIRM_INTERVAL = int(os.getenv("SEND_CONFIRM_INTERVAL", "1"))
