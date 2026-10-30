"""绑定设备查询：消息同步与资料同步共用的"在役设备"口径。"""
from backend.extensions import db


def active_bound_devices():
    """所有绑定微信设备的启用账号的 openid 列表（需在 app 上下文内调用）。"""
    from backend.models.user import User

    rows = (
        db.session.query(User.open_id)
        .filter(User.open_id.isnot(None), User.open_id != "", User.status == 1)
        .all()
    )
    return [r[0] for r in rows]
