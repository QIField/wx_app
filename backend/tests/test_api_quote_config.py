"""报价配置接口单测：合并读 / 全局行权限 / 校验 / 用户行独立 / 审计。"""
import pytest
from flask.testing import FlaskClient

from backend.extensions import db
from backend.models.audit_log import AuditLog
from backend.models.user import User
from backend.services.auth import create_token


@pytest.fixture()
def dev_client(app):
    """developer 角色客户端（黑名单/价格系数仅 admin/developer 可写）。"""
    from backend.tests.conftest import make_user

    make_user(username="dv01", name="开发者甲", role="developer")
    user = User.query.filter_by(username="dv01").one()
    token, _ = create_token(user)

    class DevClient(FlaskClient):
        def open(self, *args, **kwargs):
            headers = {"Authorization": f"Bearer {token}", **(kwargs.pop("headers", None) or {})}
            return super().open(*args, headers=headers, **kwargs)

    app.test_client_class = DevClient
    return app.test_client()


def test_get_default(client):
    """无任何配置时的合并默认值：黑名单空、系数三档默认、AI 开、仅预览。"""
    data = client.get("/api/quote/config").get_json()["data"]
    assert data == {
        "parts_blacklist": [],
        "price_map": {"vip_a": "0.75", "vip_b": "0.82", "normal": "0.90"},
        "ai_enabled": True,
        "ai_enabled_at": None,
        "ai_enabled_at_dt": None,
        "quote_mode": "preview",
    }


def test_put_global_by_developer(dev_client):
    """developer 写全局黑名单与价格系数 → 回读 + 审计。"""
    resp = dev_client.put("/api/quote/config", json={
        "parts_blacklist": ["保险杠总成", "发动机总成", "保险杠总成", "  "],
        "price_map": {"vip_a": 0.7, "vip_b": "0.85", "normal": 1.0},
    })
    body = resp.get_json()
    assert body["code"] == 0
    assert body["data"]["parts_blacklist"] == ["保险杠总成", "发动机总成"]
    assert body["data"]["price_map"] == {"vip_a": "0.70", "vip_b": "0.85", "normal": "1.00"}

    logs = AuditLog.query.filter_by(action="保存报价配置").all()
    assert len(logs) == 1
    assert "配件黑名单" in logs[0].detail and "价格系数" in logs[0].detail


def test_put_forbidden_for_agent(client):
    """agent 四个字段全部只读（执行开关已全局化，语义见 models/quote_config.py）。"""
    resp = client.put("/api/quote/config", json={"parts_blacklist": ["保险杠总成"]})
    assert resp.status_code == 403
    resp = client.put("/api/quote/config", json={"ai_enabled": False, "quote_mode": "auto"})
    assert resp.status_code == 403
    # GET 不受限
    assert client.get("/api/quote/config").get_json()["code"] == 0


def test_mode_global_shared(dev_client, client):
    """执行开关全局共享：developer 改，agent 读到同一值。"""
    dev_client.put("/api/quote/config", json={"quote_mode": "auto", "ai_enabled": False})
    for c in (dev_client, client):
        data = c.get("/api/quote/config").get_json()["data"]
        assert data["quote_mode"] == "auto"
        assert data["ai_enabled"] is False


def test_validation_errors(dev_client, client):
    """非法入参逐项 400：黑名单超限/超长、系数区间/缺键、模式枚举。"""
    url = "/api/quote/config"
    too_many = dev_client.put(url, json={"parts_blacklist": [f"配件{i}" for i in range(21)]})
    assert too_many.get_json()["code"] == 400

    too_long = dev_client.put(url, json={"parts_blacklist": ["x" * 21]})
    assert too_long.get_json()["code"] == 400

    out_range = dev_client.put(url, json={"price_map": {"vip_a": 1.5, "vip_b": 0.8, "normal": 0.9}})
    assert out_range.get_json()["code"] == 400

    missing_key = dev_client.put(url, json={"price_map": {"vip_a": 0.8, "vip_b": 0.8}})
    assert missing_key.get_json()["code"] == 400

    bad_mode = dev_client.put(url, json={"quote_mode": "magic"})
    assert bad_mode.get_json()["code"] == 400

    # 以上失败都不应产生任何写入
    db.session.commit()
    from backend.models.quote_config import QuoteConfig
    assert QuoteConfig.query.count() == 0


def test_empty_put_rejected(client):
    """空请求体 / 无关字段 → 400。"""
    assert client.put("/api/quote/config", json={}).get_json()["code"] == 400
    assert client.put("/api/quote/config", json={"foo": 1}).get_json()["code"] == 400


def test_ai_switch_off_then_on(dev_client):
    """AI 总开关关→开：审批 diff 记录两次变更。"""
    dev_client.put("/api/quote/config", json={"ai_enabled": False})
    dev_client.put("/api/quote/config", json={"ai_enabled": True})
    logs = AuditLog.query.filter_by(action="保存报价配置").all()
    details = "；".join(l.detail for l in logs)
    assert "AI开关开→关" in details and "AI开关关→开" in details
