"""存量库轻量迁移：create_all 只建新表，不会给存量表补列，这里人工补。

只在直接运行 app.py 的启动引导里调用；所有操作幂等，重复执行无副作用。
新加列：在 upgrade_existing_schema 里追加一条 _try_alter 即可。
"""
from backend.extensions import db


def upgrade_existing_schema():
    """按时间顺序给存量表补列（每条 _try_alter 自带幂等）。"""
    _try_alter("ALTER TABLE user ADD COLUMN org_id BIGINT")
    _try_alter("ALTER TABLE message ADD COLUMN operator_id BIGINT")
    _try_alter("ALTER TABLE message ADD COLUMN operator_name VARCHAR(64)")
    # 2026-11-02 姓名+组织快照规范：记录"人"的表统一补组织快照列
    _try_alter("ALTER TABLE message ADD COLUMN org_name VARCHAR(64)")
    _try_alter("ALTER TABLE audit_log ADD COLUMN org_name VARCHAR(64)")
    _try_alter("ALTER TABLE middle_call_log ADD COLUMN user_name VARCHAR(64)")
    _try_alter("ALTER TABLE middle_call_log ADD COLUMN org_name VARCHAR(64)")
    # 2026-11-03 会话右键菜单：消息免打扰标记
    _try_alter("ALTER TABLE conversation ADD COLUMN muted SMALLINT NOT NULL DEFAULT 0")
    _backfill_user_devices()
    _try_drop_user_openid()
    # 2026-11-05 设备字典重构：user_device 由手填 openid 改为引用 device.id
    _try_alter("ALTER TABLE user_device ADD COLUMN device_id BIGINT")
    # 软删除列要在 user_device 重建（SQLite 分支）之前补齐：
    # 重建会按 ORM 当前列清单拷贝数据，缺列会导致 INSERT ... SELECT 失败。
    _try_alter("ALTER TABLE device ADD COLUMN deleted_at DATETIME NULL")
    _try_alter("ALTER TABLE user_device ADD COLUMN deleted_at DATETIME NULL")
    _try_alter("ALTER TABLE contact ADD COLUMN deleted_at DATETIME NULL")
    _try_alter("ALTER TABLE contact_profile ADD COLUMN deleted_at DATETIME NULL")
    _try_alter("ALTER TABLE group_member ADD COLUMN deleted_at DATETIME NULL")
    _drop_user_device_openid_unique()
    _backfill_devices()
    _try_alter("ALTER TABLE device ADD INDEX idx_device_deleted (deleted_at)")


def _try_alter(sql):
    """执行一条 ALTER；列已存在（重复启动）时忽略。"""
    from sqlalchemy import text

    try:
        db.session.execute(text(sql))
        db.session.commit()
    except Exception:  # noqa: BLE001
        db.session.rollback()


def _backfill_user_devices():
    """存量 user.open_id 一次性搬入 user_device（幂等：已存在的 openid 跳过）。

    user 表没有 open_id 列（如 MySQL 新库或迁移已完成删列）时直接跳过。
    """
    from backend.models.device import Device
    from sqlalchemy import inspect, text

    if "open_id" not in [c["name"] for c in inspect(db.engine).get_columns("user")]:
        return

    result = db.session.execute(text(
        "INSERT INTO user_device (user_id, openid, online, created_at, updated_at) "
        "SELECT id, open_id, :unknown, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM user "
        "WHERE open_id IS NOT NULL AND open_id != '' "
        "AND open_id NOT IN (SELECT openid FROM user_device)"
    ), {"unknown": Device.ONLINE_UNKNOWN})
    if result.rowcount:
        db.session.commit()


def _try_drop_user_openid():
    """迁移完成后删掉 user.open_id 旧列（SQLite 因 UNIQUE 约束删不掉就保留，
    模型已不含该字段，不影响运行；MySQL 生产库可正常删）。"""
    _try_alter("ALTER TABLE user DROP COLUMN open_id")


def _drop_user_device_openid_unique():
    """解除 user_device.openid 唯一约束（多对多后同一设备允许多账号各一行）。

    MySQL 直接删唯一索引；SQLite 列级 UNIQUE 无法 ALTER，按当前模型重建表。
    """
    import sqlalchemy as sa
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    if "user_device" not in insp.get_table_names():
        return
    if db.engine.dialect.name != "sqlite":
        for idx in insp.get_indexes("user_device"):
            if idx["name"] == "openid" and idx["unique"]:
                _try_alter("ALTER TABLE user_device DROP INDEX openid")
                return
        return

    # SQLite：借 ORM 当前定义建 user_device_new → 拷数据 → 换名 → 重建索引
    from backend.models.user_device import UserDevice  # noqa: F401 触发表注册

    table = db.metadata.tables["user_device"]
    tmp_meta = sa.MetaData()  # 独立临时 metadata，避免污染共享 ORM 定义
    new_table = table.to_metadata(tmp_meta, name="user_device_new")
    # 只拷贝旧表真实存在的列：新增列（如 deleted_at）在存量库里可能还没加，
    # 直接用 ORM 全列会 INSERT ... SELECT 报 no such column。
    old_cols = {c["name"] for c in insp.get_columns("user_device")}
    cols = ", ".join(c.name for c in table.columns if c.name in old_cols)
    db.session.execute(text(str(sa.schema.CreateTable(new_table).compile(db.engine))))
    db.session.execute(text(
        f"INSERT INTO user_device_new ({cols}) SELECT {cols} FROM user_device"
    ))
    db.session.execute(text("DROP TABLE user_device"))
    db.session.execute(text("ALTER TABLE user_device_new RENAME TO user_device"))
    for index in table.indexes:  # 索引随旧表被删，按 ORM 定义在新表名上重建
        db.session.execute(text(str(sa.schema.CreateIndex(index).compile(db.engine))))
    db.session.commit()


def _backfill_devices():
    """存量 user_device.openid 一次性建 device 字典行并回填 device_id（幂等）。

    - 每个未入库的 openid 建 device 行：name 取 remark（空则 NULL，待补选）、
      org_id 留空（待补选）、online 沿用关联行旧值
    - device_id 为空且 openid 命中字典行的 user_device 回填引用
    """
    from sqlalchemy import inspect, text

    if "device" not in [t for t in inspect(db.engine).get_table_names()]:
        return

    db.session.execute(text(
        "INSERT INTO device (openid, name, org_id, online, created_at) "
        "SELECT ud.openid, MAX(ud.remark), NULL, MAX(ud.online), CURRENT_TIMESTAMP "
        "FROM user_device ud "
        "WHERE ud.openid IS NOT NULL AND ud.openid != '' "
        "AND ud.openid NOT IN (SELECT openid FROM device) "
        "GROUP BY ud.openid"
    ))
    db.session.execute(text(
        "UPDATE user_device SET device_id = "
        "(SELECT d.id FROM device d WHERE d.openid = user_device.openid) "
        "WHERE device_id IS NULL AND openid IS NOT NULL AND openid != ''"
    ))
    db.session.commit()
