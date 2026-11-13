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
# 有效期默认 12 小时：缩短令牌泄露后的可用窗口（够一个工作日，跨天需重新登录）
TOKEN_EXPIRE_HOURS = int(os.getenv("TOKEN_EXPIRE_HOURS", "12"))

# 接口限流（次/分钟，按桶分别控制；见 services/risk.py）
# 媒体桶不能低于「打开会话的合法突发」：一次打开最多并发 30 张图（可见气泡 +
# 预热请求，URL 去重），切几个会话就轻松破百——30 会把正常浏览当刷接口拦成 429
API_LIMIT_PER_MINUTE = int(os.getenv("API_LIMIT_PER_MINUTE", "120"))
MESSAGES_LIMIT_PER_MINUTE = int(os.getenv("MESSAGES_LIMIT_PER_MINUTE", "60"))
MEDIA_LIMIT_PER_MINUTE = int(os.getenv("MEDIA_LIMIT_PER_MINUTE", "120"))

# 登录失败锁定：同一 IP+账号在窗口内失败达到上限后，暂停登录
LOGIN_MAX_FAILS = int(os.getenv("LOGIN_MAX_FAILS", "5"))
LOGIN_WINDOW_SECONDS = int(os.getenv("LOGIN_WINDOW_SECONDS", "600"))

# 发送总开关：false 时前端发送接口直接拒绝（防止联调收消息阶段误发真消息）
SEND_ENABLED = os.getenv("SEND_ENABLED", "false").lower() in ("1", "true", "yes")

# 收消息轮询间隔（秒）
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "2"))
# 发送结果确认轮询间隔（秒）
SEND_CONFIRM_INTERVAL = int(os.getenv("SEND_CONFIRM_INTERVAL", "1"))
# 设备在线状态检测间隔（秒，默认 10 分钟）：调中间方 check_online 回写 user_device.online；
# 判定离线的设备跳过收消息/发送确认/资料同步等轮询，翻身在线后自动恢复
DEVICE_CHECK_INTERVAL_SECONDS = int(os.getenv("DEVICE_CHECK_INTERVAL_SECONDS", "600"))
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

# 上传文件公网基址：发图片/文件/视频要给中间方一个它服务器能下载到的 URL，
# 本机开发（127.0.0.1）中间方拉不到，部署到公网后在这里配 http(s)://域名
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
# 上传文件大小上限（字节，默认 50MB）
UPLOAD_MAX_BYTES = int(os.getenv("UPLOAD_MAX_BYTES", str(50 * 1024 * 1024)))
