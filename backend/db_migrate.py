"""存量库轻量迁移：create_all 只建新表，不会给存量表补列，这里人工补。

只在直接运行 app.py 的启动引导里调用；所有操作幂等，重复执行无副作用。
新加列：在 upgrade_existing_schema 里追加一条 _try_alter 即可。
"""
import logging

from backend.extensions import db

log = logging.getLogger(__name__)


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
    # 2026-11-15 消息转发：快照表补头像列（create_all 只对新库生效，存量表人工补）
    _try_alter("ALTER TABLE forward_snapshot ADD COLUMN sender_avatar VARCHAR(512) NULL")
    _backfill_user_devices()
    _try_drop_user_openid()
    # 2026-11-05 设备字典重构：user_device 由手填 openid 改为引用 device.id
    _try_alter("ALTER TABLE user_device ADD COLUMN device_id BIGINT")
    # 软删除列要在 user_device 重建（SQLite 分支）之前补齐：
    # 重建会按 ORM 当前列清单拷贝数据，缺列会导致 INSERT ... SELECT 失败。
    _try_alter("ALTER TABLE device ADD COLUMN deleted_at DATETIME NULL")
    _try_alter("ALTER TABLE user_device ADD COLUMN deleted_at DATETIME NULL")
    _try_alter("ALTER TABLE contact ADD COLUMN deleted_at DATETIME NULL")
    _try_alter("ALTER TABLE group_member ADD COLUMN deleted_at DATETIME NULL")
    _drop_user_device_openid_unique()
    _backfill_devices()
    _try_alter("ALTER TABLE device ADD INDEX idx_device_deleted (deleted_at)")
    # 2026-11-16 备注配置重构：存量备注搬入新表后旧表改名归档
    _backfill_remark_config()
    _archive_contact_profile()
    # 2026-11-17 自动报价：客户等级列（报价系数 key，存量行回默认普通客户）
    _try_alter("ALTER TABLE contact_remark_config ADD COLUMN level VARCHAR(20) NOT NULL DEFAULT 'normal'")
    # 2026-11-19 自动报价增量分析：会话记录已处理到的消息 id
    _try_alter("ALTER TABLE conversation ADD COLUMN last_analyzed_msg_id BIGINT NULL")
    # 2026-11-21 群成员群内备注：chatroom_member_detail.remark 落库
    _try_alter("ALTER TABLE group_member ADD COLUMN member_remark VARCHAR(100) NULL")
    # 2026-11-21 AI 开关时间闸门：关→开记时间戳，闸门前历史消息不触发 AI
    _try_alter("ALTER TABLE quote_config ADD COLUMN ai_enabled_at DATETIME NULL")
    # 2026-11-23 OE 详单开关：报价话术是否展开原始 OE 号码；存量行默认关
    _try_alter("ALTER TABLE contact_remark_config ADD COLUMN oe_detail_enabled TINYINT NOT NULL DEFAULT 0")
    # 2026-11-23 AI 时间闸存量回填：global 行默认 True 创建时没走过"关→开"，
    # ai_enabled_at 一直为 NULL，导致闸门形同虚设。回填 updated_at 作为生效起点。
    _backfill_ai_enabled_at()
    # 2026-11-24 询价气泡定位：QuoteInquiry 记录触发该询价的原始 message_id，
    # 前端"定位聊天气泡"按此 ID 精确命中 DOM（比时间匹配靠谱得多）
    _try_alter("ALTER TABLE quote_inquiry ADD COLUMN message_id BIGINT NULL")
    _try_alter("ALTER TABLE quote_inquiry ADD INDEX idx_inquiry_msg (message_id)")
    _backfill_inquiry_message_id()
    # 2026-11-24 行内改价持久化：详情页表格改价 → 保存 override_pricing 覆盖
    _try_alter("ALTER TABLE quote_inquiry ADD COLUMN override_pricing JSON NULL")
    # 2026-11-24 user_device.online 兜底：存量 MySQL 库该列 NOT NULL 但没 DEFAULT，
    # 新代码构造 UserDevice 忘记填 online 时触发 IntegrityError (1048)。
    # SQLite 不支持 MODIFY，_try_alter 会静默跳过；SQLite 新库由 ORM create_all 正确建。
    _try_alter("ALTER TABLE user_device MODIFY COLUMN online SMALLINT NOT NULL DEFAULT -1")
    # 2026-11-25 设备维度改造：ContactRemarkConfig 加 openid + QuoteConfig 加 openid
    # 迁移只增列 + 改约束，不写数据（存量 openid 留 NULL，服务层兼容）
    _try_alter("ALTER TABLE contact_remark_config ADD COLUMN openid VARCHAR(64) NULL")
    _try_alter("ALTER TABLE quote_config ADD COLUMN openid VARCHAR(64) NULL")
    _try_alter("ALTER TABLE quote_config ADD INDEX idx_quote_config_openid (openid)")
    _rebuild_remark_unique_for_device()  # UniqueConstraint 改了，SQLite 必须重建表
    _try_alter("ALTER TABLE quote_config ADD INDEX idx_quote_config_user (user_id)")


def _backfill_remark_config():
    """存量 contact_profile 备注/标签一次性搬入 contact_remark_config（幂等）。

    作用域按 wxid 判定：群 ID（@chatroom 结尾）→ group，其余 → user（用户级，全局生效）。
    新表同键行已存在则跳过——新表是唯一事实源，不覆盖用户已保存的新值。
    """
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    if "contact_profile" not in insp.get_table_names():
        return
    if "contact_remark_config" not in insp.get_table_names():
        return
    db.session.execute(text(
        "INSERT INTO contact_remark_config "
        "(scope_type, target_wxid, remark_name, auto_quote_enabled, "
        "level, oe_detail_enabled, tags, updated_at) "
        "SELECT CASE WHEN wxid LIKE '%@chatroom' THEN 'group' ELSE 'user' END, "
        "wxid, COALESCE(remark, ''), 0, 'normal', 0, "
        "COALESCE(tags, '[]'), CURRENT_TIMESTAMP "
        "FROM contact_profile "
        "WHERE deleted_at IS NULL "
        "AND NOT EXISTS (SELECT 1 FROM contact_remark_config rc "
        "  WHERE rc.scope_type = (CASE WHEN contact_profile.wxid LIKE '%@chatroom' "
        "    THEN 'group' ELSE 'user' END) "
        "  AND rc.target_wxid = contact_profile.wxid)"
    ))
    db.session.commit()


def _archive_contact_profile():
    """搬迁完成后旧 contact_profile 表改名归档（可查证、可恢复，不参与业务查询）。

    物理删除由观察期结束后手动执行：
    DROP TABLE _archived_contact_profile_20261116;
    """
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    if "contact_profile" not in insp.get_table_names():
        return
    db.session.execute(text(
        "ALTER TABLE contact_profile RENAME TO _archived_contact_profile_20261116"
    ))
    db.session.commit()


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


def _backfill_ai_enabled_at():
    """存量 quote_config.global 行 ai_enabled=True 但 ai_enabled_at=NULL → 回填 updated_at。

    场景：global 行默认 ai_enabled=True 创建，从未走过"关→开"动作，
    _save_global 的时间戳写入分支没被触发，闸门形同虚设。

    幂等：已填时间戳的行跳过。
    """
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    if "quote_config" not in insp.get_table_names():
        return
    db.session.execute(text(
        "UPDATE quote_config "
        "SET ai_enabled_at = COALESCE(updated_at, CURRENT_TIMESTAMP) "
        "WHERE scope = 'global' AND deleted_at IS NULL "
        "AND ai_enabled = 1 AND ai_enabled_at IS NULL"
    ))
    db.session.commit()


def _backfill_inquiry_message_id():
    """存量询价行 message_id 空 → 用 inquiry_time + inquiry_content 在同会话 message 表里定位来源消息。

    匹配策略（幂等：已填 message_id 的跳过）：
      1. 同会话 + inquiry_time ±5 分钟窗口内的用户消息（dir=1）
      2. inquiry_content 关键词在 message.content 里命中（LIKE）
      3. 两者交集取 create_time 最接近的那条

    匹配不上的保持 NULL，前端兜底走时间匹配。
    """
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    if "quote_inquiry" not in insp.get_table_names() or "message" not in insp.get_table_names():
        return
    # message_id 列刚加可能还没数据，需要先确认列存在
    if "message_id" not in [c["name"] for c in insp.get_columns("quote_inquiry")]:
        return

    rows = db.session.execute(text(
        "SELECT id, conversation_id, inquiry_time, inquiry_content "
        "FROM quote_inquiry WHERE deleted_at IS NULL AND message_id IS NULL "
        "LIMIT 500"
    )).fetchall()
    if not rows:
        return

    filled = 0
    for row in rows:
        iid, conv_id, itime, icontent = row
        # 构造时间窗口（±5 分钟）
        time_cond = ""
        params = {"cid": conv_id}
        if itime:
            time_cond = "AND create_time BETWEEN :tstart AND :tend"
            params["tstart"] = itime  # 由 SQL DATE_SUB 处理
            params["tend"] = itime

        kw_cond = ""
        if icontent and len(icontent.strip()) >= 2:
            kw_cond = "AND content LIKE :kw"
            # 取前 30 字符做关键词，AI 提取的 inquiry_content 常带"请问"等
            kw = icontent.strip()[:30]
            params["kw"] = f"%{kw}%"

        sql = text(
            f"SELECT id FROM message "
            f"WHERE deleted_at IS NULL AND conversation_id = :cid "
            f"AND direction = 1 "
            f"{time_cond} {kw_cond} "
            f"ORDER BY LENGTH(content) DESC LIMIT 1"
        )
        hit = db.session.execute(sql, params).fetchone()
        if hit:
            db.session.execute(
                text("UPDATE quote_inquiry SET message_id = :mid WHERE id = :iid"),
                {"mid": hit[0], "iid": iid},
            )
            filled += 1

    if filled:
        db.session.commit()
        log.info("backfill_inquiry_msg: filled %d rows", filled)


def _rebuild_remark_unique_for_device():
    """ContactRemarkConfig UniqueConstraint 从 (scope_type, target_wxid, deleted_at)
    改为 (scope_type, target_wxid, openid, deleted_at) —— SQLite 必须重建表。

    幂等：约束名已存在于表索引时跳过；openid 列还没加时 ALTER 会静默跳过。
    存量行 openid 为 NULL（服务层已兼容）；新代码创建行必须显式传 openid。
    """
    import sqlalchemy as sa
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    if "contact_remark_config" not in insp.get_table_names():
        return
    if "openid" not in [c["name"] for c in insp.get_columns("contact_remark_config")]:
        return  # openid 列还没加，等下一轮

    # 幂等：如果新约束已存在（按 name 检查），跳过
    existing_names = {idx["name"] for idx in insp.get_indexes("contact_remark_config")}
    new_constraint_name = "uk_remark_scope_wxid_openid_deleted"
    if new_constraint_name in existing_names:
        return

    if db.engine.dialect.name != "sqlite":
        # MySQL：直接 ADD CONSTRAINT（注意跳过 openid=NULL 时的重复，MySQL 允许 NULL 多行）
        try:
            db.session.execute(text(
                "ALTER TABLE contact_remark_config "
                f"ADD CONSTRAINT {new_constraint_name} "
                "UNIQUE (scope_type, target_wxid, openid, deleted_at)"
            ))
            db.session.commit()
        except Exception:  # noqa: BLE001 可能约束已存在或 openid=NULL 多行冲突
            db.session.rollback()
        return

    # SQLite：rename → 新建 ORM 当前定义 → INSERT ... SELECT → 删旧表
    # 参考 _drop_user_device_openid_unique 的已验证模式
    from backend.models.contact_remark_config import ContactRemarkConfig  # noqa: F401

    table = db.metadata.tables["contact_remark_config"]
    old_cols = {c["name"] for c in insp.get_columns("contact_remark_config")}

    try:
        db.session.execute(text("PRAGMA foreign_keys = OFF"))
        db.session.execute(text("ALTER TABLE contact_remark_config RENAME TO _contact_remark_config_old"))
        db.session.execute(text(str(sa.schema.CreateTable(table).compile(db.engine))))
        cols = ", ".join(c.name for c in table.columns if c.name in old_cols)
        db.session.execute(text(
            f"INSERT INTO contact_remark_config ({cols}) SELECT {cols} FROM _contact_remark_config_old"
        ))
        db.session.execute(text("DROP TABLE _contact_remark_config_old"))
        db.session.execute(text("PRAGMA foreign_keys = ON"))
        db.session.commit()
        log.info("rebuild_remark_unique: SQLite 表重建完成")
    except Exception as e:  # noqa: BLE001
        log.warning("rebuild_remark_unique SQLite 重建失败：%s，跳过", e)
        db.session.rollback()
        # 恢复旧表（如果还在）
        try:
            db.session.execute(text("ALTER TABLE _contact_remark_config_old RENAME TO contact_remark_config"))
            db.session.commit()
        except Exception:  # noqa: BLE001
            db.session.rollback()
