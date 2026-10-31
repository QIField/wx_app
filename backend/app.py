"""应用入口：创建 Flask 应用、挂扩展和路由。

职责：只做组装，不写业务逻辑。
"""
from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from backend.config import (
    APP_ENV,
    DATABASE_URL,
    POLL_INTERVAL_SECONDS,
    PROFILE_INTERVAL_SECONDS,
    SEND_CONFIRM_INTERVAL,
)
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
    register_error_handlers(app)
    return app


def register_routes(app: Flask) -> None:
    from backend.api.accounts import bp as accounts_bp
    from backend.api.audit_logs import bp as audit_logs_bp
    from backend.api.auth import bp as auth_bp
    from backend.api.contacts import bp as contacts_bp
    from backend.api.conversations import bp as conversations_bp
    from backend.api.media import bp as media_bp
    from backend.api.messages import bp as messages_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(accounts_bp)
    app.register_blueprint(audit_logs_bp)
    app.register_blueprint(messages_bp)
    app.register_blueprint(conversations_bp)
    app.register_blueprint(contacts_bp)
    app.register_blueprint(media_bp)

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

    from backend.services.audit import clean_expired_logs
    from backend.sync.confirm_worker import confirm_once
    from backend.sync.message_sync import sync_once
    from backend.sync import profile_jobs

    sched = BackgroundScheduler(daemon=True)
    sched.add_job(
        lambda: sync_once(app),
        "interval",
        seconds=POLL_INTERVAL_SECONDS,
        id="sync_message",
        max_instances=1,
    )
    sched.add_job(
        lambda: confirm_once(app),
        "interval",
        seconds=SEND_CONFIRM_INTERVAL,
        id="confirm_send",
        max_instances=1,
    )
    # 资料同步统一走任务队列：定时轮只投递任务，由单 worker 与登录触发串行消费
    sched.add_job(
        lambda: profile_jobs.enqueue_sweep(app),
        "interval",
        seconds=PROFILE_INTERVAL_SECONDS,
        id="sync_profiles",
        max_instances=1,
    )
    # 审计日志保留 180 天，每天凌晨 3:30 清理一次（规范见 docs/audit-log.md）
    sched.add_job(
        lambda: _cleanup_logs(app),
        "cron",
        hour=3,
        minute=30,
        id="clean_audit_logs",
        max_instances=1,
    )
    profile_jobs.ensure_worker(app)  # 资料同步唯一 worker，先于定时任务启动
    sched.start()
    return sched


def _cleanup_logs(app: Flask):
    with app.app_context():
        clean_expired_logs(days=180)


app = create_app()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()  # 开发期自动建表；生产环境建议换数据库迁移工具
        ensure_bootstrap_developer()
    init_scheduler(app)
    # use_reloader=False：防止调试重载导致定时器跑两份
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)
