"""组织字典 API：使用处下拉（仅启用）+ 管理表格（全量/新增/软删除/恢复）。

软删除 = status 置 0：行保留，账号等历史引用照常按 id 解析组织名；
重名（含已停用）直接拒绝，避免与唯一约束冲突时才报错。
所有写操作记审计日志，业务规则拒绝也记 fail。
"""
from flask import Blueprint, jsonify, request

from backend.extensions import db
from backend.models.org import Org
from backend.models.user import ROLE_ADMIN, ROLE_DEVELOPER, STATUS_OFF, STATUS_ON
from backend.services.audit import AuditLog, AuditModule, log_action
from backend.services.auth import require_role

bp = Blueprint("orgs", __name__)

_MANAGE_ROLES = (ROLE_DEVELOPER, ROLE_ADMIN)
_MAX_NAME = 64  # 与 org.name 列宽一致


def _clean_name(body):
    """取并清洗组织名；非法返回 None。"""
    name = str(body.get("name") or "").strip()
    return name if name and len(name) <= _MAX_NAME else None


@bp.get("/api/orgs")
@require_role(*_MANAGE_ROLES)
def list_orgs():
    """启用中的组织列表：账号表单等使用处的下拉数据源（每次实时查询）。"""
    rows = Org.query.filter_by(status=STATUS_ON).order_by(Org.id).all()
    return jsonify(code=0, msg="success", data=[o.to_json() for o in rows])


@bp.get("/api/orgs/all")
@require_role(*_MANAGE_ROLES)
def list_all_orgs():
    """全量组织列表（含停用）：组织管理表格数据源。"""
    rows = Org.query.order_by(Org.id).all()
    return jsonify(code=0, msg="success", data=[o.to_json() for o in rows])


@bp.post("/api/orgs")
@require_role(*_MANAGE_ROLES)
def create_org():
    """新增组织：重名（含已停用）拒绝，避免恢复语义混淆。"""
    name = _clean_name(request.get_json(silent=True) or {})
    if name is None:
        return jsonify(code=400, msg=f"请填写 1-{_MAX_NAME} 字的组织名"), 400

    if Org.query.filter_by(name=name).first() is not None:
        log_action(AuditModule.ORG, "新增组织", f"组织 {name}",
                   result=AuditLog.RESULT_FAIL, detail="组织名已存在")
        return jsonify(code=400, msg=f"组织 {name} 已存在"), 400

    org = Org(name=name)
    db.session.add(org)
    db.session.commit()
    log_action(AuditModule.ORG, "新增组织", f"组织 {org.name}")
    return jsonify(code=0, msg="success", data=org.to_json())


@bp.put("/api/orgs/<int:org_id>/status")
@require_role(*_MANAGE_ROLES)
def toggle_org_status(org_id):
    """启用 / 停用（软删除）：只改 status，行保留。"""
    org = db.session.get(Org, org_id)
    if org is None:
        return jsonify(code=404, msg="组织不存在"), 404

    status = (request.get_json(silent=True) or {}).get("status")
    if status not in (STATUS_ON, STATUS_OFF):
        return jsonify(code=400, msg="status 仅支持 1启用 / 0停用"), 400
    if status == org.status:
        return jsonify(code=400, msg="组织已处于该状态"), 400

    org.status = status
    db.session.commit()
    log_action(AuditModule.ORG, "启用组织" if status == STATUS_ON else "停用组织",
               f"组织 {org.name}")
    return jsonify(code=0, msg="success", data=org.to_json())
