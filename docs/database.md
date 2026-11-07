# 数据库设计

数据库：MySQL，字符集统一 **utf8mb4**（要存微信表情 emoji，utf8 装不下）。

## 一、14 张表总览

> 新增表必须同时更新本表与第 3 节《软删除规范》，否则视为未完成开发。

| 表 | 干什么用 | 删除策略 | 恢复方式 |
|---|---|---|---|
| conversation | 会话列表（左栏），含未读/置顶 | 软删除 deleted_at | 置回 NULL |
| message | 聊天记录（中栏） | 软删除 deleted_at | 置回 NULL |
| send_task | 发送任务（发给中间方的记录） | 软删除 deleted_at | 置回 NULL |
| sync_cursor | 轮询游标（记上次同步到哪了） | 软删除 deleted_at | 置回 NULL |
| user | 账号（客服/管理员/开发者） | status=0 停用 | 置 status=1 |
| org | 组织（佛山/珠海/中山…） | status=0 停用 | 置 status=1 |
| user_device | 账号与设备的关联（多对多） | 软删除 deleted_at | 再关联时复活旧行 |
| device | 设备字典（openid 唯一事实源） | 软删除 deleted_at | 管理端回收站恢复 |
| contact | 通讯录（好友/群） | 软删除 deleted_at | 名册重新出现时自动复活 |
| contact_profile | 通讯录备注/标签（业务自建） | 软删除 deleted_at | 再次保存时复活旧行 |
| group_member | 群成员（昵称/头像） | 软删除 deleted_at | 重新进群自动复活 |
| access_log | 接口访问日志 | **例外**：90 天后物理清理 | 不可恢复（过期数据） |
| audit_log | 审计日志（谁改了什么） | **例外**：180 天后物理清理 | 不可恢复（过期数据） |
| middle_call_log | 中间方调用日志（排障证据） | **例外**：90 天后物理清理 | 不可恢复（过期数据） |

## 二、核心表建表语句

> customer / quote_order / quote_item 已下线并从文档移除，别再照抄；
> 现存 14 张表的最新字段一律以 `backend/models/` 为准，本节只保留最核心的四张。

### 1. conversation 会话表

```sql
CREATE TABLE conversation (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  openid       VARCHAR(64)  NOT NULL COMMENT '中间方设备标识',
  wxid         VARCHAR(64)  NOT NULL COMMENT '对方微信ID（个人或群ID）',
  chat_type    TINYINT      NOT NULL DEFAULT 1 COMMENT '1=单聊 2=群聊',
  name         VARCHAR(128) COMMENT '对方昵称/群名',
  unread_count INT          NOT NULL DEFAULT 0 COMMENT '未读数（业务端自建）',
  pinned       TINYINT      NOT NULL DEFAULT 0 COMMENT '是否置顶 0否 1是（业务端自建）',
  last_msg     TEXT         COMMENT '最后一条消息摘要（冗余，避免每次联表）',
  last_msg_at  DATETIME     COMMENT '最后一条消息时间',
  created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  deleted_at   DATETIME     NULL COMMENT '软删除：NULL=正常，非NULL=删除时间（不真删）',
  UNIQUE KEY uk_openid_wxid (openid, wxid),
  KEY idx_last_msg_at (last_msg_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='会话';
```

### 2. message 消息表

```sql
CREATE TABLE message (
  id              BIGINT AUTO_INCREMENT PRIMARY KEY,
  conversation_id BIGINT       NOT NULL COMMENT '所属会话',
  msg_type        TINYINT      NOT NULL COMMENT '1文本 2图片 3文件 4视频 5链接卡片（接口只有这5种）',
  direction       TINYINT      NOT NULL COMMENT '1=收到 2=发出',
  sender_wxid     VARCHAR(64)  COMMENT '发送者wxid（群聊里是群成员）',
  sender_name     VARCHAR(128) COMMENT '发送者昵称',
  content         TEXT         COMMENT '文本内容/文件名等',
  payload         JSON         COMMENT '其他字段原文（图片url、视频时长等）',
  middle_msg_id   VARCHAR(64)  COMMENT '中间方消息id（撤回要用）',
  new_msg_id      VARCHAR(64)  COMMENT '中间方new_msg_id（撤回要用）',
  create_time     DATETIME     NOT NULL COMMENT '消息时间（以中间方为准）',
  status          TINYINT      NOT NULL DEFAULT 0 COMMENT '0发送中 1已发送 2失败（只对发出的消息有效）',
  created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at      DATETIME     NULL COMMENT '软删除：NULL=正常，非NULL=删除时间（不真删）',
  KEY idx_conv_time (conversation_id, create_time),
  KEY idx_middle_msg (middle_msg_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='消息';
```

> 消息状态只有 发送中/已发送/失败 三种——中间方接口没有已读回执。

### 3. send_task 发送任务表

```sql
CREATE TABLE send_task (
  id              BIGINT AUTO_INCREMENT PRIMARY KEY,
  uuid            VARCHAR(64)  NOT NULL COMMENT '本次发送唯一标识（我们自己生成，中间方用它返回结果）',
  message_id      BIGINT       COMMENT '对应 message 表 id',
  api_path        VARCHAR(64)  NOT NULL COMMENT '调用的中间方接口，如 /wx_app/send_api',
  action          VARCHAR(32)  NOT NULL COMMENT 'post_text_message / post_image_message 等',
  request_payload JSON         COMMENT '发出去的完整参数（留底，方便排查）',
  status          TINYINT      NOT NULL DEFAULT 0 COMMENT '0待下发 1已下发 2成功 3失败',
  retry_count     INT          NOT NULL DEFAULT 0 COMMENT '确认重试次数',
  created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  deleted_at      DATETIME     NULL COMMENT '软删除：NULL=正常，非NULL=删除时间（不真删）',
  UNIQUE KEY uk_uuid (uuid),
  KEY idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='发送任务';
```

### 4. sync_cursor 轮询游标表

```sql
CREATE TABLE sync_cursor (
  id             BIGINT AUTO_INCREMENT PRIMARY KEY,
  openid         VARCHAR(64) NOT NULL COMMENT '中间方设备标识',
  cursor_type    VARCHAR(32) NOT NULL COMMENT '游标类型：msg=收消息，send=发送确认',
  last_sync_time DATETIME    NOT NULL COMMENT '上次同步到的时间点，下次从这个点往后拉',
  updated_at     DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  deleted_at     DATETIME    NULL COMMENT '软删除：NULL=正常，非NULL=删除时间（不真删）',
  UNIQUE KEY uk_openid_type (openid, cursor_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='轮询游标';
```

## 三、软删除规范（强制，违反即返工）

> 之前出问题就是这一条只写了一句口号、也没写新表怎么登记，最后 7 张新增表全漏了。
> 下面拆成“字段语义 / 三条硬规则 / 例外白名单 / 新增表清单”，逐条可对照代码检查。

### 3.1 字段语义（别混用）

| 字段 | 类型 | 含义 | 允许写的地方 |
|---|---|---|---|
| `deleted_at` | DATETIME NULL | **唯一的删除标记**：NULL=正常，有值=被删除的时间 | service / api 层，UI 不直接写 |
| `status` | SMALLINT | **业务状态**，不是删除标记 | 各业务逻辑 |
| `org_id` | BIGINT NULL | 组织归属，空=未分配；**不随组织停用清空** | 创建/编辑时 |
| `openid` | VARCHAR(64) | 设备唯一身份，录入后不可改 | 仅创建设备时 |
| `wxid` / `chatroom_wxid` | VARCHAR(64) | 微信侧身份键，与 openid 组成联合唯一 | 同步时 |

`status` 的取值按表各管各的，**绝不能用 `status` 判断“是否被删除”**：

- `user` / `org`：1=启用，0=停用（这就是它们的软删除，恢复=置回 1）
- `message`：0发送中 1已发送 2失败（发送状态，与删除无关）
- `send_task`：0待下发 1已下发 2成功 3失败

### 3.2 三条硬规则

1. **写：业务删除只写 `deleted_at = now()`**
   禁止 `db.session.delete(...)`、`Model.query.filter(...).delete()`、`TRUNCATE`。
2. **读：默认过滤 `deleted_at IS NULL`**
   列表、详情、统计、下拉、同步结果一律过滤；只有“回收站”显式查 `deleted_at IS NOT NULL`。
3. **恢复：`deleted_at = NULL`，原 id 与关联不变**
   唯一键冲突时**必须复活旧行**，不能 INSERT 新行：

```python
row = Device.query.filter_by(openid=openid).first()   # 注意：不加过滤，含已删除
if row:
    row.deleted_at = None      # 复活
else:
    db.session.add(Device(openid=openid, ...))
```

### 3.3 例外白名单（唯一允许物理删除的地方）

只有三张日志表可被物理删除，且**只能通过** `backend/services/retention.py` 的 `purge_expired()`：

| 表 | 保留期 | 说明 |
|---|---|---|
| access_log | 90 天 | 访问日志 |
| middle_call_log | 90 天 | 中间方调用日志 |
| audit_log | 180 天 | 审计日志 |

要求：保留期集中配置、清理动作本身写审计（防止“审计被自己删掉”无痕）。

### 3.4 新增表 / 新增删除接口的必检清单

新增任何表，或给已有表加删除功能时，逐条打勾，缺一不可：

- [ ] 表接入 `SoftDeleteMixin`（或书面说明为何用 `status` 代替，并写进上表）
- [ ] `db_migrate.py` 补 `deleted_at` 列（含索引）
- [ ] 所有读路径加 `deleted_at IS NULL`
- [ ] 删除接口写 `deleted_at`，并在 `audit_log` 留痕
- [ ] 补恢复路径（接口或“再写入即复活”），并验证 id 不变、不产生重复行
- [ ] 唯一键场景验证：删除后同键再写入能复活，不报冲突
- [ ] 第 1 节总览表同步登记，写清删除策略与恢复方式
- [ ] `python -m pytest tests/test_soft_delete_guard.py -q` 通过

最后一条是自动闸门：业务代码里出现 `session.delete` / `.delete()` 就会失败，只有白名单文件放行。

## 四、设计要点（大白话）

1. **conversation 用 openid + wxid 做唯一键**：一个设备对一个联系人/群只有一个会话，防止重复建会话
2. **message 的索引建在 (conversation_id, create_time)**：聊天窗口永远只按会话查消息，这是最高频的查询
3. **last_msg 冗余在会话表**：会话列表要显示"最后一条消息"，联 message 表太慢，直接存一份摘要
4. **send_task 留底 request_payload**：出问题能查到当时到底发了什么参数给中间方
5. **sync_cursor 记游标**：每台设备每个游标类型一行，轮询时"只拉上次之后的新消息"，不重复不遗漏
6. **删除规则见第三节**：业务数据只打标记、可恢复；唯一能真删的是过期日志

## 五、环境切换（测试库 / 生产库）

原理一句话：**`.env` 里放两套数据库地址 + 一个开关，程序启动时看开关选地址。**

```ini
# .env（不进 git）
APP_ENV = dev          # dev=测试库  prod=生产库，不填默认 dev
DEV_DATABASE_URL  = mysql+pymysql://user:pass@192.168.1.100/wx_app_dev?charset=utf8mb4
PROD_DATABASE_URL = mysql+pymysql://user:pass@生产库地址/wx_app?charset=utf8mb4
```

config.py 的选库逻辑（3 行核心）：

```python
env = os.getenv("APP_ENV", "dev")            # 不填 = dev，防手滑连生产
url_key = "PROD_DATABASE_URL" if env == "prod" else "DEV_DATABASE_URL"
DATABASE_URL = os.getenv(url_key)
```

规则：

- 本地开发一律 dev；`.env` 永远不进 git（.gitignore 已挡）
- 改 `APP_ENV` 后要重启服务才生效
- 生产库账号建议只给读写权限，不给删库权限
