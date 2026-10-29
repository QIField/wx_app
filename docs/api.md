# 接口文档

分两部分：**业务端给前端的接口**（我们自己写）+ **中间方接口速查表**（别人给的，附录）。

---

# 第一部分：业务端 API（给前端用）

## 统一约定

- 前缀：`/api`
- 统一返回格式：

```json
{ "code": 0, "msg": "success", "data": {} }
```

- `code = 0` 表示成功，其他为错误码；`data` 里才是数据
- 请求体用 JSON

## 1. 会话

### GET /api/conversations — 会话列表（左栏）

参数：`page`、`page_size`、`pinned_first`（置顶是否靠前，默认是）

返回 data：

```json
{
  "list": [
    {
      "id": 1, "wxid": "wxid_abc", "chat_type": 1, "name": "张师傅",
      "unread_count": 2, "pinned": 0,
      "last_msg": "好的，收到", "last_msg_at": "2026-10-29 10:30:00"
    }
  ],
  "total": 42
}
```

### PATCH /api/conversations/{id} — 会话操作（置顶 / 清未读）

请求体：`{ "pinned": 1 }` 或 `{ "read": true }`（read=true 表示清零未读数）

## 2. 消息

### GET /api/conversations/{id}/messages — 聊天记录（中栏）

参数：`before_id`（翻页用，取这个 id 之前的消息）、`limit`（默认 50）

返回 data：

```json
{
  "list": [
    {
      "id": 1001, "msg_type": 1, "direction": 1,
      "sender_wxid": "wxid_abc", "sender_name": "张师傅",
      "content": "变速箱修好多钱",
      "payload": {}, "status": 1,
      "create_time": "2026-10-29 10:29:31"
    }
  ]
}
```

msg_type 对照：1文本 2图片 3文件 4视频 5链接卡片（中间方只有这 5 种）

### POST /api/conversations/{id}/messages — 发消息

请求体（按 msg_type 传对应字段，`content` 为空时需要传 `payload`）：

```json
{ "msg_type": 1, "content": "好的马上安排" }
{ "msg_type": 2, "payload": { "img_url": "https://..." } }
{ "msg_type": 3, "payload": { "file_url": "https://...", "file_name": "报价单.xlsx" } }
{ "msg_type": 4, "payload": { "video_url": "https://...", "thumb_url": "https://...", "video_duration": 15 } }
{ "msg_type": 5, "payload": { "title": "宝马320报价", "desc": "今日特价", "link_url": "https://...", "thumb_url": "https://..." } }
```

返回 data：`{ "message_id": 1002, "status": 0 }`（status=0 发送中，之后 WebSocket 推送结果）

### POST /api/messages/{id}/revoke — 撤回

后端用该消息的 middle_msg_id / new_msg_id / create_time 调中间方撤回接口。

## 3. WebSocket /ws — 实时推送

前端连接后，后端主动推三种事件：

| 事件 | 触发时机 | data |
|---|---|---|
| new_message | 轮询到新消息入库后 | `{ conversation_id, message: {...} }` |
| send_result | 发送确认成功/失败后 | `{ message_id, status: 1 或 2 }` |
| device_status | 设备在线状态变化时 | `{ openid, online: true/false }` |

## 4. 客户资料（业务端自建）

### GET /api/customers/{conversation_id} — 读客户资料

### PUT /api/customers/{conversation_id} — 保存客户资料

请求体：`{ "phone": "138xxxx", "city": "广州", "tags": ["宝马","老客户"], "note": "只修变速箱" }`

## 5. 报价处理台（业务端自建）

### GET /api/quotes/desk — 报价列表（右栏）

参数：`status`（0待处理 1已报价 2已包邮）、`assignee`（按指派人筛）、`sort`（时间排序）

返回 data：报价单列表，每条含明细行（车型、变速箱、零件号、价格、是否已报价）

### PATCH /api/quotes/{id} — 更新报价单

请求体：`{ "status": 1, "assignee": "杨洋" }`

## 6. 设备 / 通讯录（来自中间方）

### GET /api/device/status — 设备在线状态

### GET /api/contacts — 通讯录列表

---

# 第二部分（附录）：中间方接口速查表

> 开发适配器（backend/adapter/）时以这份表为准。
> 完整字段以《接口文档(2).txt》原文为准，此处是开发备忘。

## 统一规则

- 全部 **POST**，Content-Type：`application/x-www-form-urlencoded`
- 公共参数：`openid`（设备标识）、`uuid`（本次调用唯一标识）
- 带 `get_` 前缀的是结果查询接口（先 post 下发，再 get 查结果）
- 统一返回：`{"code": 0, "msg": "success"}`，查询接口多一个 `data` 字段

## send_api 发消息类（/wx_app/send_api）

| action | 参数 | 说明 |
|---|---|---|
| post_text_message | to_wxid, content, ats | 发文本，ats=群内@的人 |
| post_file_message | to_wxid, file_url, file_name | 发文件 |
| post_image_message | to_wxid, img_url | 发图片 |
| post_video_message | to_wxid, video_url, thumb_url, video_duration | 发视频 |
| post_link_message | to_wxid, title, desc, link_url, thumb_url | 发链接卡片（报价处理台发报价就用它） |
| revoke_message | to_wxid, msg_id, new_msg_id, create_time | 撤回 |

以上每个 post_xxx 都有对应 get_post_xxx 查询接口，用于确认发送结果。

## messag_api 收消息类（/wx_app/messag_api）

| action | 参数 | 说明 |
|---|---|---|
| get_message | openid（必填），from_wxid, to_wxid, start_create_time, end_create_time, page（默认1）, page_size（默认100） | 拉历史/新消息，轮询核心接口 |

## login_api 登录类

| action | 参数 | 说明 |
|---|---|---|
| check_online / get_check_online | - | 查设备是否在线 |
| logout / get_logout | - | 登出 |

## group_api 群类

| action | 参数 | 说明 |
|---|---|---|
| chatroom_info / get_chatroom_info | chatroom_id | 群信息 |
| chatroom_member_list / get_chatroom_member_list | chatroom_id | 群成员列表 |
| chatroom_member_detail / get_chatroom_member_detail | chatroom_id, member_wxids（逗号分隔） | 群成员详情 |

## contacts_api 通讯录类

| action | 参数 | 说明 |
|---|---|---|
| fetch_contacts_list / get_fetch_contacts_list | - | 拉通讯录 |
| fetch_contacts_list_cache / get_fetch_contacts_list_cache | - | 拉缓存版通讯录 |
| contact_detail_info / get_contact_detail_info | wxids（单次最多 20 个） | 联系人详情 |
| brief_info / get_brief_info | - | 简要信息 |
