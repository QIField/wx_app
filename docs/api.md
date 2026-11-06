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

### POST /api/conversations — 主动发起会话

按 wxid 建/取会话（联系人须在该设备通讯录里）。请求体：

```json
{ "wxid": "wxid_abc", "chat_type": 1 }
```

返回 data：会话对象（同会话列表元素）；已有会话直接返回不重复建。
错误：`404` 通讯录中没有该联系人；`400` 参数缺失/非法。

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

msg_type 对照：1文本 2图片 3文件 4视频 5链接卡片 6语音 7表情（业务端自定编码；中间方微信原始编码 1文本 / 3图片 / 34语音 / 43视频 / 47表情 / 49链接卡片，由收消息同步层 message_sync.py 统一转换。语音/表情只收不发）

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

### POST /api/uploads — 上传文件（发图片/文件/视频的前置）

multipart 字段 `file`，任意类型，默认上限 50MB。登录鉴权。

返回 data：`{ "url": "http(s)://域名/media/uploads/<uuid>.png", "path": "/media/uploads/<uuid>.png", "file_name": "报价单.xlsx", "size": 1024 }`

- `url` 绝对地址，随 msg_type 2/3/4 的 payload 给中间方下载（域名取 .env `PUBLIC_BASE_URL`，不配则用请求地址）
- `path` 相对路径，前端本地气泡预览用
- `GET /media/uploads/<name>` 无需登录（中间方服务器要直接拉），uuid 文件名不可猜测

### POST /api/messages/{id}/revoke — 撤回

后端用该消息的 middle_msg_id / new_msg_id / create_time 调中间方撤回接口。

### GET /api/messages/{id}/media — 拉媒体文件（图片/文件/视频/语音/表情）

- `<img>/<audio>/<video>` 带不了 Authorization 头，允许 `?token=` 传登录令牌兜底
- 图片支持 `?img_type=`：1高清 / 2常规（默认）/ 3缩略图
- 后端先查本地缓存（backend/media/，可用 .env MEDIA_DIR 改路径），未命中调中间方 V2 下载接口：POST 拿 CDN 预签名地址（fileUrl / url，见附录实测记录）→ GET 拉回文件字节，按魔数判断真实类型落盘后回文件流
- 语音/表情/图片/视频参数来自消息入库时的 content xml；表情按 xml 里的 md5 属性
- 演示模式返回占位字节，没有中间方也能调通前端

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

参数：`type=friends|groups`、`keyword`（匹配昵称 / wxid / 业务备注）

数据源：contact 表（contact_sync 全量同步入库，没聊过天的联系人也在）
∪ 历史会话补集；返回条目含 `conversation_id`（无会话为 null）、
未读/摘要/置顶（有会话时）。

同步链路：`contact_sync` 挂在 sync_profiles 兜底轮（30 分钟）——
fetch_contacts_list_cache 拉全量 wxid（好友+群，公众号跳过）→ 缺的插入
contact 表 → 缺资料好友批量 brief_info（20/批，每轮最多 10 批）、
缺资料群逐个 chatroom_info。

---

# 第二部分（附录）：中间方接口速查表

> 开发适配器（backend/adapter/）时以这份表为准。
> 完整字段以《接口文档V2》原文为准，此处是开发备忘。

## 联调实测记录（2026-10-31 全接口真实联调）

> 以下为对中间方生产环境逐接口实测的结果，与《接口文档V2》不同处**以实测为准**。
> 除 logout（破坏性：会踢设备下线需扫码重登）外，全部接口已真实调用验证。

### 公共结构（实测）

- 三段式 URL：`https://域名/wx_app/{模块}/{方法}`，全部 POST + form-urlencoded
- 下发接口返回只有 `{"code":0,"msg":"success"}`（无 data）
- 查询接口（get_ 前缀）返回 `{"code":0,"msg":"success","data":[...]}`：
  - `data` 是**任务记录数组**（V2 文档写的 `data:{}` 不准确）
  - 元素：`{create_time, id, openid, processing_result, uuid, [processing_result_date], [回显的请求参数...]}`
  - `processing_result` 是 **JSON 字符串**：`{"ret":200,"msg":"操作成功","data":<业务结果>}`，业务端需二次 `json.loads`
  - 任务未完成时为"处理中"类文案；该 uuid 无记录时 `data: []`
  - `create_time` / `processing_result_date` 为 RFC 1123 GMT（`Sat, 31 Oct 2026 10:41:05 GMT`）
- 业务结果字段普遍是**驼峰**（toWxid / newMsgId / memberList ...），不是下划线风格

### login_api

| 接口 | 实测 processing_result.data |
|---|---|
| get_check_online | `true`（在线）/ `false` |
| get_logout | 未实测（破坏性，跳过） |

### messag_api / get_message

`processing_result.data`：

```json
{
  "list": [
    {
      "id": 8231,
      "msg_id": "66328446",
      "msg_type": "51",
      "from_wxid": "wxid_yfm4es06qpzt22",
      "to_wxid": "wxid_1815ubzp53ft12",
      "content": "文本 或 <?xml ...>",
      "raw_json": "{\"TypeName\":\"AddMsg\",... 回调原文 ...}",
      "app_id": "wx_DLcv5wC1xSL52e0Bf6c8o",
      "create_time": "Thu, 29 Oct 2026 09:09:33 GMT"
    }
  ]
}
```

实测注意：

- `msg_type` / `msg_id` 是**字符串**不是 int，判断前须转 int
- 群消息 `content` 带 `发送者wxid:\n` 前缀，私聊无前缀；NewMsgId 在 `raw_json.Data.NewMsgId`
- 过滤参数实测生效：from_wxid / to_wxid / start_create_time / end_create_time（`2026-10-31 00:00:00` 格式）/ page / page_size
- `msg_type` 参数文档未列，实测疑似生效（不要依赖）
- send_api 发出的消息**不进** get_message 库（实测查不到刚发出的消息）

### messag_api / 下载接口（与文档差异大，重点）

实测返回**不是文件字节**，而是 JSON 里带 CDN 地址，需二次 GET：

```json
{"code": 0, "data": {"ret": 200, "msg": "操作成功", "data": {"fileUrl": "https://wxapii.oos-sccd.ctyunapi.cn/..."}}}
```

| 接口 | 文件地址字段 | 实测 CDN |
|---|---|---|
| get_download_image / voice / video / file | `data.data.fileUrl` | 天翼云 OOS 预签名 URL（`wxapii.oos-sccd.ctyunapi.cn`，Expires ≈ 7 天） |
| get_download_emoji | `data.data.url`（**字段名不同**） | 腾讯 CDN（`vweixinf.tc.qq.com`） |

拿到地址后普通 GET 即得文件字节。实测文件特征：

| 类型 | 魔数/实际格式 | 说明 |
|---|---|---|
| 图片 | `ffd8ffe0` JPEG | URL 扩展名（.png）不可信 |
| 语音 | `#!SILK_V3` | silk 格式（voiceformat=4），浏览器 `<audio>` 不能直接播，需转码（如 ffmpeg → mp3） |
| 视频 | `ftyp` mp4 | - |
| 表情 | JPEG | - |

- 下载响应 HTTP Content-Type 全为 `application/octet-stream`（实测还拼错为 "octst-stream"），**完全不可信**，须按魔数判断
- `img_type` 传 1/2/3 实测返回**同一个 URL**（中间方侧缓存），高清/缩略图实际无效

### send_api（发送目标 wxid_1815ubzp53ft12 实测）

发送结果 `processing_result.data` 实测：

| 接口 | 实测 data 字段 |
|---|---|
| post_text_message | `{toWxid, createTime(unix秒), msgId: 0, newMsgId, type: 1}` — 文字 **msgId 恒为 0** |
| post_link_message | `{toWxid, createTime, msgId, newMsgId, type: 5}` |
| post_image_message | `{toWxid, createTime, msgId, newMsgId, type: null, aesKey, fileId, cdnThumbUrl, length, cdnThumbLength, width, height, md5}` |
| post_video_message | `{toWxid, createTime: null, msgId, newMsgId, type: null, aesKey, fileId, length, playlength: null, cdnthumblength(全小写), width, height, cdnThumbUrl}` |
| post_file_message | `{toWxid, createTime, msgId, newMsgId, type: 6, cdnAttachUrl, aesKey, title}` |

- 查询返回 `data: []` 空数组 = 任务仍在处理，继续轮询
- 任务记录会回显请求参数（content / to_wxid / img_url / video_url / file_name 等）
- post_file_message 的 `file_url` 必须中间方服务器可达：GitHub raw 实测超时 `ret:-1 "请求超时"`，国内 URL 成功

### revoke_message 撤回（实测）

- 参数：to_wxid, msg_id, new_msg_id, create_time
- 文字消息发送结果 msgId=0，实测传 `msg_id="0"` + `new_msg_id` + `create_time`（unix 秒字符串）即可成功撤回
- `processing_result` 只有 `{"ret":200,"msg":"操作成功"}`，**无 data**
- 该查询任务记录字段与其余模块不同：`create_date` + `create_time`（字符串 `"1793414601"`，回显参数）+ `msg_id` + `new_msg_id` + `to_wxid`

### contacts_api（实测）

fetch_contacts_list / fetch_contacts_list_cache：

```json
{"friends": ["wxid_xxx", "...约300个"], "chatrooms": ["57636827476@chatroom", "..."], "ghs": ["gh_xxx", "..."]}
```

- friends / chatrooms / ghs 都是**纯字符串数组**（不是对象数组），两接口结果一致

brief_info / contact_detail_info（wxids 逗号分隔）返回联系人信息数组，元素（camelCase）：

```json
{
  "userName": "medianote", "nickName": "语音记事本",
  "pyInitial": "YYJSB", "quanPin": "yuyinjishiben", "sex": 0,
  "remark": "", "remarkPyInitial": "", "remarkQuanPin": "",
  "signature": "", "alias": "", "snsBgImg": null,
  "country": "", "bigHeadImgUrl": "https://wx.qlogo.cn/...",
  "smallHeadImgUrl": "https://wx.qlogo.cn/.../132",
  "description": null, "cardImgUrl": null, "labelList": null,
  "province": "", "city": "", "v3": null, "phoneNumList": null,
  "top": false, "silence": false, "addSource": null, "addTime": 1595143941
}
```

- contact_detail_info 结构相同，但 remark / signature / province 等常为 null，且 `v3` 有值（`v3_...@stranger`）
- 头像：bigHeadImgUrl 尾 `/0`，smallHeadImgUrl 尾 `/132`

### group_api（实测，群样本 57636827476@chatroom）

chatroom_info → `processing_result.data`：

```json
{
  "chatroomId": "57636827476@chatroom", "nickName": "业务异常自动通知群",
  "pyInitial": "...", "quanPin": "...", "sex": 0,
  "remark": null, "remarkPyInitial": null, "remarkQuanPin": null,
  "chatRoomNotify": 0, "top": true, "silence": true,
  "chatRoomOwner": "wxid_vnethznh1sqm22",
  "smallHeadImgUrl": "https://wx.qlogo.cn/mmcrhead/...",
  "memberList": [
    {"wxid": "zhangrui758", "nickName": "张锐", "inviterUserName": "wxid_vnethznh1sqm22",
     "memberFlag": 1, "displayName": null, "bigHeadImgUrl": null, "smallHeadImgUrl": null}
  ]
}
```

- chatroom_member_list → `{"memberList": [成员结构同上，头像通常有值]}`
- chatroom_member_detail（chatroom_id + member_wxids 逗号分隔）→ 联系人详情数组，除 brief 字段外多出 `friendUserName` / `inviterUserName` / `memberFlag` / `chatRoomNotify` / `labelList`
- 任务记录会回显 chatroom_id / member_wxids

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
| revoke_message | to_wxid, msg_id, new_msg_id, create_time | 撤回；实测文字消息 msg_id 传 "0"，靠 new_msg_id 定位 |

以上每个 post_xxx 都有对应 get_post_xxx 查询接口，用于确认发送结果。

## messag_api 消息查询类（/wx_app/messag_api）

| action | 参数 | 说明 |
|---|---|---|
| get_message | openid（必填），from_wxid（发送人，可选），to_wxid（接收人，可选），start_create_time, end_create_time, page（默认1）, page_size（默认100） | 拉历史/新消息，轮询核心接口；openid 为空直接返回空数组 |
| get_download_file | openid, xml | 下载文件 |
| get_download_image | openid, xml, img_type | 下载图片，img_type：1高清 2常规 3缩略图，默认 2 |
| get_download_voice | openid, xml, msg_id | 下载语音，msg_id 为回调消息中的 msgId |
| get_download_video | openid, xml | 下载视频 |
| get_download_emoji | openid, emoji_md5 | 下载表情 |

参数说明：

- `xml`：回调消息中对应资源的 xml 内容
- `emoji_md5`：emoji 图片的 md5 值
- download 系列**参数无 uuid**，不走「下发 → 查询」两步，直接传参取结果（V2 新增）
- download 系列实测返回 **JSON + CDN 地址**：image/voice/video/file 取 `data.data.fileUrl`，emoji 取 `data.data.url`，需再 GET 该地址拿文件字节；详见上方「联调实测记录」

## login_api 登录类（/wx_app/login_api）

| action | 参数 | 说明 |
|---|---|---|
| check_online / get_check_online | openid, uuid | 查设备是否在线 |
| logout / get_logout | openid, uuid | 登出 |

## group_api 群类（/wx_app/group_api）

| action | 参数 | 说明 |
|---|---|---|
| chatroom_info / get_chatroom_info | chatroom_id | 群信息 |
| chatroom_member_list / get_chatroom_member_list | chatroom_id | 群成员列表 |
| chatroom_member_detail / get_chatroom_member_detail | chatroom_id, member_wxids（逗号分隔） | 群成员详情 |

## contacts_api 通讯录类（/wx_app/contacts_api）

| action | 参数 | 说明 |
|---|---|---|
| fetch_contacts_list / get_fetch_contacts_list | - | 拉通讯录（好友、已保存群、公众号） |
| fetch_contacts_list_cache / get_fetch_contacts_list_cache | - | 拉缓存版通讯录 |
| contact_detail_info / get_contact_detail_info | wxids（逗号分隔，单次最多 20 个） | 联系人详情 |
| brief_info / get_brief_info | wxids（逗号分隔，单次最多 20 个） | 简要信息（get_ 查询只传 openid+uuid） |
