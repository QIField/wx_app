"""测试专用 app 工厂：强制内存库，绕开真实 DATABASE_URL。

与 backend/app.py 的 create_app 拆开，避免测试 import 时连上开发库。
"""
from flask import Flask
from sqlalchemy.pool import StaticPool

from backend.app import register_access_log_hooks, register_error_handlers, register_routes
from backend.extensions import db


def make_test_app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "poolclass": StaticPool,
        "connect_args": {"check_same_thread": False},
    }
    db.init_app(app)
    register_routes(app)
    register_error_handlers(app)
    register_access_log_hooks(app)  # 与生产一致的入站日志钩子
    return app
