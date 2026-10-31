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

# 登录令牌：签名密钥与有效期（小时）；SECRET_KEY 不配则开发期用固定值，生产必须在 .env 配置
SECRET_KEY = os.getenv("SECRET_KEY", "wxcs-dev-secret-key-change-me")
TOKEN_EXPIRE_HOURS = int(os.getenv("TOKEN_EXPIRE_HOURS", "72"))

# 发送总开关：false 时前端发送接口直接拒绝（防止联调收消息阶段误发真消息）
SEND_ENABLED = os.getenv("SEND_ENABLED", "false").lower() in ("1", "true", "yes")

# 收消息轮询间隔（秒）
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "2"))
# 发送结果确认轮询间隔（秒）
SEND_CONFIRM_INTERVAL = int(os.getenv("SEND_CONFIRM_INTERVAL", "1"))
# 会话资料解析间隔（秒）：群名+好友昵称头像，30 分钟一轮兜底
# （新消息触发的立即补拉见 profile_sync.refresh_missing_profiles）
PROFILE_INTERVAL_SECONDS = int(os.getenv("PROFILE_INTERVAL_SECONDS", "1800"))

# 登录触发资料全量同步：true=账号登录且已绑定设备时，对该设备做一次完整资料同步
PROFILE_LOGIN_SYNC_ENABLED = os.getenv("PROFILE_LOGIN_SYNC_ENABLED", "true").lower() in (
    "1", "true", "yes",
)
# 同一设备登录触发的冷却期（秒）：默认 6 小时，避免反复登录重复全量拉取
PROFILE_LOGIN_COOLDOWN_SECONDS = int(os.getenv("PROFILE_LOGIN_COOLDOWN_SECONDS", "21600"))

# 媒体缓存目录：中间方下载接口拉回的图片/文件/视频/语音/表情落盘缓存
MEDIA_DIR = Path(os.getenv("MEDIA_DIR") or (BASE_DIR / "backend" / "media"))
