"""测试公共夹具：内存数据库 + 干净的 app 实例。"""
import pytest
from sqlalchemy.pool import StaticPool

from backend.extensions import db as _db
from backend.models import Conversation
from backend.tests.app_factory import make_test_app


@pytest.fixture()
def app():
    """每个用例一个独立 app + 内存库（创建时就传测试配置，杜绝误连 dev 库）。"""
    app = make_test_app()
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture(autouse=True)
def real_middle_mode(monkeypatch):
    """默认走真实适配器路径（adapter 单测自己 mock requests）；demo 测试再显式开演示模式。"""
    from backend.adapter import client

    monkeypatch.setattr(client, "DEMO_MODE", False)


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
