# 消息转发：现状、保留资产与升级预案

> 维护场景：改动转发逻辑前先读「现状」；中间方加了原生卡片接口后照「升级预案」操作。
> 最后更新：2026-11-15（方案由「合并卡片+快照」切换为「逐条真实下发」，切换人：产品定稿）。

## 一、现状（活跃链路）

**转发 = 换个目标会话重新发消息。** 没有新消息形态、没有快照落库、没有方式确认弹窗。

```
右键气泡 → 转发 ┐
右键 → 多选 → 底栏「转发」（仅取消/转发，无删除）┘
        ↓
  ForwardPicker（最近转发置顶 + 昵称/全拼/首字母三路搜索，目标 ≤20）
        ↓ 确认
  POST /api/messages/forward  mode:"single"
        ↓
  services/forward.py::forward_single 逐条下发：
    - 文本(1)：原文直达，无「原发送者：」前缀（2026-11-15 产品定稿）
    - 图片(2)/视频(4)：payload 带 url 直接重发；没有 url（收到的消息）
      走 _rehost_media：媒体缓存取回文件 → 复制进 media/uploads/ → 挂可下载 URL 重发
    - 文件(3)/链接(5)：payload 带 url 才发
    - 语音/表情/引用/系统消息：跳过，计入 skipped（前端 toast 提示）
        ↓
  客户微信收到普通气泡；返回 {sent, failed, skipped}；广播 conv_updated 刷摘要
```

关键文件：

| 层 | 文件 | 说明 |
|---|---|---|
| 编排 | `backend/services/forward.py` | `forward_single` / `_redispatch_params` / `_rehost_media` / `_sender_display` |
| 接口 | `backend/api/messages.py` | `forward_messages_api`（归属校验：源/目标会话都必须在本账号绑定设备内） |
| 选择器 | `frontend/src/components/ForwardPicker.vue` | 拼音数据复用通讯录接口（contact 行带 pinyin_toks + conversation_id） |
| 编排 UI | `frontend/src/components/ChatPanel.vue`「多选与转发」段 | 多选状态、底栏、流程串联 |
| 卡片渲染 | `frontend/src/components/MessageRow.vue` msg_type=9 分支 | 历史合并卡片仍显示、可点开回看 |
| 回看弹窗 | `frontend/src/components/ForwardRecord.vue` | 拉 forward-snapshot 接口，显示头像+昵称 |
| 测试 | `backend/tests/test_api_forward.py` | 13 个用例，覆盖逐条与合并两条链路 |

## 二、保留资产（合并卡片方案，当前无前端入口）

2026-11-15 之前实现过完整的「合并转发」方案：目标会话落一张本地卡片（msg_type=9）+ 快照表。
后因**中间方没有微信原生「聊天记录」卡片（appmsg type 19）的发送接口**，卡片只在业务端可见、
真实微信收不到（当时用户反馈"显示已发送但微信没收到"即此根因），产品定稿切到逐条方案。

切换时遵循「**降级不拆除**」原则，以下资产全部保留且有测试守护：

| 资产 | 位置 | 状态 |
|---|---|---|
| 快照表（含 sender_avatar 列） | `backend/models/forward_snapshot.py`，db_migrate 自动补列 | 库表已存在，**只读遗留**（新转发不写入） |
| 合并落库编排 | `forward.py::forward_merge` + `broadcast_cards`（WS 按 message_id 幂等） | 函数完整可调 |
| 发送者冻结解析 | `forward.py::_sender_display`（群查 GroupMember 名册、单聊取会话资料） | 逐条方案的快照展示也复用它 |
| merge 接口 | `api/messages.py::forward_messages_api` 的 `mode:"merge"` 分支 | 在线可用（接口工具直调仍会出卡片） |
| 最近转发接口 | `GET /api/forwards/recent`（按操作人合并卡片去重） | 在线可用 |
| 卡片气泡 + 回看弹窗 | MessageRow.vue / ForwardRecord.vue | 已挂载，历史卡片可回看 |

**为什么保留快照表而不删**：①历史卡片回看依赖它；②它就是升级后拼原生 XML 的数据源（见下节第 3 步）；
③零写入零维护成本。哪天历史卡片也不需要了，可整体下线：快照表 + MessageRow 卡片分支 +
ForwardRecord.vue + merge 接口分支 + forwards/recent 接口，共 5 处。

## 三、升级预案（中间方提供原生卡片接口后）

前提：中间方 send_api 新增「合并转发卡片」发送能力（微信 appmsg type 19 / recordinfo XML）。

1. **适配层**（约 10 行）：`backend/adapter/sender.py` 加
   `post_record(to_wxid, xml, uuid=None, openid="")`，调中间方新 action；
   同时在 `sync/send_service.py::_DISPATCH` 讨论是否纳入常规 dispatch（卡片建议单独处理，见下）。
2. **编排层**：`forward.py::forward_merge` 落库快照后追加真实下发——用 `items`
   （发送者+内容+顺序，快照数据现成）拼 appmsg XML，逐目标调 `post_record`。
   失败处理与 `forward_single` 对齐（SendDispatchError → 计 failed）。
3. **前端**：重写 `ForwardModeDialog.vue`（约 60 行，git 历史或原型
   `prototypes/forward-favorite/` 可参照），ChatPanel 加回 `modeDlg` 编排，
   `onPickerConfirm` 改回「多选一律先弹方式确认，再按所选 mode 调接口」。
4. **测试**：给 forward_merge 的下发分支加 mock 用例；恢复原「合并/逐条」双链路用例。
5. **文档**：更新本文档「现状」、api.md 的 forward 词条、database.md 的 forward_snapshot 备注。

工作量估计：半天以内。**注意**：届时逐条方案不废弃——单条右键转发仍走 direct single
（微信同款：单条转发选完人直发），只有多选才弹方式确认。

## 四、已知限制与陷阱（改动前必读）

1. **媒体转发的 URL 可达性**：`_rehost_media` 拼的地址依赖 `.env PUBLIC_BASE_URL`
   （不配则用请求 Host）。中间方服务器必须能访问该地址才能下载图片/视频，与文件上传
   发送是同一条链路；部署在内外网隔离环境时转发媒体会失败（消息计 skipped）。
2. **sender_name 存的是 wxid 原文**（中间方不提供昵称）：任何要展示发送者的地方都必须经
   `_sender_display` / GroupMember 名册解析，直接透传会露 wxid（脱敏契约）。
3. **msg_type=9 是"只发不收"**：`send_message` 的 `_VALID_TYPES` 不含 9，正常发送接口
   造不出卡片；卡片只可能来自 merge 接口。前端 `isSystemXml` 等文本判定对 9 不生效，无影响。
4. **转发去重靠 msgKey**：WS 广播的卡片按 message_id 幂等；`forwards/recent` 用
   `operator_id == user.id` 过滤，换账号登录看不到别人的转发记录（刻意设计）。
5. **限流档位**：`/api/messages/forward` 命中 risk.py 的 `/messages` 档（60 次/分钟），
   多选大批量转发时前端一次请求带全部 target，不要拆成循环调用。
