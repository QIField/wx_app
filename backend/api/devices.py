"""设备卡片 API：顶栏多账号切换的数据源（当前登录人的绑定设备）。"""
from flask import Blueprint, g, jsonify
from sqlalchemy import func

from backend.extensions import db
from backend.models.conversation import Conversation
from backend.services.auth import require_role
from backend.services.devices import user_devices

bp = Blueprint("devices", __name__)


@bp.get("/api/devices")
@require_role()
def list_devices():
    """当前账号的绑定设备：openid/备注/在线状态/未读数（绑定顺序）。"""
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
    return jsonify(code=0, msg="success", data=[
        {**d.to_json(), "unread": unread.get(d.openid, 0)} for d in devices
    ])
