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
    from backend.api.conversations import bp as conversations_bp
    from backend.api.messages import bp as messages_bp

    app.register_blueprint(messages_bp)
    app.register_blueprint(conversations_bp)

    import backend.ws.hub  # noqa: F401 注册 /ws WebSocket 路由

    @app.get("/api/health")
    def health():
        return jsonify(code=0, msg="success", data={"env": APP_ENV})


def register_error_handlers(app: Flask) -> None:
    """统一把 HTTP 异常（如 404/400）转成 JSON：{code, msg}。"""

    @app.errorhandler(HTTPException)
    def to_json(e):
        return jsonify(code=e.code, msg=e.description), e.code


def init_scheduler(app: Flask):
    """定时任务：收消息轮询 + 发送结果确认 + 会话资料解析。只在直接运行 app.py 时启动。"""
    from apscheduler.schedulers.background import BackgroundScheduler

    from backend.sync.confirm_worker import confirm_once
    from backend.sync.message_sync import sync_once
    from backend.sync.profile_sync import sync_profiles

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
    sched.add_job(
        lambda: sync_profiles(app),
        "interval",
        seconds=PROFILE_INTERVAL_SECONDS,
        id="sync_profiles",
        max_instances=1,
    )
    sched.start()
    return sched


app = create_app()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()  # 开发期自动建表；生产环境建议换数据库迁移工具
    init_scheduler(app)
    # use_reloader=False：防止调试重载导致定时器跑两份
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)
