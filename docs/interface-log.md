# 接口调用日志规范（interface-log）

> 状态：**已实施**（2026-11-02，P0 日志基建 + P1 查询接口 + P2 组织管理全部上线）。
> 方案原型见 `prototypes/api-log-scheme/index.html`。
> 与 `docs/audit-log.md` 的分工：audit_log 记**业务动作**（谁改了什么，手动埋点）；
> access_log / middle_call_log 记**接口调用流水**（自动、全量、排障用）。互不替代。

## 日志范围

| 链路 | 记录点 | 表 | 接入方式 |
|---|---|---|---|
| 入站：前端 → 后端 API | `app.py` 全局 before/after_request 钩子 | `access_log` | 自动，新接口零代码 |
| 出站：后端 → 中间方 | `adapter/client.call / call_download` | `middle_call_log` | 自动，唯一出口 |

## 条款（对现有功能与未来新功能一律生效）

1. **入站全量自动记录**：任何新接口零代码接入；禁止在业务代码里手写访问日志。
2. **出站唯一出口**：对中间方的所有请求必须经 `adapter/client.call / call_download`，
   **禁止在业务代码直接 `requests.*`**；新增 module / action 无需额外埋点。
3. **完成标准**：新功能验收时，"在 access_log / middle_call_log 能查到该功能的调用记录"
   是完成标准之一；现有功能随 P0/P1 上线自动覆盖。
4. **写失败不阻断业务**：日志环节整体 try/except，失败仅 `app.logger.warning`。
5. **脱敏与截断**：`password / token / authorization` 等字段值打码为 `***`；
   出站响应体截断 2000 字符；媒体二进制只记状态码 + 类型 + 字节数。
6. **豁免清单**：`/api/health`、`/ws`、静态资源、`OPTIONS` 预检不记入站日志；
   媒体接口不豁免（304 缓存命中照记）。
7. **保留期 90 天**：并入现有每日 3:30 清理任务；audit_log 维持 180 天不变。
8. **uuid 串联**：中间方调用的 `uuid` 与 `SendTask.uuid` 同源，发送闭环按 uuid 追踪。

## 关键字段约定

- `user_name / org_name` 存**快照**而非外键（账号停用后历史可读，与 audit_log 同款）。
- `middle_call_log.ret` 单独成列：查询类接口的 `processing_result.ret`
  （如 `500 设备已离线`），便于按业务结果筛选。
- `success`：`code=0` 且非异常为 1；`code!=0` / `ret!=200` / HTTP 异常 / 非 JSON 均为 0。

## 查询接口（P1）

- `GET /api/logs/access`：`start/end/path/user_id/org_id/status/method` 过滤。
- `GET /api/logs/middle`：`start/end/module/action/uuid/success/openid` 过滤。
- 权限 `developer`；只读，删除仅走定时清理。
- 2026-11-02 姓名+组织快照规范：`middle_call_log` 补 `user_name / org_name` 快照列
  （请求上下文有登录人即抄录；定时任务为空），与 `audit_log` / `message` 的
  「姓名 + 组织」双快照规范一致（见 docs/audit-log.md 第六节）。

## 组织管理（P2，已确认方案 A，已实施）

- 2026-11-02 评审结论：**方案 A（仅归属标记）**——组织只是账号属性与检索维度，
  会话/消息等业务数据全部账号互通，不做数据隔离。
- 组织字典固定五条：佛山、珠海、中山、东莞百业、东莞合峰；新建账号必选组织。
- `dev` 开发者账号不绑组织（跨组织）。
- 实施落点：`models/org.py`（幂等种子 `Org.ensure_seed`）、`user.org_id`（DB 可空，
  API 创建/编辑强校验非空，developer 豁免）、`GET /api/orgs`、账号表单组织下拉。
- 存量账号不阻塞：org_id 为空显示「未分配」，编辑时可补选。
- 启动引导自动完成：`upgrade_existing_schema()` 给存量库补列 + 组织种子幂等写入。
