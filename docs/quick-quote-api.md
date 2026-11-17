# 快捷报价接口文档

外部服务对接文档：快捷报价服务（询价要素提取 / VIN·配件译码 / OCR 识别 / 平台比价），
共 **5 个模块 11 个接口**，全部已于 2026-11-16 ~ 11-17 实测验证。

- 原始文档照录存档：[quick-quote-api-original.md](quick-quote-api-original.md)（2026-11-16 原文）
- 实测过程与原始返回记录：[quick-quote-api-test.md](quick-quote-api-test.md)
- 本文档在原文基础上补充：部署地址、鉴权行为、参数实测语义、响应字段类型、真实示例、已知问题

---

## 统一约定

| 项 | 约定 | 备注 |
| ---- | ---- | ---- |
| 基址 | `http://wx_api.fsbbr.net/wechat_x/` | 实测确认；原文档未注明部署地址 |
| 请求方式 | 全部 `POST` | - |
| 传参类型 | form / `application/x-www-form-urlencoded` | **不支持 JSON body**（原备注 1） |
| 返回类型 | JSON | - |
| 鉴权 | `openid` 必填 | 服务方签发的专用 id，**独立注册表**，与中间方设备 openid 不通用 |
| HTTPS | 证书 hostname 不匹配 | 当前仅 HTTP 可用，如需 HTTPS 由服务方修正证书 |

统一返回：

```json
{ "code": 0, "data": [], "msg": "success" }
```

| 字段 | 类型 | 说明 |
| ---- | ---- | ---- |
| code | int | `0` 成功；实测存在 `401`（鉴权失败） |
| data | 按接口不同 | 业务数据；实测有 **list / dict / str** 三种形态，逐接口标注 |
| msg | string | 提示文字 |

实际错误行为（与原文档差异，以实测为准）：

| 场景 | HTTP | 返回 |
| ---- | ---- | ---- |
| 缺少 openid 参数 | 401 | `{"code":401,"msg":"缺少openid"}` |
| openid 未注册 / 已关闭 | 401 | `{"code":401,"msg":"openid不存在或已关闭"}` |
| 服务上游异常 | 500 | Flask HTML 错误页（**非 JSON**）——调用方必须整体 try/except 兜底 |

> 原备注 2：表格中标注必填的参数才有非空判断，其余参数直接透传给 service 层。
> 原备注 3：统一返回 code=0，无业务错误码分支（实测补充：鉴权层有 401 分支）。

## 接口总表

| 模块 | 接口地址 | 接口名称 | 请求参数 | 校验规则（原文） |
| ---- | ---- | ---- | ---- | ---- |
| crm_api | /wechat_x/crm_api/product_list | 产品列表 | openid、number | openid、number 必填，任一为空返回空data |
| crm_api | /wechat_x/crm_api/purchaseHistory_list | 采购历史 | openid、number、page、limit | openid、number 必填，任一为空返回空data |
| ai_api | /wechat_x/ai_api/extract_parts_demand | 聊天提取配件需求 | openid、chat_content | openid、chat_content 必填，任一为空返回空data；chat_content为JSON字符串 |
| decoding_api | /wechat_x/decoding_api/vininfo | VIN解析信息 | openid、vin | openid、vin 必填，任一为空返回空data |
| decoding_api | /wechat_x/decoding_api/partno | OE译码查询 | openid、vin、originalPartsNos | 无校验 |
| decoding_api | /wechat_x/decoding_api/partImages | 单个OE爆炸图 | openid、vin、oeCode | 无校验 |
| decoding_api | /wechat_x/decoding_api/partImages_list | 爆炸图+周边配件图 | openid、vin、imageIds、oeCode、carBrandId | 无校验 |
| ocr_api | /wechat_x/ocr_api/local_vin | 本地OCR识别VIN | openid、image_url | openid、image_url 必填，任一为空返回空data |
| ocr_api | /wechat_x/ocr_api/tx_vin | 腾讯云OCR识别VIN | openid、image_url | openid、image_url 必填，任一为空返回空data |
| platform_api | /wechat_x/platform_api/jqr | 机汽人平台查询 | openid、number | openid、number 必填，任一为空返回空data |
| platform_api | /wechat_x/platform_api/zpy | 兆配云平台查询 | openid、number | openid、number 必填，任一为空返回空data |

## 编号体系与归一化（通用业务规则，实测）

- `number` 类参数接受**三种编号**检索：OE 件号（`1665000075`）、store 号（`A` + OE，如
  `A1665000075`）、PARTENT 号（菲尔内部号，如 `724500401`）。
- **OE 归一化**：服务侧匹配时剥离前缀字母（`A0005400017` 按 `0005400017` 匹配），
  部分返回（译码/zpy）反而补 `A` 前缀输出。**我方传参前不必自行清洗 OE**。
- `jqr` / `zpy` 为全网比价：按任意 OE 返回全量第三方报价，无「档案不存在」概念。

---

## 1. crm_api（客户与产品）

### POST /wechat_x/crm_api/product_list — 产品列表

按编号查询本服务产品库档案（含品牌比价 child）。

请求参数（form）：

| 参数 | 类型 | 必填 | 说明 |
| ---- | ---- | ---- | ---- |
| openid | string | 是 | 服务方签发 |
| number | string | 是 | OE / store 号（`A+OE`）/ PARTENT 号均可 |

返回 `data`（dict）：

| 字段 | 类型 | 说明 |
| ---- | ---- | ---- |
| total / per_page / current_page | int / **str** / int | 分页信息；`per_page` 实测为字符串 |
| data.data | list | 产品行；`per_page` 默认 10，实测上限未知 |
| data.no_exist_oe | list | 未命中编号回显（如 `["0005400017"]`，前缀字母已剥离） |

`list` 条目主要字段（完整 40+ 字段原始 JSON 见测试报告 §4.6）：

| 字段 | 类型 | 说明 / 实测样例 |
| ---- | ---- | ---- |
| product_id | int | `91327` |
| store_number | string | `A1665000075`（store 号 = `A` + OE） |
| partent_number | string | `724500401`（PARTENT 号） |
| display_number | object | `{"key":"OE","value":"1665000075"}` 命中编号回显 |
| product_name | string | 上水管 |
| brand_id | int | **配件品牌** id：`1`=菲尔(FREY) / `79`=原厂 / `43`=盖茨（非车品牌） |
| cost_price | string | `"69.00"` 我方采购价 |
| store_price | string | `"628.14"` 4S 对照价 |
| auto_quote | list[str] | `["1280","91327","32464"]`，语义**待服务方说明**（91327=product_id） |
| child | list | 按配件品牌拆分的多行报价（同一 OE 菲尔 69.00 / 原厂 260.00 / 盖茨 109.00） |

请求示例：`openid=…&number=1665000075`

### POST /wechat_x/crm_api/purchaseHistory_list — 采购历史

按 OE 查询历史采购记录与汇总。

请求参数（form）：

| 参数 | 类型 | 必填 | 说明 |
| ---- | ---- | ---- | ---- |
| openid | string | 是 | - |
| number | string | 是 | **OE**（用户已确认） |
| page | int | 否 | 默认 1（未传按 1 处理） |
| limit | int | 否 | 默认 10（实测回显 `per_page:"10"`） |

返回 `data`（dict，**三层嵌套**，2026-11-17 实测纠正）：

```json
{ "code": 0, "msg": "success",
  "data": { "status": 200, "msg": "返回成功",
    "data": { "total": { "purchase_quantity": "129", "totalprice": "17415.54" },
              "list": { "current_page": "2", "data": [ ... ], "last_page": 17, "per_page": "5", "total": 81 } } } }
```

| 字段（路径） | 类型 | 说明 |
| ---- | ---- | ---- |
| data.status / data.msg | int / str | 内层状态：`200` / `返回成功` |
| data.data.total | object | **全量采购汇总**（不分页）：`{"purchase_quantity":"129","totalprice":"17415.54"}`，数字字段为字符串 |
| data.data.list.current_page / per_page | **str** | 分页信息（字符串） |
| data.data.list.total / last_page | int | 总条数（81）/ 总页数 |
| data.data.list.data | list | 订单行（约 69 字段） |

订单行主要字段：`order_no`（`CGRK002202608160060` 采购入库单号）、`number` / `search_number`
（OE）、`frey_no`（PARTENT 号）、`l_name_zh_default`（上水管）、`l_model_zh`（`276/166` 车型）、
`brand`（菲尔）、`fullname`（广东菲尔）、`company_name`（佛山市巴博瑞汽车零配件有限公司 供应商）、
`name`（经手人）、`price` / `amount_money` / `unit_cost` / `standard_price`、`purchase_quantity` /
`received_quantity`、`unit`、`warehouse`、`payment_method` / `payment_description`（月结）、
`create_date` / `expected_delivery_date` / `delivery_date`、`is_tax` / `is_shipping_fee` /
`is_packing_fee` / `exchange_rate` 等。完整原始 JSON 见测试报告 §4.2。

⚠️ 注意：

- `create_date`、`expected_delivery_date` 是 **Unix 时间戳字符串**（如 `1786873575`），
  前端展示需格式化。
- **间歇故障（已于 2026-11-17 服务方修复）**：修复前同参数连打结果漂移、偶发 HTTP 500；
  修复后同参数 6/6 连测全部稳定。稳健起见对接仍建议保留重试 + 空值容错。

请求示例：`openid=…&number=1665000075&page=1&limit=10`

---

## 2. ai_api（AI 要素提取）

### POST /wechat_x/ai_api/extract_parts_demand — 聊天提取配件需求

从聊天记录中提取询价要素（VIN / 配件名 / OE / 数量 / 是否跟进 / 是否已回复），
并按「询价人」归并会话。

请求参数（form）：

| 参数 | 类型 | 必填 | 说明 |
| ---- | ---- | ---- | ---- |
| openid | string | 是 | - |
| chat_content | string(JSON) | 是 | 消息数组 JSON 字符串，作为**一个表单字段值**传递（URL 编码） |

`chat_content` 消息结构支持 5 种 type（完整原文示例见附录 A）：

| type | 字段 | 说明 |
| ---- | ---- | ---- |
| input_text | text | 文本消息（`时间【昵称】：内容` 格式） |
| input_image | image_url | 图片消息，需紧跟一条「系统备注」文本说明发送人 |
| input_audio | audio_url | 音频消息（同上） |
| input_file | file_url | 文件消息（同上） |
| input_video | video_url | 视频消息（同上） |

返回 `data`（list，每条对应一个询价场景）：

| 字段 | 类型 | 说明（原文照录） |
| ---- | ---- | ---- |
| sender_name | string | 询价人昵称 |
| vin | string/null | 车架号，17 位车辆识别码，原文无则为 null |
| quoted | bool | 是否为跟进询价/二次议价；true=跟进旧报价，false=全新询价 |
| part_name | string | 配件名称，多个配件使用换行符 `\n` 分隔 |
| oem_no | string/null | 配件 OEM 零件号，和 part_name 一一对应换行，无件号则 null |
| inquiry_time | string | 客户这条询价第一条消息的时间 |
| inquiry_content | string | 客户询价原文，合并该客户全部询价内容 |
| is_replied | bool | 客服是否回复该询价；true 有回复，false 无回复 |
| first_reply_time | string/null | 客服第一条回复的时间，无回复为 null |
| reply_content | string/null | 客服回复内容，多条序号拼接，无回复为 null |

实测行为：多条消息按询价人正确归并（4 条消息 → 3 条询价）；图片/音频条目配合
「系统备注」文本可正确归属发送人；多配件 `\n` 分隔、多条回复序号拼接均与文档一致。
（图片/音频/视频条目的**端到端识别**联调期补测，见附录 B。）

请求示例（纯文本 3 条，URL 编码前）：

```
chat_content=[{"type":"input_text","text":"2026-11-16 10:10:12【老王】：W1NFB4KB9MA569173，右前减震一支，不限品质"},{"type":"input_text","text":"2026-11-16 10:15:12【马斯克】：885625662火花塞多少钱"},{"type":"input_text","text":"2026-11-16 10:20:12【黄晓明】：油底壳 节温器"}]
```

---

## 3. decoding_api（译码与爆炸图）

### POST /wechat_x/decoding_api/vininfo — VIN 解析信息

请求参数（form）：

| 参数 | 类型 | 必填 | 说明 |
| ---- | ---- | ---- | ---- |
| openid | string | 是 | - |
| vin | string | 是 | 17 位车架码；**不含字母 I/O/Q**，发送前建议本地格式校验 |

返回 `data`（list，单元素数组）：

| 字段 | 类型 | 说明 / 实测样例 |
| ---- | ---- | ---- |
| carBrandCode | string | 品牌码：`"BENZ"` / `"BMW"`（**partImages_list 的 carBrandId 取此值**） |
| carBrandName | string | 奔驰 / 宝马 |
| 其余 | - | 车型/年款/排量等档案字段，完整原始 JSON 见测试报告 §4.5 |

行为（实测）：

- 命中：`WBAWX3100G0L69597` → 进口宝马 X3 20iX / xDrive20i 2016 2.0T。
- 未命中 / 非法 VIN：HTTP 200 + `data` 空（按「查无此车」处理，**不重试**）。
- 个别脏数据 VIN 字符串会触发 HTTP 500（见附录 B）——对接做兜底 catch。

### POST /wechat_x/decoding_api/partno — OE 译码查询

按 VIN + 编号/名称译出标准件信息。**实测核心用法：`originalPartsNos` 可传配件名称**
（如 `节温器`），实现「VIN+名称 → 标准 OE」——AI 报价链路核心（extract 的 part_name → partno）。

请求参数（form）：

| 参数 | 类型 | 必填 | 说明 |
| ---- | ---- | ---- | ---- |
| openid | string | 是 | - |
| vin | string | 是 | 车型上下文 |
| originalPartsNos | string | 是 | OE 件号或**配件名称**；多值逗号分隔（逐 OE 返回一条对象） |

返回 `data`（dict；多值时逐条）：

| 字段 | 类型 | 说明 / 实测样例 |
| ---- | ---- | ---- |
| partsNo | string | 请求回显 |
| oeCode 相关 | string | 标准码：`11 53 8 635 689`（格式化）/ 译码输出补 `A` 前缀（`A 166 500 00 75`） |
| oeName | string | 节温器 / 上水管 |
| brandCode | string | `BENZ` / `BMW` |
| price4s | string | `"628.14"` / `"1270.0"` 4S 价 |

行为：编号/名称不在档案时**不报错**，字段返回空串（仅回显 partsNo）。

请求示例：`openid=…&vin=WBAWX3100G0L69597&originalPartsNos=节温器`

### POST /wechat_x/decoding_api/partImages — 单个 OE 爆炸图定位

请求参数（form）：

| 参数 | 类型 | 必填 | 说明 |
| ---- | ---- | ---- | ---- |
| openid | string | 是 | - |
| vin | string | 是 | - |
| oeCode | string | 是 | OE 件号 |

返回 `data`（**两种形态**）：

- 有档案：list，条目字段：

| 字段 | 类型 | 说明 / 实测样例 |
| ---- | ---- | ---- |
| imageId | string | `10097483`（**partImages_list 的 imageIds 取此值**） |
| position | string | 图上标号 `"2"` |
| lableTop / lableBottom / lableLeft / lableRight | string | 标注框四角坐标（像素） |
| modal | string | 车型名 `"X3 20iX"`（非品牌 id） |
| oeCode / partNumber | string | 回显 |
| count / extraCode | string | 用量 / 补充码 |
| x_img_url | string | **相对路径** `/static/imgfile/1794886767_XXXX.png`，拼接基址域名访问；每次调用生成随机后缀副本 |

- 无档案：dict 空对象（字段空串）——**对接需同时兼容两种形态**。

请求示例：`openid=…&vin=WBAWX3100G0L69597&oeCode=11538635689`

### POST /wechat_x/decoding_api/partImages_list — 爆炸图 + 周边配件清单

返回整张爆炸图上全部配件明细（标号/坐标/名称/4S 价/用量）。

请求参数（form）：

| 参数 | 类型 | 必填 | 说明 |
| ---- | ---- | ---- | ---- |
| openid | string | 是 | - |
| vin | string | 是 | - |
| oeCode | string | 是 | - |
| imageIds | string | 是 | **取 partImages 返回的 `imageId`**（实测闭环证实） |
| carBrandId | string | 是 | **取 vininfo 返回的 `carBrandCode`**（如 `"BMW"`，实测闭环证实） |

返回 `data`（list）：

| 字段 | 类型 | 说明 / 实测样例 |
| ---- | ---- | ---- |
| imageLabel / images_position | string | 图上标号 1~4 |
| images_lableTop / images_lableBottom / images_lableLeft / images_lableRight | string | 标注框四角坐标 |
| oeCode | string | 格式化码 `11 53 8 635 689` |
| oeCodeTrim | string | 紧凑码 `11538635689` |
| oeName / stdName | string | 冷却液泵 / 电子水泵 |
| price4s | string | `"5220.00"` 4S 价 |
| count | string | 用量（`"1"` / `"3"`） |
| extraList | list | `[{key:补充说明,value:200W-2013-04-01},{key:生产起始日期},{key:备注}]` |
| x_img_url | string | 相对路径，同 partImages |

请求示例：`openid=…&vin=WBAWX3100G0L69597&oeCode=11538635689&imageIds=10097483&carBrandId=BMW`

---

## 4. ocr_api（图片识别 VIN）

### POST /wechat_x/ocr_api/local_vin — 本地 OCR 识别 VIN

### POST /wechat_x/ocr_api/tx_vin — 腾讯云 OCR 识别 VIN

两接口参数与返回结构相同；**实测 tx_vin 识别成功率更高，建议优先 tx_vin**。

请求参数（form）：

| 参数 | 类型 | 必填 | 说明 |
| ---- | ---- | ---- | ---- |
| openid | string | 是 | - |
| image_url | string | 是 | **公网可访问**的图片 URL；微信 `mmbiz.qpic.cn` CDN 链接可用，临时素材需先转存 |

返回 `data`（**str**）：

- 成功：17 位 VIN 字符串，实测 `gg.png` → `"LBV5S3104GSN16986"`。
- 识别失败：**空字符串 `""`，无错误码**——调用方按空值处理（不重试同图）。

请求示例：`openid=…&image_url=http://wx_api.fsbbr.net/static/gg.png`

---

## 5. platform_api（第三方平台比价）

### POST /wechat_x/platform_api/jqr — 机汽人平台查询

全网竞价数据（多供应商多品牌）。

请求参数（form）：

| 参数 | 类型 | 必填 | 说明 |
| ---- | ---- | ---- | ---- |
| openid | string | 是 | - |
| number | string | 是 | OE / store 号 / PARTENT 号均可 |

返回 `data`（dict）：

| 字段 | 类型 | 说明 |
| ---- | ---- | ---- |
| jy_data | list | 竞价数据（实测 OE `11538635689` → 230 条；`1665000075` → 469 条） |
| xj_data | list | 询价数据（结构联调期展开） |

`jy_data` 条目主要字段：`_score`（匹配分 10060100.0）、`brand_name`（马勒/依纳）、
`brand_initial`、`custom_brand_name`（`依纳(INA)INA`）、`brand_images_url`
（cdn.jiqirenai.com 图片）、`city_name`、`country_code`（`CN`）、`credit_score`、
`default_code`（`PRD025071`）、`level_code`（`L002`）、`level_flag`、`enquiry_count`、
`datelastupdate`（ISO 时间）、`make`（车型适配数组：`{id, images, …}`）、
`circle_name` / `circle_prod_id` / `description` / `en_*`（可为 null）。
完整字段见测试报告 §4.11。

请求示例：`openid=…&number=11538635689`

### POST /wechat_x/platform_api/zpy — 兆配云平台查询

4S 供应链报价（按城市多行）。

请求参数（form）：同 jqr（openid、number）。

返回 `data`（list，**中文键名**，实测 OE `11538635689` → 9 条 / `1665000075` → 8 条）：

| 字段 | 类型 | 说明 / 实测样例 |
| ---- | ---- | ---- |
| 配件编号 | string | `11538635689` / `A1665000075`（自动归一化 A+OE） |
| 配件名称 | string | 节温器 / 冷却液软管 |
| 品牌 | string | 宝马 / 奔驰 |
| 物料组 | string | `115040` |
| 城市 | string | 北京 / 杭州 / 武汉 / 上海…（**按城市多行报价**） |
| 库存 | int | `131` |
| 折扣 | float | `0.81` ~ `0.85`（城市而异） |
| 4S含税售价 | **string** | `"1270.00"` |
| 4S含税进价 | **string** | `"800.10"` |
| 含税售价 | **float** | `648.08` |
| 发货说明 | string | `服务站下订后3~4个工作日内发货` |

⚠️ 类型混杂：`4S含税售价`/`4S含税进价` 是字符串，`含税售价`/`库存`/`折扣` 是数字——
前端/后端取值需统一转换。

请求示例：`openid=…&number=1665000075`

---

## 附录 A：chat_content 完整消息结构（原文示例照录）

```json
[
    {"type": "input_text", "text": "2026-11-16 10:10:12【老王】：W1NFB4KB9MA569173，右前减震一支，不限品质"},
    {"type": "input_image", "image_url": "http://wx_api.fsbbr.net/static/gg.png"},
    {"type": "input_text", "text": "2026-11-16 10:10:13【系统备注】：上一条是【黄晓明】发的图片"},

    {"type": "input_text", "text": "2026-11-16 10:15:12【马斯克】：885625662火花塞多少钱"},
    {"type": "input_text", "text": "2026-11-16 10:16:45【我回复】：@马斯克 885625662 马勒 120"},

    {"type": "input_text", "text": "2026-11-16 10:20:12【黄晓明】：油底壳 节温器"},

    {"type": "input_audio", "audio_url": "http://wx_api.x.net/static/voice.mp3"},
    {"type": "input_text", "text": "2026-11-16 10:20:25【系统备注】：上一条是【黄晓明】发的音频"},

    {"type": "input_file", "file_url": "http://wx_api.x.net/static/需求.xlsx"},
    {"type": "input_text", "text": "2026-11-16 10:22:16【系统备注】：上一条是【黄晓明】发的文件"},

    {"type": "input_video", "video_url": "http://wx_api.x.net/static/需求.mp4"},
    {"type": "input_text", "text": "2026-11-16 10:23:36【系统备注】：上一条是【黄晓明】发的视频"}
]
```

服务方提供的 Postman 测试参数（unicode 转义原样，含 6 条消息）：

```
chat_content = [{"type": "input_text", "text": "2026-11-16 10:10:12\u3010\u8001\u738b\u3011\uff1aW1NFB4KB9MA569173\uff0c\u53f3\u524d\u51cf\u9707\u4e00\u652f\uff0c\u4e0d\u9650\u54c1\u8d28"}, {"type": "input_image", "image_url": "http://wx_api.fsbbr.net/static/gg.png"}, {"type": "input_text", "text": "2026-11-16 10:10:13\u3010\u7cfb\u7edf\u5907\u6ce8\u3011\uff1a\u4e0a\u4e00\u6761\u662f\u3010\u9ec4\u6653\u660e\u3011\u53d1\u7684\u56fe\u7247"}, {"type": "input_text", "text": "2026-11-16 10:15:12\u3010\u9a6c\u65af\u514b\u3011\uff1a885625662\u706b\u82b1\u585e\u591a\u5c11\u94b1"}, {"type": "input_text", "text": "2026-11-16 10:16:45\u3010\u6211\u56de\u590d\u3011\uff1a@\u9a6c\u65af\u514b 885625662 \u9a6c\u52d2 120"}, {"type": "input_text", "text": "2026-11-16 10:20:12\u3010\u9ec4\u6653\u660e\u3011\uff1a\u6cb9\u5e95\u58f3 \u8282\u6e29\u5668"}]
```

## 附录 B：AI 报价完整调用链路与已知问题

### 调用链路（全部实测闭环）

```
extract_parts_demand（聊天 → VIN + 件名）
  → vininfo（VIN → 车型/carBrandCode）
  → partno（VIN + 件名 → 标准 OE）
  → partImages（VIN + OE → imageId）
  → partImages_list（imageId + carBrandId → 全件清单 + 坐标 + 4S 价）
  → zpy / jqr（OE → 多平台比价）
  → product_list / purchaseHistory_list（本库档案与历史采购）
```

对接建议：OCR 优先 `tx_vin`；`partno` 直接吃 extract 的 `part_name`；
编号无需本地清洗；purchaseHistory / partImages 做重试与空值容错；500 统一兜底。

### 已知问题与待确认（截至 2026-11-17）

| # | 事项 | 状态 | 影响 |
| ---- | ---- | ---- | ---- |
| 1 | ~~purchaseHistory_list 同参数连打结果漂移、偶发 500~~ | **已修复**（2026-11-17，6/6 连测稳定） | 响应层级勘误见该接口章节 |
| 2 | product_list 的 `auto_quote:["1280","91327","32464"]` 语义 | 待服务方说明 | 91327=product_id 已证实，另两个未知 |
| 3 | 个别脏数据 VIN 触发 vininfo 500（如误读变体 `…G0L68597`） | 边缘行为 | 500 兜底 catch，不重试 |
| 4 | chat_content 的 input_image / input_audio / input_video / input_file | 联调期补测 | 纯文本链路已完整验证 |
| 5 | jqr 的 `xj_data`（询价数据）内部结构 | 联调期展开 | jy_data 已完整验证 |
| 6 | HTTPS 证书 hostname 不匹配 | 仅 HTTP 可用 | 需要时由服务方修正 |
| 7 | local_vin 对样图识别失败（返回空串） | 已知局限 | 优先 tx_vin |
