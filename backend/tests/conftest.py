"""测试公共夹具：内存数据库 + 干净的 app 实例。"""
import pytest
from sqlalchemy.pool import StaticPool

from backend.app import create_app
from backend.extensions import db as _db
from backend.models import Conversation


@pytest.fixture()
def app():
    """每个用例一个独立 app + 内存库，用 StaticPool 保证同库连接。"""
    app = create_app()
    app.config.update(
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_ENGINE_OPTIONS={
            "poolclass": StaticPool,
            "connect_args": {"check_same_thread": False},
        },
        TESTING=True,
    )
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def conversation(app):
    """一个测试会话：设备 dev01 → 客户 wxid_customer。"""
    conv = Conversation(openid="dev01", wxid="wxid_customer", chat_type=1, name="张师傅")
    _db.session.add(conv)
    _db.session.commit()
    return conv
