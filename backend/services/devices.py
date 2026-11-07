"""绑定设备查询：账号↔设备多对多关联（user_device + device 字典）的统一口径。

三个职责：
- 账号维度：user_devices / user_openids（关联顺序 = id 升序；openid 自关联行取）
- 全局维度：active_bound_devices（在线检测用，含离线）/ pollable_devices（轮询用，剔除离线）
- 状态维度：check_device_online（中间方 check_online→get_check_online 两步，定时轮询回写）

在线状态唯一事实源在 device 表；同一台设备可被多个账号关联，状态只回写字典行。
"""
from backend.extensions import db


def user_devices(user_id, include_deleted=False):
    """某账号的关联设备列表，按关联顺序（id 升序）。

    include_deleted=True 用于账号编辑：命中已软删的关联行时“复活”，
    避免解除关联后重新关联产生重复行。
    """
    from backend.models.user_device import UserDevice

    q = UserDevice.query.filter_by(user_id=user_id)
    if not include_deleted:
        q = q.filter(UserDevice.deleted_at.is_(None))
    return q.order_by(UserDevice.id).all()


def user_openids(user_id):
    """某账号关联的 openid 列表（关联顺序）。"""
    return [d.openid for d in user_devices(user_id)]


def _linked_device_query():
    """启用账号关联的设备字典查询（join user_device 去重）。"""
    from backend.models.device import Device
    from backend.models.user import User
    from backend.models.user_device import UserDevice

    return (
        db.session.query(Device)
        .join(UserDevice, UserDevice.device_id == Device.id)
        .join(User, UserDevice.user_id == User.id)
        .filter(
            User.status == 1,
            Device.deleted_at.is_(None),
            UserDevice.deleted_at.is_(None),
        )
        .distinct()
    )


def active_bound_devices():
    """启用账号关联的设备 openid 列表（在线状态检测口径，含离线设备）。"""
    return [d.openid for d in _linked_device_query().all()]


def offline_devices():
    """已知离线的设备 openid 集合（online=0，最近一轮检测判定的）。"""
    from backend.models.device import Device

    rows = _linked_device_query().filter(Device.online == Device.ONLINE_OFF).all()
    return {d.openid for d in rows}


def pollable_devices():
    """轮询口径：启用账号关联的设备里未被判定离线的（未知/在线）。

    收消息/发送确认/资料同步等定时轮询都按此取设备；
    离线设备跳过，等在线检测翻身后自动恢复。
    """
    from backend.models.device import Device

    rows = _linked_device_query().filter(Device.online != Device.ONLINE_OFF).all()
    return [d.openid for d in rows]


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
    再用同一 uuid 查 get_check_online，processing_result.data=true/false。
    不下发直接查恒为 data:[]（此前一直误判离线的根因）。
    下发/查询/解包收口到 task_query 共享工具；任何异常（网络错误等）视为离线，下一轮纠正。
    """
    from backend.adapter import client as middle
    from backend.models.device import Device
    from backend.sync import task_query

    if middle.DEMO_MODE:
        return Device.ONLINE_ON
    try:
        task_uuid = task_query.new_task_uuid()
        middle.call("login_api", "check_online", {}, uuid=task_uuid, openid=openid)
        record = task_query.query_record(
            "login_api", "get_check_online", task_uuid, openid=openid, retries=2)
        online = task_query.unwrap_result(record) is True
        return Device.ONLINE_ON if online else Device.ONLINE_OFF
    except Exception:  # noqa: BLE001 中间方不可达 = 离线
        return Device.ONLINE_OFF


def refresh_all_device_online(app):
    """轮询启用账号关联的设备并回写 device.online（定时任务入口）。"""
    with app.app_context():
        from backend.models.device import Device

        openids = active_bound_devices()
        if not openids:
            return
        try:
            for openid in openids:
                device = Device.query.filter_by(openid=openid, deleted_at=None).first()
                if device is not None:
                    device.online = check_device_online(openid)
            db.session.commit()
        except Exception:  # noqa: BLE001 状态轮询失败不影响主业务
            db.session.rollback()
            app.logger.warning("设备在线状态轮询失败", exc_info=True)
