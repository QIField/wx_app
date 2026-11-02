"""组织字典 API：只读列表（固定五条种子，方案 A 见 docs/interface-log.md §8）。"""
from flask import Blueprint, jsonify

from backend.models.org import Org
from backend.models.user import ROLE_ADMIN, ROLE_DEVELOPER
from backend.services.auth import require_role

bp = Blueprint("orgs", __name__)


@bp.get("/api/orgs")
@require_role(ROLE_DEVELOPER, ROLE_ADMIN)
def list_orgs():
    """启用中的组织列表：账号表单下拉数据源。"""
    rows = Org.query.filter_by(status=1).order_by(Org.id).all()
    return jsonify(code=0, msg="success", data=[o.to_json() for o in rows])
