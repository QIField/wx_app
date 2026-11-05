"""设备字典迁移单测：存量 user_device（手填 openid）→ device 字典行 → 回填 device_id。

模拟旧库结构（openid 列级 UNIQUE）验证三件事：
1. 每个 openid 建 device 行（name=remark、online 沿用、org 留空待补选）
2. device_id 回填；唯一约束解除后同一 openid 可插第二行（多对多）
3. 幂等：重复执行无副作用
"""
import pytest
from sqlalchemy import text

from backend.db_migrate import (
    _backfill_devices,
    _drop_user_device_openid_unique,
    _try_alter,
)
from backend.extensions import db


@pytest.fixture()
def legacy_db(app):
    """在内存库里复刻旧版 user_device（openid 唯一）并插入存量数据。

    device 表由 create_all 先行建立（与 app.py 启动顺序一致）。
    """
    with app.app_context():
        db.create_all()
        db.session.execute(text("DROP TABLE user_device"))
        db.session.execute(text(
            "CREATE TABLE user_device ("
            " id INTEGER PRIMARY KEY,"
            " user_id BIGINT NOT NULL,"
            " openid VARCHAR(64) UNIQUE,"
            " remark VARCHAR(64),"
            " online SMALLINT,"
            " created_at DATETIME NOT NULL,"
            " updated_at DATETIME NOT NULL)"
        ))
        db.session.execute(text(
            "INSERT INTO user_device (user_id, openid, remark, online, created_at, updated_at)"
            " VALUES (1, 'WX_OLD', '老设备', 1, '2026-01-01 00:00:00', '2026-01-01 00:00:00'),"
            "        (2, 'WX_UNNAMED', NULL, 0, '2026-01-01 00:00:00', '2026-01-01 00:00:00')"
        ))
        db.session.commit()
        yield app


def test_device_backfill_migration(legacy_db):
    """迁移链路：补列 → 建字典行 + 回填引用 + 解除唯一约束（幂等）。

    与 app.py 启动顺序一致：先 ADD COLUMN device_id，再重建表、回填。
    """
    from backend.models.device import Device
    from backend.models.user_device import UserDevice

    _try_alter("ALTER TABLE user_device ADD COLUMN device_id BIGINT")
    _drop_user_device_openid_unique()
    _backfill_devices()

    # 字典行：name 取 remark（无名留空待补选）、online 沿用旧值、org 留空
    old = Device.query.filter_by(openid="WX_OLD").one()
    assert old.name == "老设备" and old.online == 1 and old.org_id is None
    unnamed = Device.query.filter_by(openid="WX_UNNAMED").one()
    assert not unnamed.name and unnamed.online == 0

    # 引用回填：绑定行指向字典行
    rows = {r.openid: r for r in UserDevice.query.all()}
    assert rows["WX_OLD"].device_id == old.id
    assert rows["WX_UNNAMED"].device_id == unnamed.id
    assert rows["WX_OLD"].device.openid == "WX_OLD"

    # 唯一约束解除：同一 openid 可再插一行（多账号关联同一设备）
    db.session.execute(text(
        "INSERT INTO user_device (user_id, device_id, openid, created_at, updated_at)"
        f" VALUES (3, {old.id}, 'WX_OLD', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
    ))
    db.session.commit()
    assert UserDevice.query.filter_by(openid="WX_OLD").count() == 2

    # 幂等：重复执行不改数据
    _drop_user_device_openid_unique()
    _backfill_devices()
    assert Device.query.count() == 2
    assert UserDevice.query.filter_by(openid="WX_OLD").count() == 2
