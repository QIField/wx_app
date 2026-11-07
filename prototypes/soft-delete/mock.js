/* ===== 方案页唯一数据源（页面只读这里，不散落硬编码） =====
   group: compliant=已有 deleted_at | hard=硬删除需改 | purge=日志清理例外
          | status=用 status 软删 | missing=缺字段且会漏删
*/

const TABLES = [
  {
    name: "conversation", group: "compliant",
    current: "已有 deleted_at，读路径均过滤",
    target: "保持",
    action: "补 deleted_at 过滤/索引检查",
    risk: "低",
  },
  {
    name: "message", group: "compliant",
    current: "已有 deleted_at；撤回用 payload.revoked 标记",
    target: "保持",
    action: "确认所有统计查询带过滤",
    risk: "低",
  },
  {
    name: "send_task", group: "compliant",
    current: "已有 deleted_at，无删除入口",
    target: "保持",
    action: "补管理端回收站（可选）",
    risk: "低",
  },
  {
    name: "sync_cursor", group: "compliant",
    current: "已有 deleted_at，按设备+类型唯一",
    target: "保持",
    action: "无",
    risk: "低",
  },
  {
    name: "device", group: "hard",
    current: "db.session.delete(device) 物理删除，无 deleted_at",
    target: "软删除 + 恢复",
    action: "加 deleted_at；删除改打标记；补恢复接口",
    risk: "高：设备字典是 openid 唯一事实源",
  },
  {
    name: "user_device", group: "hard",
    current: "解除关联时 db.session.delete(row) 物理删除",
    target: "软删除 + 复活",
    action: "加 deleted_at；再关联时命中旧行置 NULL",
    risk: "高：绑定历史丢失，易产生重复行",
  },
  {
    name: "access_log", group: "purge",
    current: "按 access_time 保留 90 天后批量 DELETE",
    target: "保留例外",
    action: "统一到 purge 入口；补清理审计",
    risk: "中：无 deleted_at，但属过期数据",
  },
  {
    name: "audit_log", group: "purge",
    current: "按 created_at 保留期批量 DELETE",
    target: "保留例外",
    action: "统一到 purge 入口；清理动作本身要留痕",
    risk: "中：审计表被自己删掉",
  },
  {
    name: "middle_call_log", group: "purge",
    current: "按 call_time 保留期批量 DELETE",
    target: "保留例外",
    action: "统一到 purge 入口；保留期可配置",
    risk: "中：出站排障证据会过期",
  },
  {
    name: "user", group: "status",
    current: "status=0 停用，不删除；无 deleted_at",
    target: "status 即软删除",
    action: "明确语义；管理端启用即恢复",
    risk: "低：可恢复",
  },
  {
    name: "org", group: "status",
    current: "status=0 停用，已有恢复接口",
    target: "status 即软删除",
    action: "文档标注；无需加 deleted_at",
    risk: "低：可恢复",
  },
  {
    name: "contact", group: "missing",
    current: "只 upsert；好友被删后旧行永久残留",
    target: "加 deleted_at",
    action: "同步差异置 deleted_at；读路径过滤",
    risk: "中：残留脏数据",
  },
  {
    name: "contact_profile", group: "missing",
    current: "只覆盖更新，无删除接口",
    target: "加 deleted_at",
    action: "补软删除与恢复，读路径过滤",
    risk: "低",
  },
  {
    name: "group_member", group: "missing",
    current: "只 upsert；退群成员不会被标记",
    target: "加 deleted_at",
    action: "成员清单差异置 deleted_at；读路径过滤",
    risk: "低",
  },
];

const GROUPS = {
  compliant: { label: "已合规", cls: "ok", note: "已有 deleted_at" },
  hard: { label: "必须改", cls: "hard", note: "物理删除，不可恢复" },
  purge: { label: "日志例外", cls: "purge", note: "仅过期清理可物理删除" },
  status: { label: "状态即软删", cls: "status", note: "status=0，可恢复" },
  missing: { label: "待补字段", cls: "missing", note: "缺 deleted_at" },
};

/* 字段字典：点击卡片展开 */
const FIELDS = [
  {
    name: "deleted_at",
    type: "DATETIME NULL",
    sum: "软删除的唯一事实源：NULL=正常，非 NULL=该行被删除的时间。",
    rows: [
      ["取值", "NULL / '2026-11-07 10:23:41'"],
      ["写入", "删除=now()；恢复=置回 NULL；只在 service 层写"],
      ["读取", "所有业务查询追加 WHERE deleted_at IS NULL；回收站反过来只查非 NULL"],
      ["坑", "<span class='warn'>软删除后同自然键再次插入会撞唯一键，必须“复活”旧行而不是新增</span>"],
      ["索引", "高频表建议 (deleted_at) 或与业务键组成联合索引"],
    ],
  },
  {
    name: "status",
    type: "SMALLINT",
    sum: "业务启停状态，不是删除标记；在 user / org 上承担“可恢复的软删除”。",
    rows: [
      ["user", "1=启用 0=停用；停用后不能登录，历史行仍可解析"],
      ["org", "1=启用 0=停用（软删除）；下拉只出启用项，历史归属仍显示原名"],
      ["message", "0发送中 1已发送 2失败——发送状态，与删除无关"],
      ["send_task", "0待下发 1已下发 2成功 3失败"],
      ["坑", "<span class='warn'>同名不同义：改造时不要用 status 判断“是否删除”</span>"],
    ],
  },
  {
    name: "org_id",
    type: "BIGINT NULL",
    sum: "归属组织标记（方案 A：只标记、不隔离数据），空值=未分配/跨组织。",
    rows: [
      ["写入", "后台创建设备/账号时必填；开发者账号可空"],
      ["读取", "列表按 org_id 展示组织名，日志按组织检索"],
      ["坑", "<span class='warn'>组织停用后不要置空 org_id，否则历史归属无法解析</span>"],
    ],
  },
  {
    name: "openid",
    type: "VARCHAR(64)",
    sum: "中间方设备标识，全局唯一，是消息/会话/通讯录的数据隔离键。",
    rows: [
      ["写入", "设备录入时写入，之后不可修改"],
      ["读取", "user_device 关联校验、会话归属校验、同步游标定位"],
      ["坑", "<span class='warn'>设备软删除后仍被关联引用；删除前必须要求先解除关联</span>"],
    ],
  },
  {
    name: "wxid / chatroom_wxid",
    type: "VARCHAR(64)",
    sum: "微信侧对象 ID：好友/群/群成员的身份键，与 openid 组成联合唯一。",
    rows: [
      ["contact", "唯一键 (openid, wxid)，软删除后同键需复活"],
      ["group_member", "唯一键 (openid, chatroom_wxid, wxid)"],
      ["坑", "微信侧对象消失时应打 deleted_at，而不是保留脏行或物理删除"],
    ],
  },
  {
    name: "last_msg_at",
    type: "DATETIME",
    sum: "会话最后消息时间（冗余字段），用于会话列表排序，避免联表。",
    rows: [
      ["写入", "收/发/撤回消息时同步更新"],
      ["读取", "会话列表 ORDER BY last_msg_at DESC"],
      ["坑", "软删除消息后要回算 last_msg，否则列表摘要指向已删消息"],
    ],
  },
  {
    name: "must_change_password",
    type: "SMALLINT",
    sum: "1=仍是初始密码，登录后必须改密；与删除恢复无关，但属于账号状态位。",
    rows: [
      ["写入", "创建账号/重置密码时置 1，改密成功后置 0"],
      ["读取", "登录与鉴权中间件拦截"],
      ["坑", "不要和 status 混在一个字段里表达"],
    ],
  },
  {
    name: "request_payload",
    type: "JSON",
    sum: "发送任务留底：调用中间方的完整参数，排障证据。",
    rows: [
      ["写入", "创建 send_task 时一次性写入"],
      ["读取", "开发者排障、失败重试定位"],
      ["坑", "含敏感内容；日志清理只按时间，不按业务软删"],
    ],
  },
  {
    name: "online",
    type: "SMALLINT",
    sum: "设备在线状态：-1 未知 0 离线 1 在线，由轮询回写，全系统唯一事实源。",
    rows: [
      ["写入", "check_online 定时轮询"],
      ["读取", "客服工作台展示、发送前判断"],
      ["坑", "软删除设备要同时把 online 归为 -1，避免前端显示在线"],
    ],
  },
  {
    name: "last_sync_time",
    type: "DATETIME",
    sum: "同步游标：每台设备每种类型一行，记录拉到哪个时间点。",
    rows: [
      ["写入", "每轮同步成功后续写"],
      ["读取", "只拉游标之后的增量"],
      ["坑", "游标行软删除等于重置同步起点，必须二次确认"],
    ],
  },
];

/* 实施步骤 */
const STEPS = [
  {
    no: "01",
    title: "模型层：统一 SoftDeleteMixin",
    detail: "先给会删除的表加字段，已有 4 张保持；org / user 保留 status 并写入文档作为“软删除等价实现”。",
    code:
`class Device(db.Model, SoftDeleteMixin):
    __tablename__ = "device"
    # openid 全局唯一，删除只打标记

class UserDevice(db.Model, SoftDeleteMixin):
    # 再关联时：命中已删行 -> deleted_at=None（复活），不新增
    __table_args__ = (
        db.UniqueConstraint("user_id", "device_id", name="uk_user_device"),
    )`,
  },
  {
    no: "02",
    title: "迁移：补列 + 补索引",
    detail: "MySQL 加列是瞬时的；给 deleted_at 建索引，避免默认过滤导致全表扫描。",
    code:
`ALTER TABLE device
  ADD COLUMN deleted_at DATETIME NULL COMMENT '软删除：NULL=正常',
  ADD INDEX idx_device_deleted (deleted_at);

ALTER TABLE user_device
  ADD COLUMN deleted_at DATETIME NULL COMMENT '软删除：NULL=正常';

ALTER TABLE contact         ADD COLUMN deleted_at DATETIME NULL;
ALTER TABLE contact_profile ADD COLUMN deleted_at DATETIME NULL;
ALTER TABLE group_member    ADD COLUMN deleted_at DATETIME NULL;
-- 唯一键保持不动；软删除后靠“复活旧行”避免冲突`,
  },
  {
    no: "03",
    title: "写操作：只替换两处物理删除",
    detail: "device 删除与 user_device 解除关联改打标记；恢复走同一个 service，保证审计一致。",
    code:
`def soft_delete(obj, operator):
    obj.deleted_at = datetime.now()
    log_action(AuditModule.DEVICE, "删除", _target(obj), detail=operator)
    db.session.commit()

def restore(obj, operator):
    obj.deleted_at = None
    log_action(AuditModule.DEVICE, "恢复", _target(obj), detail=operator)
    db.session.commit()

# 调用处
- db.session.delete(device)
+ soft_delete(device, current_user.name)`,
  },
  {
    no: "04",
    title: "读路径：默认过滤 + 回收站参数",
    detail: "业务查询默认 WHERE deleted_at IS NULL；只有管理端“回收站”显式 with_deleted。",
    code:
`def active(model):
    return model.query.filter(model.deleted_at.is_(None))

# 回收站
Device.query.filter(Device.deleted_at.isnot(None))

# 唯一键冲突时复活旧行（不要 INSERT）
row = Device.query.filter_by(openid=openid).first()   # 含已删
if row:
    row.deleted_at = None
else:
    db.session.add(Device(openid=openid, ...))`,
  },
  {
    no: "05",
    title: "日志例外：只保留一条物理清理通道",
    detail: "三张日志表统一到 purge_expired()，保留期配置化；清理动作必须写入审计，避免“审计被自己删掉”。",
    code:
`# services/retention.py  唯一允许物理删除的文件
TARGETS = [
    (AccessLog,      AccessLog.access_time,      90),
    (AuditLog,       AuditLog.created_at,       180),
    (MiddleCallLog,  MiddleCallLog.call_time,    90),
]

def purge_expired():
    for model, time_col, days in TARGETS:
        cutoff = datetime.now() - timedelta(days=days)
        model.query.filter(time_col < cutoff).delete()  # 白名单内唯一 DELETE
    log_action(AuditModule.SYSTEM, "过期清理", detail="日志保留期到期")`,
  },
  {
    no: "06",
    title: "守护：禁止回退的检查",
    detail: "在 CI / 预提交加一条 grep：业务代码里出现 session.delete 或 .delete() 直接失败，只放行 retention 白名单。",
    code:
`# scripts/check_soft_delete.ps1
$hit = Get-ChildItem backend -Recurse -Include *.py |
  Select-String -Pattern "session\\.delete\\(|query.*\\.delete\\(\\)" |
  Where-Object { $_.Path -notmatch "retention.py|tests" }
if ($hit) { $hit | ForEach-Object { Write-Error $_.Line }; exit 1 }`,
  },
];

/* 恢复演示：设备字典 */
const DEMO_DEVICES = [
  { id: 1, name: "销售一组手机", openid: "wxid_dev_a1", org: "佛山", linked: 3, deletedAt: null },
  { id: 2, name: "客服值班机", openid: "wxid_dev_b7", org: "珠海", linked: 5, deletedAt: null },
  { id: 3, name: "仓库备用机", openid: "wxid_dev_c3", org: "中山", linked: 0, deletedAt: "2026-11-05 14:20:00" },
  { id: 4, name: "售后专用机", openid: "wxid_dev_d9", org: "东莞百业", linked: 0, deletedAt: "2026-10-30 09:10:00" },
  { id: 5, name: "新购备用机", openid: "wxid_dev_e5", org: "佛山", linked: 0, deletedAt: null },
];

/* 验收清单 */
const CHECKS = [
  "全库 grep 无 db.session.delete / 批量 .delete()（仅 retention 白名单）",
  "14 张表都有 deleted_at，或已书面定义 status 软删语义",
  "所有业务读查询默认带 deleted_at IS NULL",
  "设备删除后能从回收站恢复，且原有关联仍在",
  "解除关联后再次关联走“复活”，不产生重复行",
  "已删除数据不出现在列表、统计、下拉与同步结果",
  "日志物理清理有保留期配置 + 清理审计 + 单一入口",
  "docs/database.md 从 7 张表更新为 14 张，并写明例外",
];
