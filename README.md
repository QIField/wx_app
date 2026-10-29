# 微信客服聊天系统

客服用的聊天工作台：客服在网页上收发微信消息，后台自动同步、保存、推送。

## 一、整体架构

```
微信（客户手机）
    ↕  消息
中间方（别人家的服务，给我们 HTTP 接口）
    ↕  HTTP 接口（全部 POST + x-www-form-urlencoded）
业务端（本项目）
    ├── 后端 Flask + MySQL：调接口、存消息、推新消息
    └── 前端 Vue3 + Element Plus：客服聊天的三栏工作台
```

## 二、消息怎么收（轮询方案）

1. 后端定时器（APScheduler）每隔几秒调中间方的 `get_message`，带上上次同步到的时间（游标），增量拉新消息
2. 新消息解析后存进 MySQL
3. 存完通过 WebSocket（flask-sock）推给前端，前端聊天窗口实时刷新

## 三、消息怎么发（下发 + 确认）

1. 客服在前端点发送 → 请求业务端 API
2. 业务端先生成本地发送任务（带唯一 uuid），状态=待下发，消息状态=发送中
3. 调中间方 `post_text_message` 等接口下发
4. 之后用对应的 `get_post_xxx` 接口轮询确认发送结果
5. 成功 → 消息状态改为已发送；失败 → 改为失败

> 注意：中间方接口只能确认"发送成功/失败"，**没有已读回执**，前端不显示"已读"。

## 四、哪些数据来自接口，哪些是自己建的

| 数据 | 来源 |
|---|---|
| 会话列表、聊天记录、发消息 | 中间方接口（只是搬运和保存） |
| 在线状态、群信息、通讯录 | 中间方接口 |
| 报价处理台、客户电话/城市/标签/备注、未读数、置顶 | **业务端自建**（存自己的 MySQL，接口里没有） |

## 五、目录结构（规划）

```
wx_app/
├── backend/
│   ├── app.py            # 入口：启动 Flask、定时器、WebSocket
│   ├── config.py         # 配置：读 .env，按 APP_ENV 选数据库
│   ├── adapter/          # 中间方接口适配器：所有对中间方的调用只写在这里
│   ├── sync/             # 收消息轮询、发送结果确认
│   ├── api/              # 业务 API：给前端调用的接口
│   ├── ws/               # WebSocket 推送
│   ├── models/           # 数据库表定义
│   └── tests/            # 单元测试（核心业务必须写）
├── frontend/             # Vue3 + Element Plus + Pinia
├── docs/
│   ├── database.md       # 数据库设计
│   └── api.md            # 接口文档 + 中间方接口速查表
├── .env                  # 本地密钥配置（不进 git）
├── .env.example          # 配置模板（进 git）
└── requirements.txt      # Python 依赖
```

## 六、启动步骤（后端）

```powershell
# 1. 首次：安装依赖
pip install -r requirements.txt

# 2. 复制配置模板，填上自己的数据库和中间方密钥
copy .env.example .env

# 3. 启动
python backend/app.py
```

VS Code 里打开终端会自动激活虚拟环境（已配置好，见 `.vscode/settings.json`）。

## 七、测试库 / 生产库怎么切换

在 `.env` 文件里改一个开关即可，**改完重启服务**：

```ini
APP_ENV = dev          # dev=测试库，prod=生产库
DEV_DATABASE_URL  = mysql+pymysql://用户:密码@测试库地址/库名?charset=utf8mb4
PROD_DATABASE_URL = mysql+pymysql://用户:密码@生产库地址/库名?charset=utf8mb4
```

- 程序按 `APP_ENV` 的值自动选对应的库
- **`APP_ENV` 不填时默认 dev**，防止手滑连上生产库
- `.env` 不进 git，模板 `.env.example` 进 git
- 详细设计见 [docs/database.md](docs/database.md)

## 八、开发规范（摘要）

- 没画完流程图不写业务代码
- 一个文件一个职责，超 400 行拆分；函数超 80 行考虑拆分
- 每 2-3 个功能做一次重构；核心业务必须写单测
- 删除一律软删除（deleted_at 标记），不执行真删除，详见 [docs/database.md](docs/database.md)
- 提交规范：`feat:` 新功能 / `fix:` 修 Bug / `refactor:` 重构（重构必须单独提交）
