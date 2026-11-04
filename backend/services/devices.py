"""绑定设备查询：多设备绑定（user_device 表）的统一口径。

三个职责：
- 账号维度：user_devices / user_openids（绑定顺序 = id 升序）
- 全局维度：active_bound_devices（在线检测用，含离线）/ pollable_devices（轮询用，剔除离线）
- 状态维度：check_device_online（中间方 check_online→get_check_online 两步，定时轮询回写）
"""
from uuid import uuid4
import time

from backend.extensions import db


def user_devices(user_id):
    """某账号的绑定设备列表，按绑定顺序（id 升序）。"""
    from backend.models.user_device import UserDevice

    return UserDevice.query.filter_by(user_id=user_id).order_by(UserDevice.id).all()


def user_openids(user_id):
    """某账号绑定的 openid 列表（绑定顺序）。"""
    return [d.openid for d in user_devices(user_id)]


def active_bound_devices():
    """所有启用账号绑定的 openid 列表（在线状态检测的口径，含离线设备）。"""
    from backend.models.user import User
    from backend.models.user_device import UserDevice

    rows = (
        db.session.query(UserDevice.openid)
        .join(User, UserDevice.user_id == User.id)
        .filter(User.status == 1)
        .all()
    )
    return [r[0] for r in rows]


def offline_devices():
    """已知离线的设备 openid 集合（online=0，最近一轮检测判定的）。"""
    from backend.models.user import User
    from backend.models.user_device import UserDevice

    rows = (
        db.session.query(UserDevice.openid)
        .join(User, UserDevice.user_id == User.id)
        .filter(User.status == 1, UserDevice.online == UserDevice.ONLINE_OFF)
        .all()
    )
    return {r[0] for r in rows}


def pollable_devices():
    """轮询口径：启用账号绑定的设备里未被判定离线的（未知/在线）。

    收消息/发送确认/资料同步等定时轮询都按此取设备；
    离线设备跳过，等在线检测翻身后自动恢复。
    """
    from backend.models.user import User
    from backend.models.user_device import UserDevice

    rows = (
        db.session.query(UserDevice.openid)
        .join(User, UserDevice.user_id == User.id)
        .filter(User.status == 1, UserDevice.online != UserDevice.ONLINE_OFF)
        .all()
    )
    return [r[0] for r in rows]


def active_openid_for(user, requested=""):
    """选出本次请求工作的设备 openid（工作台一次只看一个账号）。

    requested 空 → 默认第一个绑定设备；指定了但不在绑定列表 → 拒绝。
    返回 (openid, None) 或 (None, (msg, status))。
    """
    openids = user_openids(user.id)
    if not openids:
        return None, ("当前账号未绑定微信设备", 400)
    requested = (requested or "").strip()
    if not requested:
        return openids[0], None
    if requested not in openids:
        return None, ("无权访问该设备", 403)
    return requested, None


def check_device_online(openid):
    """查单台设备在线状态：1在线 0离线。

    中间方套路（2026-11-04 实测）：两步式——先 check_online 下发任务（只回 code/msg），
    再用同一 uuid 调 get_check_online 查任务记录，processing_result.data=true/false。
    不下发直接查恒为 data:[]（此前一直误判离线的根因）。任务未完成时记录是
    "处理中"文案，补查一次。任何异常（网络错误等）视为离线，下一轮纠正。
    """
    from backend.adapter import client as middle
    from backend.models.user_device import UserDevice
    from backend.sync.task_query import as_dict

    if middle.DEMO_MODE:
        return UserDevice.ONLINE_ON
    uuid = str(uuid4())
    try:
        middle.call("login_api", "check_online", {}, uuid=uuid, openid=openid)
        rows = None
        for delay in (0.5, 2):  # 第二次为兜底补查：首轮记录还在处理中时再等一等
            time.sleep(delay)
            body = middle.call("login_api", "get_check_online", {}, uuid=uuid, openid=openid)
            rows = body.get("data") if isinstance(body, dict) else None
            if any(as_dict(r.get("processing_result")).get("ret") == 200
                   for r in rows or [] if isinstance(r, dict)):
                break
    except Exception:  # noqa: BLE001 中间方不可达 = 离线
        return UserDevice.ONLINE_OFF
    for row in rows or []:
        result = as_dict(row.get("processing_result") if isinstance(row, dict) else None)
        if result.get("ret") == 200:
            return UserDevice.ONLINE_ON if result.get("data") is True else UserDevice.ONLINE_OFF
    return UserDevice.ONLINE_OFF


def refresh_all_device_online(app):
    """轮询所有在役设备的在线状态并回写 user_device.online（定时任务入口）。"""
    with app.app_context():
        from backend.models.user_device import UserDevice

        openids = active_bound_devices()
        if not openids:
            return
        try:
            for openid in openids:
                row = UserDevice.query.filter_by(openid=openid).first()
                if row is not None:
                    row.online = check_device_online(openid)
            db.session.commit()
        except Exception:  # noqa: BLE001 状态轮询失败不影响主业务
            db.session.rollback()
            app.logger.warning("设备在线状态轮询失败", exc_info=True)
