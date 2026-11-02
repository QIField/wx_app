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
    _backfill_user_devices()
    _try_drop_user_openid()


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
    from backend.models.user_device import UserDevice
    from sqlalchemy import inspect, text

    if "open_id" not in [c["name"] for c in inspect(db.engine).get_columns("user")]:
        return

    result = db.session.execute(text(
        "INSERT INTO user_device (user_id, openid, online, created_at, updated_at) "
        "SELECT id, open_id, :unknown, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM user "
        "WHERE open_id IS NOT NULL AND open_id != '' "
        "AND open_id NOT IN (SELECT openid FROM user_device)"
    ), {"unknown": UserDevice.ONLINE_UNKNOWN})
    if result.rowcount:
        db.session.commit()


def _try_drop_user_openid():
    """迁移完成后删掉 user.open_id 旧列（SQLite 因 UNIQUE 约束删不掉就保留，
    模型已不含该字段，不影响运行；MySQL 生产库可正常删）。"""
    _try_alter("ALTER TABLE user DROP COLUMN open_id")
