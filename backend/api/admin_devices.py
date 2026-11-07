"""管理后台设备字典 API：设备先入库，再由账号管理关联（多对多）。

权限规则（与账号绑定一致的口径）：
- developer / admin：可查看设备列表（含关联账号）
- developer：新增 / 编辑 / 删除（关联配置仅开发者可操作）
- openid 录入后不可改；仍被账号关联的设备不可删除（409）
"""
from flask import Blueprint, jsonify, request

from backend.extensions import db
from backend.models.device import Device
from backend.models.user import MANAGE_ROLES, ROLE_DEVELOPER
from backend.models.user_device import UserDevice
from backend.services.audit import AuditModule, AuditLog, log_action
from backend.services.auth import require_role

bp = Blueprint("admin_devices", __name__)


def _device_target(device):
    """审计日志的对象格式：设备名（openid）——能唯一定位。"""
    return f"{device.name or device.openid}（{device.openid}）"


def _bound_users(device_id):
    """关联该设备的账号列表（含停用账号，删除拦截提示以真实行数为准）。"""
    from backend.models.user import User

    rows = (
        db.session.query(User)
        .join(UserDevice, UserDevice.user_id == User.id)
        .filter(UserDevice.device_id == device_id, UserDevice.deleted_at.is_(None))
        .order_by(User.id)
        .all()
    )
    return [
        {"id": u.id, "name": u.name, "username": u.username,
         "org_id": u.org_id, "org_name": u.org_name}
        for u in rows
    ]


def _resolve_org(org_id):
    """校验设备归属组织：必填且启用。返回 (Org, None) 或 (None, (响应, 状态码))。"""
    from backend.models.org import Org

    if not org_id:
        return None, (jsonify(code=400, msg="请选择所属组织"), 400)
    try:
        org = db.session.get(Org, int(org_id))
    except (TypeError, ValueError):
        return None, (jsonify(code=400, msg="组织参数不合法"), 400)
    if org is None or org.status != 1:
        return None, (jsonify(code=400, msg="组织不存在或已停用"), 400)
    return org, None


@bp.get("/api/admin/devices")
@require_role(*MANAGE_ROLES)
def list_devices():
    """设备列表：默认只看未删除；?include_deleted=1 为回收站（含已删除）。

    已删除设备同时清零 online，避免回收站里仍显示“在线”。
    """
    include_deleted = request.args.get("include_deleted") == "1"
    q = Device.query
    if not include_deleted:
        q = q.filter(Device.deleted_at.is_(None))
    rows = q.order_by(Device.id).all()
    data = []
    for d in rows:
        data.append({**d.to_json(), "bound_users": _bound_users(d.id)})
    return jsonify(code=0, msg="success", data=data)


@bp.post("/api/admin/devices")
@require_role(ROLE_DEVELOPER)
def create_device():
    """入库新设备：openid 全局唯一（重复 409）。"""
    body = request.get_json(silent=True) or {}
    openid = str(body.get("openid") or "").strip()
    name = str(body.get("name") or "").strip()

    if not openid:
        return jsonify(code=400, msg="请填写设备 ID"), 400
    if len(openid) > 64:
        return jsonify(code=400, msg="设备 ID 不能超过 64 字"), 400
    if not name:
        return jsonify(code=400, msg="请填写设备名称"), 400
    if len(name) > 64:
        return jsonify(code=400, msg="设备名称不能超过 64 字"), 400

    org, err = _resolve_org(body.get("org_id"))
    if err:
        return err

    exists = Device.query.filter_by(openid=openid).first()
    if exists is not None:
        detail = "设备 ID 在回收站中，请先恢复" if exists.is_deleted else "设备 ID 已存在"
        log_action(AuditModule.DEVICE, "新增设备", f"{openid}",
                   result=AuditLog.RESULT_FAIL, detail=detail)
        return jsonify(code=409, msg=f"设备 ID {openid} {detail}"), 409

    device = Device(openid=openid, name=name, org_id=org.id)
    db.session.add(device)
    db.session.commit()
    log_action(AuditModule.DEVICE, "新增设备", _device_target(device),
               detail=f"组织 {org.name}")
    return jsonify(code=0, msg="success", data=device.to_json())


def _active_device(device_id):
    """取未删除的设备；回收站里的行对编辑/删除操作视为不存在。"""
    device = db.session.get(Device, device_id)
    if device is None or device.is_deleted:
        return None
    return device


@bp.put("/api/admin/devices/<int:device_id>")
@require_role(ROLE_DEVELOPER)
def update_device(device_id):
    """编辑设备：名称 / 组织；openid 录入后不可改（body 里的 openid 一律忽略）。"""
    device = _active_device(device_id)
    if device is None:
        return jsonify(code=404, msg="设备不存在"), 404

    body = request.get_json(silent=True) or {}
    name = str(body.get("name") or "").strip()
    if not name:
        return jsonify(code=400, msg="请填写设备名称"), 400
    if len(name) > 64:
        return jsonify(code=400, msg="设备名称不能超过 64 字"), 400

    org, err = _resolve_org(body.get("org_id"))
    if err:
        return err

    changed = []
    if name != (device.name or ""):
        device.name = name
        changed.append("名称")
    if org.id != device.org_id:
        device.org_id = org.id
        changed.append("组织")

    db.session.commit()
    log_action(AuditModule.DEVICE, "编辑设备", _device_target(device),
               detail="、".join(changed) or "无变更")
    return jsonify(code=0, msg="success", data=device.to_json())


@bp.delete("/api/admin/devices/<int:device_id>")
@require_role(ROLE_DEVELOPER)
def delete_device(device_id):
    """删除设备（软删除）：仍被账号关联时 409，需先在账号管理解除关联。"""
    device = _active_device(device_id)
    if device is None:
        return jsonify(code=404, msg="设备不存在"), 404

    linked = UserDevice.query.filter_by(device_id=device_id, deleted_at=None).count()
    if linked:
        log_action(AuditModule.DEVICE, "删除设备", _device_target(device),
                   result=AuditLog.RESULT_FAIL, detail=f"仍被 {linked} 个账号关联")
        return jsonify(
            code=409, msg=f"该设备仍被 {linked} 个账号关联，请先在账号管理中解除关联"
        ), 409

    device.soft_delete()
    device.online = Device.ONLINE_UNKNOWN  # 回收站里不再显示在线
    db.session.commit()
    log_action(AuditModule.DEVICE, "删除设备", _device_target(device), detail="软删除，可恢复")
    return jsonify(code=0, msg="success")


@bp.post("/api/admin/devices/<int:device_id>/restore")
@require_role(ROLE_DEVELOPER)
def restore_device(device_id):
    """从回收站恢复设备：deleted_at 置回 NULL，原 id 与关联不变。"""
    device = db.session.get(Device, device_id)
    if device is None or not device.is_deleted:
        return jsonify(code=404, msg="回收站中没有该设备"), 404

    device.restore()
    db.session.commit()
    log_action(AuditModule.DEVICE, "恢复设备", _device_target(device))
    return jsonify(code=0, msg="success", data=device.to_json())
