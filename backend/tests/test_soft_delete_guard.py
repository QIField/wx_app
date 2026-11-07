"""软删除守护测试：业务代码里不允许出现物理删除。

唯一允许 DELETE 的位置是日志保留期清理（三个 log service + retention 入口）。
新增业务表删除时若用了 db.session.delete / query.delete，这条测试会直接失败。
"""
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ALLOWED = {
    "services/access_log.py",
    "services/audit.py",
    "services/middle_log.py",
    "services/retention.py",
}
PATTERNS = ("db.session.delete(", "session.delete(", ".delete()")


def _hits():
    found = []
    for path in BACKEND.rglob("*.py"):
        rel = path.relative_to(BACKEND).as_posix()
        if rel.startswith("tests/") or rel in ALLOWED:
            continue
        for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if PATTERNS[0] in line or PATTERNS[1] in line:
                found.append(f"{rel}:{no}: {line.strip()}")
            elif PATTERNS[2] in line and ".query.filter(" in line:
                found.append(f"{rel}:{no}: {line.strip()}")
    return found


def test_no_physical_delete_outside_retention():
    hits = _hits()
    assert not hits, "业务代码出现物理删除（改为写 deleted_at）：\n" + "\n".join(hits)
