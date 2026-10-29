# 数据库设计

数据库：MySQL，字符集统一 **utf8mb4**（要存微信表情 emoji，utf8 装不下）。

## 一、7 张表总览

| 表 | 干什么用 | 来源 |
|---|---|---|
| conversation | 会话列表（左栏） | 接口数据 + 业务端自建字段（未读/置顶） |
| message | 聊天记录（中栏） | 接口数据 |
| send_task | 发送任务（发给中间方的记录） | 业务端自建 |
| customer | 客户资料（电话/城市/标签/备注） | 业务端自建 |
| quote_order | 报价单（报价处理台的一行） | 业务端自建 |
| quote_item | 报价明细（车型/变速箱/零件号/价格） | 业务端自建 |
| sync_cursor | 轮询游标（记上次同步到哪了） | 业务端自建 |

## 二、建表语句

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

### 4. customer 客户资料表（业务端自建）

```sql
CREATE TABLE customer (
  id               BIGINT AUTO_INCREMENT PRIMARY KEY,
  conversation_id  BIGINT       NOT NULL COMMENT '关联会话',
  wxid             VARCHAR(64)  NOT NULL COMMENT '客户微信ID',
  phone            VARCHAR(32)  COMMENT '电话',
  city             VARCHAR(64)  COMMENT '城市',
  source           VARCHAR(64)  COMMENT '来源（怎么来的客户）',
  agent_name       VARCHAR(64)  COMMENT '负责客服',
  tags             JSON         COMMENT '标签列表',
  note             TEXT         COMMENT '备注',
  first_contact_at DATETIME     COMMENT '首次联系时间',
  created_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  deleted_at       DATETIME     NULL COMMENT '软删除：NULL=正常，非NULL=删除时间（不真删）',
  UNIQUE KEY uk_wxid (wxid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='客户资料（业务端自建）';
```

### 5. quote_order 报价单表（业务端自建）

```sql
CREATE TABLE quote_order (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  quote_no     VARCHAR(32)  NOT NULL COMMENT '报价单号',
  conversation_id BIGINT    COMMENT '关联会话（可从会话跳到客户）',
  status       TINYINT      NOT NULL DEFAULT 0 COMMENT '0待处理 1已报价 2已包邮',
  assignee     VARCHAR(64)  COMMENT '指派给谁（客服名）',
  remark       VARCHAR(255) COMMENT '备注',
  created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  deleted_at   DATETIME     NULL COMMENT '软删除：NULL=正常，非NULL=删除时间（不真删）',
  UNIQUE KEY uk_quote_no (quote_no),
  KEY idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='报价单（业务端自建）';
```

### 6. quote_item 报价明细表（业务端自建）

```sql
CREATE TABLE quote_item (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  quote_order_id BIGINT     NOT NULL COMMENT '所属报价单',
  car_model    VARCHAR(128) COMMENT '车型',
  gearbox      VARCHAR(64)  COMMENT '变速箱',
  part_no      VARCHAR(128) COMMENT '零件号',
  part_name    VARCHAR(255) COMMENT '零件名称',
  price        DECIMAL(10,2) COMMENT '报价',
  qty          INT          NOT NULL DEFAULT 1 COMMENT '数量',
  quoted       TINYINT      NOT NULL DEFAULT 0 COMMENT '是否已报价 0否 1是',
  created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at   DATETIME     NULL COMMENT '软删除：NULL=正常，非NULL=删除时间（不真删）',
  KEY idx_order (quote_order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='报价明细（业务端自建）';
```

### 7. sync_cursor 轮询游标表

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

## 三、设计要点（大白话）

1. **conversation 用 openid + wxid 做唯一键**：一个设备对一个联系人/群只有一个会话，防止重复建会话
2. **message 的索引建在 (conversation_id, create_time)**：聊天窗口永远只按会话查消息，这是最高频的查询
3. **last_msg 冗余在会话表**：会话列表要显示"最后一条消息"，联 message 表太慢，直接存一份摘要
4. **send_task 留底 request_payload**：出问题能查到当时到底发了什么参数给中间方
5. **quote_order / quote_item / customer 是业务端自建的**：中间方接口里完全没有这些概念，是我们自己加的"报价处理台"
6. **sync_cursor 记游标**：每台设备每个游标类型一行，轮询时"只拉上次之后的新消息"，不重复不遗漏
7. **删除一律软删除**：每张表都带 deleted_at（NULL=正常），删除只填删除时间、永不执行 DELETE，查询默认加 `WHERE deleted_at IS NULL`

## 四、环境切换（测试库 / 生产库）

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
