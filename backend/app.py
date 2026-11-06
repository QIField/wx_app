"""应用入口：创建 Flask 应用、挂扩展和路由。

职责：只做组装，不写业务逻辑。
"""
import os
import sys

# 宝塔等面板以脚本方式直接运行本文件时，backend 包不在搜索路径里，补上项目根目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from backend.config import (
    APP_ENV,
    DATABASE_URL,
    DEVICE_CHECK_INTERVAL_SECONDS,
    POLL_INTERVAL_SECONDS,
    PROFILE_INTERVAL_SECONDS,
    SEND_CONFIRM_INTERVAL,
)
from backend.db_migrate import upgrade_existing_schema
from backend.extensions import db, sock
from backend.models import Conversation, Message, SendTask  # noqa: F401 触发表注册


def create_app() -> Flask:
    """工厂函数：单测里每个用例可以建独立的应用实例。"""
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    sock.init_app(app)

    register_routes(app)
    register_frontend(app)
    register_error_handlers(app)
    register_access_log_hooks(app)
    return app


def register_frontend(app: Flask) -> None:
    """生产托管前端静态文件 frontend/dist：页面和接口同源，无需另配 nginx 静态站。

    dist 不存在（如单测环境）时跳过；根路径及未命中文件的路径统一回退 index.html。
    """
    from flask import send_from_directory

    dist = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist"
    )
    if not os.path.isdir(dist):
        return

    @app.get("/")
    @app.get("/<path:path>")
    def spa(path: str = ""):
        if path and os.path.isfile(os.path.join(dist, path)):
            return send_from_directory(dist, path)
        return send_from_directory(dist, "index.html")


def register_access_log_hooks(app: Flask) -> None:
    """入站接口日志钩子（规范见 docs/interface-log.md）：自动全量记录，业务零代码。"""
    from backend.services import access_log as svc

    @app.before_request
    def _access_begin():
        svc.start_timer()

    @app.after_request
    def _access_end(response):
        svc.record(response)
        return response

    @app.teardown_request
    def _access_teardown(exc):
        # 兜底：未处理异常时 after_request 不会执行，补记一条 500
        if exc is not None:
            svc.record_crash(exc)


def register_routes(app: Flask) -> None:
    from backend.api.accounts import bp as accounts_bp
    from backend.api.admin_devices import bp as admin_devices_bp
    from backend.api.audit_logs import bp as audit_logs_bp
    from backend.api.auth import bp as auth_bp
    from backend.api.contacts import bp as contacts_bp
    from backend.api.conversations import bp as conversations_bp
    from backend.api.devices import bp as devices_bp
    from backend.api.logs import bp as logs_bp
    from backend.api.media import bp as media_bp
    from backend.api.messages import bp as messages_bp
    from backend.api.orgs import bp as orgs_bp
    from backend.api.send_logs import bp as send_logs_bp
    from backend.api.uploads import bp as uploads_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(accounts_bp)
    app.register_blueprint(admin_devices_bp)
    app.register_blueprint(audit_logs_bp)
    app.register_blueprint(messages_bp)
    app.register_blueprint(conversations_bp)
    app.register_blueprint(contacts_bp)
    app.register_blueprint(devices_bp)
    app.register_blueprint(send_logs_bp)
    app.register_blueprint(media_bp)
    app.register_blueprint(uploads_bp)
    app.register_blueprint(logs_bp)
    app.register_blueprint(orgs_bp)

    import backend.ws.hub  # noqa: F401 注册 /ws WebSocket 路由

    @app.get("/api/health")
    def health():
        return jsonify(code=0, msg="success", data={"env": APP_ENV})


def register_error_handlers(app: Flask) -> None:
    """统一把 HTTP 异常（如 404/400）转成 JSON：{code, msg}。"""

    @app.errorhandler(HTTPException)
    def to_json(e):
        return jsonify(code=e.code, msg=e.description), e.code


def ensure_bootstrap_developer():
    """首次启动引导：user 表为空时创建初始开发者账号 dev / 123456。

    open_id 设备绑定、其他账号都由开发者登录后台后自行配置。
    """
    from werkzeug.security import generate_password_hash

    from backend.models.user import ROLE_DEVELOPER, User

    if User.query.first() is None:
        db.session.add(User(
            username="dev",
            name="开发者",
            role=ROLE_DEVELOPER,
            password_hash=generate_password_hash("123456"),
        ))
        db.session.commit()


def init_scheduler(app: Flask):
    """定时任务：收消息轮询 + 发送结果确认 + 会话资料解析 + 日志清理。
    只在直接运行 app.py 时启动。
    """
    from apscheduler.schedulers.background import BackgroundScheduler

    from backend.config import DEVICE_CHECK_INTERVAL_SECONDS
    from backend.services import middle_log
    from backend.services.audit import clean_expired_logs
    from backend.services.devices import refresh_all_device_online
    from backend.sync.confirm_worker import confirm_once
    from backend.sync.message_sync import sync_once
    from backend.sync import profile_jobs

    def scheduled(name, fn):
        """包装定时任务：给出站日志标记触发来源。"""
        def run():
            middle_log.set_job_source(name)
            fn(app)
        return run

    sched = BackgroundScheduler(daemon=True)
    sched.add_job(
        scheduled("message_sync", sync_once),
        "interval",
        seconds=POLL_INTERVAL_SECONDS,
        id="sync_message",
        max_instances=1,
    )
    sched.add_job(
        scheduled("confirm_worker", confirm_once),
        "interval",
        seconds=SEND_CONFIRM_INTERVAL,
        id="confirm_send",
        max_instances=1,
    )
    # 设备在线状态检测：check_online 回写 user_device.online（顶栏卡片在线点）。
    # 启动立即跑一次，之后每 10 分钟一轮；判定离线的设备各轮询任务自动跳过
    sched.add_job(
        scheduled("device_online", refresh_all_device_online),
        "interval",
        seconds=DEVICE_CHECK_INTERVAL_SECONDS,
        id="device_online",
        max_instances=1,
        next_run_time=datetime.now(),
    )
    # 资料同步统一走任务队列：定时轮只投递任务，由单 worker 与登录触发串行消费
    sched.add_job(
        scheduled("profile_sweep", profile_jobs.enqueue_sweep),
        "interval",
        seconds=PROFILE_INTERVAL_SECONDS,
        id="sync_profiles",
        max_instances=1,
    )
    # 日志清理：audit_log 180 天，access_log / middle_call_log 90 天（规范见 docs/interface-log.md）
    sched.add_job(
        lambda: _cleanup_logs(app),
        "cron",
        hour=3,
        minute=30,
        id="clean_logs",
        max_instances=1,
    )
    profile_jobs.ensure_worker(app)  # 资料同步唯一 worker，先于定时任务启动
    sched.start()
    return sched


def _cleanup_logs(app: Flask):
    with app.app_context():
        from backend.services.access_log import clean_expired as clean_access_logs
        from backend.services.middle_log import clean_expired as clean_middle_logs

        clean_expired_logs(days=180)  # audit_log 保留 180 天
        clean_access_logs(days=90)
        clean_middle_logs(days=90)


app = create_app()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()  # 开发期自动建表；生产环境建议换数据库迁移工具
        upgrade_existing_schema()
        from backend.models.org import Org
        Org.ensure_seed()  # 组织字典固定五条种子（幂等）
        ensure_bootstrap_developer()
    init_scheduler(app)
    # use_reloader=False：防止调试重载导致定时器跑两份
    # dev：仅本机 + 调试；prod：对外开放 + 关调试（WebSocket 依赖 werkzeug，不能用 waitress/gunicorn 常规 worker）
    if APP_ENV == "prod":
        app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
    else:
        app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)
