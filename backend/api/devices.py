"""设备卡片 API：顶栏多账号切换的数据源（当前登录人的绑定设备）。"""
from flask import Blueprint, g, jsonify
from sqlalchemy import func

from backend.extensions import db
from backend.models.conversation import Conversation
from backend.services.auth import require_role
from backend.services.devices import check_device_online, user_devices

bp = Blueprint("devices", __name__)


@bp.get("/api/devices")
@require_role()
def list_devices():
    """当前账号的绑定设备：openid（路由键）/备注/在线状态/未读数（绑定顺序）。

    脱敏契约：display_name 无备注时按绑定顺序回退「设备N」，不出现 openid 字样。
    """
    devices = user_devices(g.current_user.id)
    if not devices:
        return jsonify(code=0, msg="success", data=[])

    openids = [d.openid for d in devices]
    rows = (
        db.session.query(
            Conversation.openid,
            func.coalesce(func.sum(Conversation.unread_count), 0),
        )
        .filter(Conversation.deleted_at.is_(None), Conversation.openid.in_(openids))
        .group_by(Conversation.openid)
        .all()
    )
    unread = {openid: int(total) for openid, total in rows}
    data = []
    for i, d in enumerate(devices, start=1):
        item = {**d.to_json(), "unread": unread.get(d.openid, 0)}
        if not item["display_name"]:
            item["display_name"] = f"设备{i}"
        data.append(item)
    return jsonify(code=0, msg="success", data=data)


@bp.post("/api/devices/<openid>/online-check")
@require_role()
def check_online_now(openid):
    """点击账号卡片即时查一次在线状态：调中间方 check_online 并回写库。

    只查当前登录人自己绑定的设备，别人的设备按无权拒绝。
    """
    device = next(
        (d for d in user_devices(g.current_user.id) if d.openid == openid), None
    )
    if device is None:
        return jsonify(code=403, msg="无权访问该设备"), 403
    device.online = check_device_online(openid)
    db.session.commit()
    return jsonify(code=0, msg="success",
                   data={"openid": openid, "online": device.online})
