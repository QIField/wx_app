"""资料同步任务队列：30 分钟兜底轮与登录触发统一入队，单线程串行执行。

设计目标（见 prototype/profile-sync-queue/index.html）：
- 互斥：唯一的 worker 线程消费队列，定时轮与登录触发不会并发；
- 排队：多账号按 FIFO 逐台执行，不叠加中间方请求；
- 去重：同一设备 / 同一兜底轮已在队列或执行中时不重复投递；
- 冷却：登录触发按设备冷却（默认 6 小时），避免反复登录重复拉取。

边界：队列是进程内内存结构，只适用于当前单进程部署。
"""
import queue
import threading
import time

from backend.config import PROFILE_LOGIN_COOLDOWN_SECONDS, PROFILE_LOGIN_SYNC_ENABLED
from backend.extensions import db
from backend.services.audit import AuditLog, AuditModule, log_action

SWEEP_KEY = "sweep"

_job_queue = queue.Queue()
_state_lock = threading.Lock()
_queued_keys = set()          # 已在队列或执行中的任务 key
_login_last_at = {}           # openid -> monotonic 秒，供登录冷却判断
_worker = None
_worker_app = None


def enqueue_sweep(app):
    """30 分钟兜底轮入队；已有一轮在队列/执行中则跳过。"""
    if not _reserve(SWEEP_KEY):
        return False
    _put(app, {"type": "sweep", "key": SWEEP_KEY, "reason": "scheduled"})
    return True


def enqueue_device(app, openid, reason="login"):
    """单设备全量任务入队；同设备排队中或处于登录冷却期则跳过。"""
    if not openid:
        return False
    key = _device_key(openid)
    if not _reserve_device(key, openid, reason):
        return False
    _put(app, {"type": "device", "key": key, "openid": openid, "reason": reason})
    return True


def enqueue_login_sync(app, user):
    """登录成功后调用：已绑定设备且账号启用才入队；队列层负责冷却与去重。"""
    if not PROFILE_LOGIN_SYNC_ENABLED:
        return False
    if user is None or not getattr(user, "open_id", None) or not user.enabled:
        return False
    return enqueue_device(app, user.open_id, reason="login")


def ensure_worker(app):
    """启动唯一的 worker 线程（幂等）；测试环境不启动，避免内存 SQLite 跨线程。"""
    global _worker, _worker_app
    if app.config.get("TESTING"):
        return
    with _state_lock:
        if _worker is not None and _worker.is_alive():
            return
        _worker_app = app
        _worker = threading.Thread(
            target=_run_forever, name="profile-sync-worker", daemon=True
        )
        _worker.start()


def _reserve(key):
    with _state_lock:
        if key in _queued_keys:
            return False
        _queued_keys.add(key)
        return True


def _reserve_device(key, openid, reason):
    with _state_lock:
        if key in _queued_keys:
            return False
        if reason == "login":
            now = time.monotonic()
            last = _login_last_at.get(openid)
            if last is not None and now - last < PROFILE_LOGIN_COOLDOWN_SECONDS:
                return False
            _login_last_at[openid] = now
        _queued_keys.add(key)
        return True


def _put(app, job):
    ensure_worker(app)
    _job_queue.put(job)


def _release(job):
    with _state_lock:
        _queued_keys.discard(job["key"])


def _run_forever():
    """消费循环：一次只执行一个任务；失败只记日志，不中断后续任务。"""
    app = _worker_app
    while True:
        job = _job_queue.get()
        try:
            with app.app_context():
                try:
                    _execute(job, app)
                finally:
                    db.session.remove()
        except Exception as exc:  # noqa: BLE001 单任务失败不影响队列
            app.logger.warning("资料同步任务失败(%s): %s", job.get("type"), exc)
            _log_failure(app, job, exc)
        finally:
            _release(job)
            _job_queue.task_done()


def _execute(job, app):
    from backend.sync import profile_sync

    if job["type"] == "sweep":
        profile_sync.sync_profiles(app)
    else:
        profile_sync.sync_device_full(job["openid"])


def _log_failure(app, job, exc):
    """审计兜底：任务整体失败时记一条 fail（内部步骤失败各自已记）。"""
    target = f"设备 {job['openid']}" if job.get("openid") else "全部设备"
    try:
        with app.app_context():
            log_action(AuditModule.SYNC, "资料同步任务", target,
                       result=AuditLog.RESULT_FAIL, detail=str(exc)[:255])
    except Exception:  # noqa: BLE001 日志失败不能再拖垮 worker
        pass


def _device_key(openid):
    return f"device:{openid}"


def _reset_for_tests():
    """单测清理模块级状态（不启动 worker，队列任务直接丢弃）。"""
    with _state_lock:
        _queued_keys.clear()
        _login_last_at.clear()
    while True:
        try:
            job = _job_queue.get_nowait()
        except queue.Empty:
            break
        else:
            _job_queue.task_done()
