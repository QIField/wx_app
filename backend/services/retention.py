"""过期日志物理清理：全库唯一允许物理删除（DELETE）的位置。

业务表（device / user_device / contact / contact_profile / group_member 等）
一律软删除，只写 deleted_at；只有日志表按保留期物理清理。
保留期集中在本文件配置，清理动作本身写入审计，避免“审计被自己删掉”无痕。
"""
from backend.services.access_log import clean_expired as clean_access_logs
from backend.services.audit import (
    AuditLog,
    AuditModule,
    clean_expired_logs,
    log_action,
)
from backend.services.middle_log import clean_expired as clean_middle_logs

# 表名 → 保留天数（与 docs/interface-log.md 的保留期约定保持一致）
RETENTION_DAYS = {
    "access_log": 90,
    "middle_call_log": 90,
    "audit_log": 180,
}


def purge_expired():
    """按保留期清理三张日志表，返回各表清理行数。

    定时任务每天 03:30 调用；清理完再写一条“过期清理”审计，
    保证“谁在什么时候清掉了多少日志”可追溯。
    """
    counts = {
        "access_log": clean_access_logs(days=RETENTION_DAYS["access_log"]),
        "middle_call_log": clean_middle_logs(days=RETENTION_DAYS["middle_call_log"]),
        "audit_log": clean_expired_logs(days=RETENTION_DAYS["audit_log"]),
    }
    log_action(
        AuditModule.SYSTEM,
        "过期清理",
        "日志保留期清理",
        detail=", ".join(f"{k}={v}" for k, v in counts.items()),
    )
    return counts
