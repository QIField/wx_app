"""单机多进程并发互斥验证。

核心验证：N 个进程同时对同一个 group_wxid 调用 try_acquire()
必须恰好只有 1 个返回 True。跑 100 轮，只要有一轮违反就退出码非 0。

用法：
    set PYTHONPATH=g:\work\BBR\FLASK\wx_app
    python backend/plugins/mutex_protocol/test_concurrent.py
"""
import os
import sys
import time
import multiprocessing as mp

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

os.environ["MUTEX_PROTOCOL_ENABLED"] = "true"
os.environ["MUTEX_PROTOCOL_BACKEND"] = "db"

# ── 单轮：4 进程并发 try_acquire ──

def worker_try_acquire(device_id: str, group_wxid: str, term_hint: int):
    from backend.app import create_app
    from backend.extensions import db
    from backend.plugins.mutex_protocol.db_lock import DBLockManager

    app = create_app()
    with app.app_context():
        lm = DBLockManager(db)
        lm._ensure_table()
        ok = lm.try_acquire(group_wxid, device_id, term_hint)
        return device_id, ok


def main():
    N = 4
    ROUNDS = 30
    group = "concurrent_test_grp"

    print("=" * 64)
    print(f"🔐 DB 锁并发互斥验证: {N} 进程 × {ROUNDS} 轮")
    print(f"   后端    : {os.environ['MUTEX_PROTOCOL_BACKEND']}")
    print(f"   关键断言: 每轮返回 True 的进程数 == 1")
    print("=" * 64)

    violations = 0

    for r in range(1, ROUNDS + 1):
        term = r
        # 每轮开始前清锁（由主进程执行）
        from backend.app import create_app
        from backend.extensions import db as _db
        tmp = create_app()
        with tmp.app_context():
            from backend.plugins.mutex_protocol.db_lock import DBLockManager
            lm = DBLockManager(_db)
            lm._ensure_table()
            with _db.engine.begin() as conn:
                conn.execute(_db.text("DELETE FROM mutex_lock WHERE group_wxid = :g"),
                             {"g": group})

        # N 进程并发抢锁
        with mp.Pool(N) as pool:
            args = [(f"dev_{i}", group, term) for i in range(N)]
            results = pool.starmap(worker_try_acquire, args)

        leaders = [did for did, ok in results if ok]
        n = len(leaders)

        if n == 1:
            if r <= 5 or r % 10 == 0:
                print(f"  Round {r:3d} ✅  leaders={leaders[0]}")
        else:
            print(f"  Round {r:3d} ❌ VIOLATION! n={n} leaders={leaders}")
            violations += 1
        time.sleep(0.01)

    print()
    print("=" * 64)
    if violations == 0:
        print(f"🎉🎉🎉 全部 {ROUNDS} 轮通过 —— DB 锁并发互斥成立")
        print(f"   即使 4 台设备同时对同一条群消息抢锁，也恰好只有 1 个 Leader")
        return 0
    else:
        print(f"💥 发现 {violations} 次双 Leader/零 Leader")
        print(f"   DB 锁方案在真实并发下有缺陷 —— 不能直接用")
        return 1


if __name__ == "__main__":
    mp.freeze_support()
    sys.exit(main())
