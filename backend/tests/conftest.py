"""测试公共夹具：内存数据库 + 干净的 app 实例 + 登录态客户端。"""
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


@pytest.fixture(autouse=True)
def no_profile_refresh(monkeypatch):
    """收消息单测不真跑资料补拉（避免同步等待中间方）；补拉行为在 test_profile_sync 专测。"""
    from backend.sync import profile_sync

    monkeypatch.setattr(profile_sync, "refresh_missing_profiles", lambda openid, ids: [])


@pytest.fixture(autouse=True)
def no_task_query_wait(monkeypatch):
    """单测不等中间方：任务查询重试间隔清零（重试次数语义不变）。"""
    from backend.sync import task_query

    monkeypatch.setattr(task_query, "QUERY_WAIT_SECONDS", 0)


@pytest.fixture()
def client(app):
    """已登录默认客服账号（绑定设备 dev01）的测试客户端。

    通过自定义 test_client_class 给所有请求自动带 Bearer 令牌；
    会话数据沿用既有约定的 openid=dev01。
    """
    from flask.testing import FlaskClient

    from backend.models.user import User
    from backend.services.auth import create_token

    class BearerClient(FlaskClient):
        """所有请求默认带上登录令牌；单测里传 headers= 可覆盖。"""

        auth_headers = {}

        def open(self, *args, **kwargs):
            headers = {**self.auth_headers, **(kwargs.pop("headers", None) or {})}
            return super().open(*args, headers=headers, **kwargs)

    make_user(open_ids=["dev01"])
    user = User.query.filter_by(username="cs01").one()
    token, _ = create_token(user)

    app.test_client_class = BearerClient
    c = app.test_client()
    c.auth_headers = {"Authorization": f"Bearer {token}"}
    return c


def make_user(**over):
    """测试造号工厂：默认客服角色 cs01/123456，可覆盖任意字段。

    open_ids=["o1", ...]：造号同时按顺序绑定微信设备（user_device）。
    """
    from backend.models.user import ROLE_AGENT, User
    from backend.models.user_device import UserDevice
    from werkzeug.security import generate_password_hash

    open_ids = over.pop("open_ids", None)
    fields = dict(
        username="cs01",
        name="客服01",
        role=ROLE_AGENT,
        password_hash=generate_password_hash("123456"),
    )
    fields.update(over)
    user = User(**fields)
    _db.session.add(user)
    _db.session.flush()  # 拿 id 再绑设备
    for openid in open_ids or []:
        _db.session.add(UserDevice(user_id=user.id, openid=openid))
    _db.session.commit()
    return user


def bind_device(user, openid, remark=None):
    """给已有账号追加一台绑定设备（多设备用例用）。"""
    from backend.models.user_device import UserDevice

    row = UserDevice(user_id=user.id, openid=openid, remark=remark)
    _db.session.add(row)
    _db.session.commit()
    return row


def login_headers(user):
    """指定账号的登录令牌头（多角色用例用）。"""
    from backend.services.auth import create_token

    token, _ = create_token(user)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def conversation(app):
    """一个测试会话：设备 dev01 → 客户 wxid_customer。"""
    conv = Conversation(openid="dev01", wxid="wxid_customer", chat_type=1, name="张师傅")
    _db.session.add(conv)
    _db.session.commit()
    return conv
