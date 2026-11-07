# 审计日志规范（audit_log）

> 目标：谁、在什么时候、对什么、做了什么、结果如何。只服务「追责与排查」，不是业务数据。
> 对应界面：`prototypes/auth-admin/logs.html`（仅开发者可见）。

## 一、记录原则

**记**：
- 一切**写操作**（新增 / 修改 / 删除 / 状态变更 / 绑定），无论成功失败
- **登录**：成功、失败都记（失败记账号名 + IP，用于发现撞密码）
- **系统自动任务的失败**：同步失败、发送确认失败

**不记**：
- 查询、浏览、搜索等只读操作
- 聊天消息收发本身（业务数据，工作台天然可见）
- 定时任务正常成功的心跳

## 二、表结构（audit_log）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BigIntPK | |
| operator_id | String(64), 可空 | 操作人账号 id；空 = 系统自动任务 |
| operator_name | String(64), 冗余 | 操作时姓名快照（账号删除后历史仍可读） |
| org_name | String(64), 冗余 | 操作时组织快照；系统任务 / 跨组织开发者 / 未分配为空（2026-11-02 补列） |
| role | String(32), 冗余 | 操作时角色快照：developer / admin / agent / system |
| module | String(32) | 模块枚举，见下 |
| action | String(64) | 动宾结构，如「重置密码」 |
| target | String(128) | 能唯一定位对象：`账号 · 姓名` / `任务 uuid` / `客户 手机号` |
| result | String(16) | success / fail |
| detail | String(255), 可空 | 失败原因或补充信息；**result=fail 时必填** |
| ip | String(64), 可空 | 登录、后台操作记录来源 IP；系统任务记 127.0.0.1 |
| created_at | DateTime | 即界面上的「时间」 |

## 三、统一入口（唯一写日志的方式）

实现时建 `backend/services/audit.py`，全项目只允许通过它写日志：

```python
from backend.services.audit import log_action, AuditModule

log_action(
    module=AuditModule.ACCOUNT,
    action="重置密码",
    target=f"{u.username} · {u.name}",
)
```

- `operator` 缺省自动取当前登录人；定时任务 / 系统行为不传，自动记「系统」
- **禁止**在接口里手写 INSERT——新增功能的日志接入 = 调这一个函数
- 模块名必须用枚举常量，禁止裸字符串：

```python
class AuditModule:
    AUTH = "认证"          # 登录成功 / 登录失败
    ACCOUNT = "账号管理"    # 新增 / 编辑 / 启停用 / 重置密码 / 绑定微信设备
    CONTACT = "客户资料"    # 编辑电话 / 城市 / 标签 / 备注
    SYNC = "同步任务"       # 消息同步失败 / 发送确认失败（仅 fail）
    SYSTEM = "系统设置"     # 预留：接口配置变更（该功能后做）
```

## 四、命名规范

| 字段 | 规则 | 示例 |
|---|---|---|
| module | 枚举里选；新功能先加枚举 | 账号管理 |
| action | 动宾结构，≤ 10 字 | 新增账号 / 停用账号 / 绑定微信设备 |
| target | 必须能唯一定位对象，带 ID 优先 | `cs05 · 吴桐` / `任务 uuid 9f3e…c2` |
| result | success / fail | fail 时 detail 必填 |

**失败也记**：写接口的 except 分支里调 `log_action(..., result="fail", detail=异常摘要)` 后照常抛出。例：绑定设备被占用 → fail「该微信设备已绑定其他账号」。

## 五、查看与权限

- 日志查询接口与页面**仅开发者**（管理员也不可看）
- 页面：关键词搜索 + 全量列表，不加分页筛选（量大后再议）

## 六、姓名 + 组织快照规范（全局，2026-11-02 起）

**以后所有新增的、记录"人"的表和操作，一律存「姓名 + 组织」双快照，不允许只存 id 或只存姓名。**

- 已按此规范落地：`audit_log`（operator_name + org_name）、`middle_call_log`（user_name + org_name）、`message`（operator_name + org_name）、`access_log`（user_name + org_name，最初即有）
- 取值时机：**写入那一刻**从账号/组织字典抄下来，不搞关联查询——账号改名、换组织后，历史记录仍是当时的样子（不穿越）
- 留空场景：系统自动任务（无操作人）、跨组织开发者、未分配组织——展示层显示「系统 / 跨组织 / 未分配」
- 内部 `*_id` 关联列照常保留：id 给机器连表用，姓名+组织快照给人直接读，两者并存
- 不适用的地方：聊天气泡、发送日志等"自己看自己"的工作台内部界面（只显示姓名即可，组织是噪音）

## 七、维护

- **只插入，不更新不删除**（唯一例外：清理任务）
- **保留 180 天**，每日定时任务删除过期数据（挂在现有定时器上）
- 清理只走 `backend/services/retention.py` 的 `purge_expired()`，保留期写在该文件；清理完再记一条“过期清理”审计（否则审计被删无痕）
- 与 `docs/database.md` 第三节《软删除规范》一致：业务表软删除，日志表过期物理清理
- 不建外键——账号删除不影响历史日志（operator_name 冗余就是为了这个）
- 表体积按月观察；过大再考虑归档，现在不做

## 八、新功能接入 checklist（6 条）

1. 是写操作吗？只读 → 不记
2. module 在枚举里吗？没有 → 先加枚举再开发
3. action 动宾结构、target 能唯一定位对象
4. 失败路径 catch 里也调 `log_action(result="fail", detail=原因)`
5. 新表记录"人"了吗？→ 按第六节规范带姓名+组织双快照
6. 自测：操作一次 → 日志页能看到，字段齐全（含组织）
