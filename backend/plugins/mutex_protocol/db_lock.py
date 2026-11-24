"""DBLockManager: 用项目现有 SQLite/MySQL 实现分布式互斥锁。

设计：
- 通用事务方案（BEGIN + SELECT + 条件 INSERT/UPDATE），SQLite/MySQL 都能跑
- 不依赖方言特定语法（不用 SQLite ON CONFLICT WHERE 或 MySQL ON DUPLICATE）
- 性能：报价轮询通常每秒几十条消息，DB 锁毫秒级开销不是瓶颈

关键实现：
- engine 在第一次有 app context 时抓出来缓存（_get_engine），
  后续心跳线程从缓存拿 engine，不再走 Flask-SQLAlchemy 的 context 检查
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import text

log = logging.getLogger(__name__)

LOCK_TTL_SEC = 30


class DBLockManager:
    """基于项目数据库的分布式互斥锁管理器。

    API 与 Redis LockManager 完全一致 —— 上层代码可以无感切换后端。
    """

    def __init__(self, db):
        self._db = db
        self._engine = None     # 第一次有 context 时抓出来存，心跳线程复用
        self._engine_name = None
        self._table_ready = False

    def _get_engine(self):
        """延迟获取并缓存 engine（第一次调用必须在 app context 内）。"""
        if self._engine is None:
            self._engine = self._db.engine  # 触发 context 检查
            self._engine_name = self._engine.dialect.name
        return self._engine

    # ---------- 内部 ----------

    def _ensure_table(self) -> None:
        if self._table_ready:
            return
        eng = self._get_engine()
        sql = text(
            "CREATE TABLE IF NOT EXISTS mutex_lock ("
            "  group_wxid VARCHAR(128) PRIMARY KEY,"
            "  owner VARCHAR(128) NOT NULL,"
            "  term INTEGER NOT NULL,"
            "  lease_until DATETIME NOT NULL,"
            "  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        try:
            with eng.begin() as conn:
                conn.execute(sql)
            self._table_ready = True
            log.info("🔐 mutex_lock 表已就绪 (backend=%s)", self._engine_name)
        except Exception:
            log.exception("🔐 建 mutex_lock 表失败（将延迟重试）")

    def _lease(self) -> datetime:
        return datetime.utcnow() + timedelta(seconds=LOCK_TTL_SEC)

    def _utcnow(self) -> datetime:
        return datetime.utcnow()

    # ---------- 公共 API ----------

    def try_acquire(self, group_wxid: str, device_id: str, term: int) -> bool:
        """抢锁：事务内 SELECT + 条件 INSERT/UPDATE，带死锁重试。"""
        self._ensure_table()
        lease = self._lease()
        now = self._utcnow()
        eng = self._get_engine()
        max_retries = 3

        for attempt in range(max_retries):
            try:
                with eng.begin() as conn:
                    peek_sql = ("SELECT owner, term, lease_until FROM mutex_lock "
                                "WHERE group_wxid = :g")
                    if self._engine_name != "sqlite":
                        peek_sql += " FOR UPDATE"
                    row = conn.execute(text(peek_sql), {"g": group_wxid}).fetchone()

                    if row is not None:
                        owner, rterm, lease_until = row[0], row[1], row[2]
                        if owner != device_id and lease_until > now:
                            return False
                        if owner == device_id and int(rterm) == int(term):
                            return self.renew(group_wxid, device_id, term)

                        conn.execute(text(
                            "UPDATE mutex_lock SET owner=:o, term=:t, "
                            "lease_until=:l, updated_at=CURRENT_TIMESTAMP "
                            "WHERE group_wxid=:g"
                        ), {"g": group_wxid, "o": device_id, "t": int(term), "l": lease})
                    else:
                        conn.execute(text(
                            "INSERT INTO mutex_lock "
                            "(group_wxid, owner, term, lease_until, updated_at) "
                            "VALUES (:g, :o, :t, :l, CURRENT_TIMESTAMP)"
                        ), {"g": group_wxid, "o": device_id, "t": int(term), "l": lease})

                log.info("🔒 DB 抢锁成功 group=%s owner=%s term=%d (attempt=%d)",
                         group_wxid[:20], device_id[:12], term, attempt + 1)
                return True

            except Exception as exc:
                msg = str(exc).lower()
                if ("deadlock" in msg or "lock wait timeout" in msg) and attempt < max_retries - 1:
                    log.warning("DB 锁冲突，重试 %d/%d group=%s err=%s",
                                attempt + 1, max_retries, group_wxid[:20], type(exc).__name__)
                    time.sleep(0.02 * (attempt + 1))
                    continue
                log.exception("🔒 DB 抢锁异常 group=%s", group_wxid[:20])
                return False

        return False

    def renew(self, group_wxid: str, device_id: str, term: int) -> bool:
        """续租：只有 owner 和 term 都匹配才延长 lease_until。"""
        self._ensure_table()
        eng = self._get_engine()
        lease = self._lease()
        try:
            with eng.begin() as conn:
                result = conn.execute(text(
                    "UPDATE mutex_lock SET lease_until = :l, updated_at = CURRENT_TIMESTAMP "
                    "WHERE group_wxid = :g AND owner = :o AND term = :t"
                ), {"g": group_wxid, "o": device_id, "t": int(term), "l": lease})
                return (getattr(result, "rowcount", 0) or 0) > 0
        except Exception:
            log.exception("续租 DB 异常 group=%s", group_wxid[:20])
            return False

    def release(self, group_wxid: str, device_id: str, term: int) -> bool:
        """释放：只删 owner+term 匹配的行。"""
        self._ensure_table()
        eng = self._get_engine()
        try:
            with eng.begin() as conn:
                result = conn.execute(text(
                    "DELETE FROM mutex_lock "
                    "WHERE group_wxid = :g AND owner = :o AND term = :t"
                ), {"g": group_wxid, "o": device_id, "t": int(term)})
                return (getattr(result, "rowcount", 0) or 0) > 0
        except Exception:
            return False

    def peek(self, group_wxid: str) -> Optional[dict]:
        """读锁内容。"""
        row = self._peek_row(group_wxid)
        if row is None:
            return None
        lease = row["lease_until"]
        if isinstance(lease, datetime):
            lease_until = int(lease.timestamp())
        else:
            lease_until = int(datetime.fromisoformat(str(lease)).timestamp())
        return {
            "owner": row["owner"],
            "term": int(row["term"]),
            "lease": lease_until,
            "ts": int(time.time()),
        }

    # ---------- 内部 ----------

    def _peek_row(self, group_wxid: str) -> Optional[dict]:
        self._ensure_table()
        eng = self._get_engine()
        try:
            with eng.connect() as conn:
                row = conn.execute(text(
                    "SELECT group_wxid, owner, term, lease_until FROM mutex_lock "
                    "WHERE group_wxid = :g"
                ), {"g": group_wxid}).fetchone()
            if row is None:
                return None
            return {
                "group_wxid": row[0],
                "owner": row[1],
                "term": row[2],
                "lease_until": row[3],
            }
        except Exception:
            log.exception("peek DB 异常 group=%s", group_wxid[:20])
            return None
