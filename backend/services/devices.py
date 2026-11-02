"""绑定设备查询：多设备绑定（user_device 表）的统一口径。

三个职责：
- 账号维度：user_devices / user_openids（绑定顺序 = id 升序）
- 全局维度：active_bound_devices（消息/资料同步轮询用）
- 状态维度：check_device_online（中间方 get_check_online，定时轮询回写）
"""
from uuid import uuid4

from backend.extensions import db


def user_devices(user_id):
    """某账号的绑定设备列表，按绑定顺序（id 升序）。"""
    from backend.models.user_device import UserDevice

    return UserDevice.query.filter_by(user_id=user_id).order_by(UserDevice.id).all()


def user_openids(user_id):
    """某账号绑定的 openid 列表（绑定顺序）。"""
    return [d.openid for d in user_devices(user_id)]


def active_bound_devices():
    """所有启用账号绑定的 openid 列表（消息/资料同步轮询口径）。"""
    from backend.models.user import User
    from backend.models.user_device import UserDevice

    rows = (
        db.session.query(UserDevice.openid)
        .join(User, UserDevice.user_id == User.id)
        .filter(User.status == 1)
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

    中间方套路：get_check_online 返回任务记录数组，processing_result.data=true/false。
    任何异常（网络错误/结果未生成）都视为离线，下一轮纠正。
    """
    from backend.adapter import client as middle
    from backend.models.user_device import UserDevice
    from backend.sync.task_query import as_dict

    if middle.DEMO_MODE:
        return UserDevice.ONLINE_ON
    try:
        body = middle.call("login_api", "get_check_online", {}, uuid=str(uuid4()), openid=openid)
    except Exception:  # noqa: BLE001 中间方不可达 = 离线
        return UserDevice.ONLINE_OFF
    rows = body.get("data") if isinstance(body, dict) else None
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
