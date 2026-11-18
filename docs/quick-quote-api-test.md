# 快捷报价接口实测报告（2026-11-16）

> 状态：**四轮实测完成——11/11 接口全部拿到真实业务数据且链路闭环（jqr/zpy/partImages 已由服务方修复并复测验证）；剩余仅 purchaseHistory 间歇故障与 auto_quote 含义，见 §6**。
> 接口清单来源：[quick-quote-api-original.md](quick-quote-api-original.md)（《快捷报价接口6-11-16》原文照录；标准化整理后的对接文档为 [quick-quote-api.md](quick-quote-api.md)）。
> 按要求排除音频/视频场景：`ai_api/extract_parts_demand` 仅用**纯文本** `chat_content` 实测
> （剔除 input_image / input_audio / input_video 条目），其余 10 个接口全量实测。

## 1. 结论摘要（TL;DR）

1. **真实部署地址是 `http://wx_api.fsbbr.net/wechat_x/`**。
   初选地址 `https://wxapi.pandas.ltd` 下 `/wechat_x/` 全部 404（该域名只部署了中间方
   `/wx_app/` 路由——对照组 `POST /wx_app/login_api/check_online` 返回 200 正常）。
   文档示例静态资源 `http://wx_api.fsbbr.net/static/gg.png` 所在域名才是本服务宿主。
2. **11 个接口路由全部存在**（无一 404），form 传参通道正常，返回 JSON 结构与文档
   「统一返回」一致（`code` / `msg` / `data` 三键，`application/json`）。
3. **鉴权历史**：中间方侧 openid `B636769FFDAE0882AAB8C4D0138D0677`（采购@小时）与
   `demo` 均被 401 拒绝——快捷报价服务维护**独立 openid 注册表**，
   **两边 id 不通用**（用户已确认）。
4. **改用服务方签发的快捷报价侧专用 openid `5A8D08A1A292061C4B52B3E5DF035B53` 后鉴权放行，
   9/11 接口返回真实业务数据**（HTTP 200 + code=0，见 §4.5）。
5. `ai_api/extract_parts_demand` 的 10 个返回字段与文档解释**逐一吻合**；
   `platform_api/jqr` 与 `zpy` 稳定 HTTP 500（4 次复现）——**服务端缺陷**；【已于 2026-11-17 由服务方修复，复测 200 真实数据，详见 §4.11】。
6. **文档与实际差异**：空/缺 openid 实际返回 401「缺少openid」（非文档的"返回空data"）；
   `data` 实际类型按接口分为 list / str / dict 三种（文档统一写 `[]`）；详见 §5。

## 2. 测试环境

| 项 | 值 |
|---|---|
| 测试日期 | 2026-11-16（当日） |
| 请求方式 | POST，`application/x-www-form-urlencoded`（文档规定不支持 JSON body，实测遵守） |
| 最终基址 | `http://wx_api.fsbbr.net/`（**用户 2026-11-16 确认**；接口路径按文档带 `/wechat_x/` 前缀；HTTPS 不可用，见 §6-4） |
| openid | `5A8D08A1A292061C4B52B3E5DF035B53`（服务方签发的快捷报价侧专用 id，用户提供；**与中间方 id 不通用**，鉴权历史见 §4.2~4.4） |
| 业务测试值 | `number=885625662`、`vin=W1NFB4KB9MA569173`、`image_url=http://wx_api.fsbbr.net/static/gg.png`（均取自文档示例） |
| chat_content | 文档「测试参数」的纯文本子集（4 条 input_text：老王 VIN 减震 / 马斯克火花塞 / 我回复马勒 / 黄晓明油底壳节温器） |
| 工具 | Python requests，超时 30~120s，实测均在 0.1s 内返回 |

## 3. 请求参数清单整理（11 接口）

> 「文档校验规则」= 原文照录；「类型/说明」为按文档语境整理，文档未说明含义处已标注。

| # | 模块 | 接口地址 | 名称 | 必填 | 可选 | 参数类型与说明 | 文档校验规则 |
|---|---|---|---|---|---|---|---|
| 1 | crm_api | /wechat_x/crm_api/product_list | 产品列表 | openid、number | - | openid: string 设备标识；number: string 编号（文档未说明具体含义，疑为件号/客户号） | openid、number 必填，任一为空返回空data |
| 2 | crm_api | /wechat_x/crm_api/purchaseHistory_list | 采购历史 | openid、number | page、limit | page/limit: 分页参数（数字，文档未说明默认值） | openid、number 必填，任一为空返回空data |
| 3 | ai_api | /wechat_x/ai_api/extract_parts_demand | 聊天提取配件需求 | openid、chat_content | - | chat_content: **JSON 字符串**，消息数组，type ∈ input_text / input_image / input_audio / input_file / input_video；文本条目 `{"type":"input_text","text":"时间【昵称】：内容"}`；图片/音频/文件/视频条目分别带 image_url / audio_url / file_url / video_url，后跟「系统备注」文本说明来源 | openid、chat_content 必填，任一为空返回空data；chat_content为JSON字符串 |
| 4 | decoding_api | /wechat_x/decoding_api/vininfo | VIN解析信息 | openid、vin | - | vin: 17 位车架号 | openid、vin 必填，任一为空返回空data |
| 5 | decoding_api | /wechat_x/decoding_api/partno | OE译码查询 | -（无校验） | openid、vin、originalPartsNos | originalPartsNos: OE 零件号（可多个？文档未说明分隔方式） | 无校验 |
| 6 | decoding_api | /wechat_x/decoding_api/partImages | 单个OE爆炸图 | -（无校验） | openid、vin、oeCode | oeCode: OE 编码 | 无校验 |
| 7 | decoding_api | /wechat_x/decoding_api/partImages_list | 爆炸图+周边配件图 | -（无校验） | openid、vin、imageIds、oeCode、carBrandId | imageIds: 图片 id（可多个？分隔方式未说明）；carBrandId: 车型品牌 id（取值范围未说明） | 无校验 |
| 8 | ocr_api | /wechat_x/ocr_api/local_vin | 本地OCR识别VIN | openid、image_url | - | image_url: 图片的公网可下载 URL | openid、image_url 必填，任一为空返回空data |
| 9 | ocr_api | /wechat_x/ocr_api/tx_vin | 腾讯云OCR识别VIN | openid、image_url | - | 同上 | openid、image_url 必填，任一为空返回空data |
| 10 | platform_api | /wechat_x/platform_api/jqr | 机汽人平台查询 | openid、number | - | number: 件号/编码 | openid、number 必填，任一为空返回空data |
| 11 | platform_api | /wechat_x/platform_api/zpy | 兆配云平台查询 | openid、number | - | 同上 | openid、number 必填，任一为空返回空data |

统一返回（文档原文）：`{"code": 0, "data": [], "msg": "success"}`，code 固定 0。

## 4. 实测结果总表

### 4.1 第一轮：`https://wxapi.pandas.ltd`（用户初选地址）

| 接口 | HTTP 状态码 | 返回 |
|---|---|---|
| 全部 11 个接口 | **404** | Flask 默认 404 HTML 页（`text/html`）——该域名未部署 `/wechat_x/` 路由 |
| 对照组 `POST /wx_app/login_api/check_online` | 200 | `{"code":0,"msg":"success"}`（中间方路由正常，排除域名整体故障） |
| 变体 `POST /crm_api/product_list`（无前缀） | 404 | 同上 404 页 |

### 4.2 第二轮：`http://wx_api.fsbbr.net/wechat_x/`（真实部署地址）

全部 POST + form 传参，`Content-Type: application/json`，耗时 0.05~0.12s：

| # | 接口 | HTTP 状态码 | code | msg | data |
|---|---|---|---|---|---|
| 1 | crm_api/product_list | 401 | 401 | openid不存在或已关闭 | null |
| 2 | crm_api/purchaseHistory_list | 401 | 401 | openid不存在或已关闭 | null |
| 3 | ai_api/extract_parts_demand（纯文本） | 401 | 401 | openid不存在或已关闭 | null |
| 4 | decoding_api/vininfo | 401 | 401 | openid不存在或已关闭 | null |
| 5 | decoding_api/partno | 401 | 401 | openid不存在或已关闭 | null |
| 6 | decoding_api/partImages | 401 | 401 | openid不存在或已关闭 | null |
| 7 | decoding_api/partImages_list | 401 | 401 | openid不存在或已关闭 | null |
| 8 | ocr_api/local_vin | 401 | 401 | openid不存在或已关闭 | null |
| 9 | ocr_api/tx_vin | 401 | 401 | openid不存在或已关闭 | null |
| 10 | platform_api/jqr | 401 | 401 | openid不存在或已关闭 | null |
| 11 | platform_api/zpy | 401 | 401 | openid不存在或已关闭 | null |

实测返回结构：`{"code": 401, "msg": "...", "data": null}` —— 与文档统一返回的三键结构一致，
但 `data` 为 null（不是 `[]`）。

### 4.3 openid 变体探测（以 product_list 代表）

| 用例 | HTTP 状态码 | 返回 |
|---|---|---|
| openid=`demo` | 401 | `{"code":401,"msg":"openid不存在或已关闭"}` |
| openid=`""`（空值） | 401 | `{"code":401,"msg":"缺少openid"}` |
| 不传 openid | 401 | `{"code":401,"msg":"缺少openid"}` |
| HTTPS `https://wx_api.fsbbr.net` | 连接失败 | SSL 证书校验失败：`certificate verify failed: Hostname mismatch, certificate is not valid for 'wx_api.fsbbr.net'` |

### 4.4 复测记录（2026-11-16，用户确认 openid 后）

用户明确指定使用 openid = `B636769FFDAE0882AAB8C4D0138D0677` 重测，结果：

- 11 个接口全部复测：仍为 HTTP 401 `{"code":401,"msg":"openid不存在或已关闭"}`，与首轮完全一致（耗时 0.05~0.17s）
- 小写变体 `b636769ffdae0882aab8c4d0138d0677`：同样 401「openid不存在或已关闭」——**排除大小写格式问题**
- 判定：该 openid 在中间方（wxapi.pandas.ltd `check_online` 返回 code=0）有效，
  但在快捷报价服务（wx_api.fsbbr.net）的注册表中**不存在或被关闭**。
  这是服务方侧的注册/启用问题，不是传参问题。需服务方在其后台登记并启用该 openid 后复测。
- **基址确认补充**（用户随后指定基址为 `http://wx_api.fsbbr.net/`）：复测验证
  带前缀 `/wechat_x/crm_api/product_list` 与无前缀 `/crm_api/product_list`
  返回**完全相同**的 401——鉴权为该服务全局层，与路径前缀无关；openid 仍未放行。



### 4.5 第三轮：快捷报价侧专用 openid 业务实测（11 接口真实返回）

openid = `5A8D08A1A292061C4B52B3E5DF035B53`，全部 HTTP 200 / code=0（jqr、zpy 除外）：

| # | 接口 | HTTP | code | data 类型 | 耗时 | 关键返回 |
|---|---|---|---|---|---|---|
| 1 | crm_api/product_list | 200 | 0 | dict（内嵌信封） | 0.57s | `data.data` 含分页字段（current_page/last_page/per_page/total）+ `data[].child[]` 产品行 + `no_exist_oe` + `pricehead:"开思(CNY)"`；测试 OE `885625662` 无档案 → name「找不到产品」、`no_exist_oe:["885625662"]`；`auto_quote:[]`、`company_system:1`、`store_price_state:0` |
| 2 | crm_api/purchaseHistory_list | 200 | 0 | dict（内嵌信封） | 2.65s | `list:{current_page:"1", data:"", last_page:"0", per_page:"10", total:"0"}`（**数字字段全是字符串**）+ `total:{purchase_quantity:"0", totalprice:"0.00"}`；内层 msg「返回成功」 |
| 3 | ai_api/extract_parts_demand | 200 | 0 | **list**（3 条） | 3.13s | **10 个字段与文档逐一吻合**（见下方详述） |
| 4 | decoding_api/vininfo | 200 | 0 | list（1 条） | 1.53s | `{carBrandCode:"BENZ", carBrandName:"奔驰", carModelName:"进口奔驰 GLE 350 4MATIC", fuelType:"汽油", saleModelName:"奔驰 GLE 350 4MATIC 2021 2.0T 手自一体 动感型", transmissionType:"自动", vin}` |
| 5 | decoding_api/partno | 200 | 0 | list（1 条） | 0.43s | `{partsNo:"885625662"(回显), brandCode, count, oeCode, oeCodeTrim, oeName, price4s}`——OE 无档案时**字段全空串**（非空数组） |
| 6 | decoding_api/partImages | 200 | 0 | list（1 条） | 0.39s | `{oeCode, vin(回显), imageId, lableTop/Bottom/Left/Right, position, modal, partNumber, count, extraCode, x_img_url}`——无档案时除回显外全空 |
| 7 | decoding_api/partImages_list | 200 | 0 | list（1 条） | 0.50s | `{oeCode, vin(回显), extraList, imageLabel, images_lableTop/Bottom/Left/Right, images_position, stdName, oeName, oeCodeTrim, price4s, count, x_img_url}`——同样空档案不报错 |
| 8 | ocr_api/local_vin | 200 | 0 | **str** | 0.30s | `data:""`——本地 OCR 对样图 gg.png 未识别出 VIN，**失败仅返回空串**，无错误码 |
| 9 | ocr_api/tx_vin | 200 | 0 | **str** | 1.35s | `data:"LBV5S3104GSN16986"`——腾讯云 OCR 成功；样图 gg.png 实含 BMW 车架号 |
| 10 | platform_api/jqr | **500** | - | HTML 错误页 | 1.08s | Flask 500 Internal Server Error（非 JSON） |
| 11 | platform_api/zpy | **500** | - | HTML 错误页 | 6.08s | 同上 |

**ai_api 返回明细（3 条询价，4 条输入消息被正确归并）**：

| sender_name | vin | part_name | oem_no | quoted | is_replied | first_reply_time | reply_content |
|---|---|---|---|---|---|---|---|
| 老王 | W1NFB4KB9MA569173 | 右前减震 | null | false | false | null | null |
| 马斯克 | null | 火花塞 | 885625662 | false | true | 2026-11-16 10:16:45 | `1、@马斯克 885625662 马勒 120`（多条回复序号拼接，同文档） |
| 黄晓明 | null | `油底壳\n节温器`（**多件换行分隔，同文档**） | null | false | false | null | null |

每条含 `inquiry_time`（该客户首条消息时间）、`inquiry_content`（询价原文合并）。
「马斯克」的问价与「我回复」被正确归并为同一询价（is_replied=true）——归并逻辑符合业务预期。

### 4.6 跟进测试（2026-11-16 同日）

| 用例 | 结果 |
|---|---|
| vininfo(OCR 所得 VIN `LBV5S3104GSN16986`) | 200：`华晨宝马 525Li / BMW / 2016 2.0T 手自一体 / 汽油 / 自动`——**OCR → 译码链路闭环验证通过** |
| jqr 重试（原 OE） | 500 复现 |
| zpy 重试（原 OE） | 500 复现 |
| jqr 换 OE 样本 `A0005400017` | 500 复现 |
| zpy 换 OE 样本 `A0005400017` | 500 复现 |
| purchaseHistory_list 换 OE 样本 `A0005400017` | 200：空列表（该 OE 不在产品库，属正常） |
| product_list 换 OE 样本 `A0005400017` | 200：`no_exist_oe:["0005400017"]`（**OE 归一化：前缀字母被剥离**） |

→ jqr/zpy 的 500 共 **4/4 复现**，与 OE 取值无关，判定服务端缺陷（疑其对接机汽人/兆配云上游异常）。

### 4.7 真实 OE 补测（2026-11-16，用户提供 OE `1665000075`）

真实 OE = `1665000075`（奔驰 276/166 上水管，菲尔 FREY 品牌替代厂件，库内 product_id 91327）：

| 接口 | 结果 |
|---|---|
| product_list | **完整产品档案解锁**：`brand_name:"菲尔"` / `brand_code:"724500401"`、`l_name_zh:"上水管"`、`l_model_zh:"276/166"`、`cass_oebrand_name:"奔驰"`、`cost_price:"69.00"`、`display_number` 含 OE / PARTENT(724500401) / **store(`A1665000075`)** 三种编号、`bigpic`、`frey_no`/`frey_stock` 系列、`last_purch_time:"2026-09-17"`、`kingdee_encoding:"1665000075 FREY 276/166"` 等字段；child 实际 **101 个字段**、按**配件品牌**分 3 行（菲尔 cost 69.00 / 原厂 260.00 / 盖茨 109.00，store_price 均 628.14）；`auto_quote:["1280","91327","32464"]`（**语义未知**，91327=product_id） |
| purchaseHistory_list | **真实采购历史解锁**：订单 `CGRK002202610150116`（采购入库单）、`brand:"原厂"`、`price:"260"`、`amount_money:"780"`、供应商「佛山市巴博瑞汽车零配件有限公司」、客户「广州腾熙(昌盛)汽配」/经手人「李禹函」、`payment_description:"月结"`；**`create_date` 是 Unix 时间戳字符串 `"1792060695"`**（≈2026-10-15，与订单号日期吻合）——对接时需前端格式化 |
| partno | **完整译码解锁**：`{brandCode:"BENZ", oeCode:"A 166 500 00 75", oeCodeTrim:"A1665000075", oeName:"上水管", count:1, price4s:"628.14"}`——4S 价 628.14 vs 我方 cost 69.00；译码侧输出奔驰标准 A 前缀格式 |
| jqr | **仍 HTTP 500**——真实存在 OE 也 500，证实与 OE 是否存在无关，服务端缺陷 |
| zpy | **仍 HTTP 500**——同上 |
| partImages | **HTTP 502 Bad Gateway**（nginx）→ 重试 ReadTimeout(60s) → 120s 再试仍 502；空 OE 时秒回 200 空字段，**真实数据场景上游挂起**；partImages_list 用真实 imageId 的串联验证被阻塞 |

**小结**：除 partImages（真实数据 502/超时）与 jqr/zpy（500）外，全部接口的真实数据路径均已验证。

### 4.8 收尾补测（2026-11-16，参数行为关闭）

| 用例 | 结果 |
|---|---|
| partno 多值 OE（`1665000075,885625662` 逗号分隔） | ✅ 有效：返回 2 条对象，不存在的 OE 返回全空对象——**多值问题关闭** |
| product_list 用 store 号 `A1665000075` 检索 | ✅ 命中同一产品——number 接受 store 编号 |
| product_list 用 PARTENT 号 `724500401` 检索 | ✅ 命中同一产品——number 接受 PARTENT 编号（is_bold=0、auto_quote 仅 1 项，细节差异） |
| purchaseHistory_list `page=2` | ❌ **HTTP 500**（page=1 正常）——**翻页服务端缺陷** |
| jqr / zpy 换 store 号 / PARTENT 号 | ❌ 全部 500——累计 **8 次**，彻底排除编号格式因素 |

### 4.9 按开发方 Postman 截图复测（2026-11-16，用户提供 4 张截图）

截图参数：`vin=WBAWX3100G0L69597`（宝马 X3）、`oeCode=11538635689`、`imageIds=10097483`、`carBrandId=BMW`、`originalPartsNos=节温器`：

> **勘误（2026-11-17）**：本节最初将截图 VIN 第 14 位 `9` 误读为 `8`，据此得出"截图
> VIN 崩溃"的错误结论。经开发方指正复核：截图 VIN 为 `…G0L69597`，复测 **200 完整
> 译码，与截图完全一致，vininfo 本身健康**。字符串 `WBAWX3100G0L68597`（误读变体）
> 稳定 500/502 仅说明服务端对个别脏数据/不存在记录会崩，不再列为对接故障。

| 用例 | 截图（开发方） | 本次复测 | 差异结论 |
|---|---|---|---|
| vininfo（宝马X3 VIN `…G0L69597`） | 200：宝马 X3 20iX | ✅ **200 完整译码，与截图一致**（含修正 O→0 后双连测稳定） | **无差异**；此前记录的 500 系误读 VIN（见上方勘误） |
| partno（`originalPartsNos=节温器` + 宝马VIN） | 200：`11 53 8 635 689` / 1270.0 | ✅ **200，结果与截图完全一致** | **重大发现：originalPartsNos 接受配件名称**，按名+VIN 译码；奔驰 VIN+节温器 亦正常（`A 264 200 39 01`/1738.54）——跨品牌按名译码可用 |
| partImages（宝马 OE） | 200：imageId=10097483、坐标、modal="X3 20iX"、x_img_url | ⚠️ 200 但**字段全空** | 图片上游已从 502 变为**静默空返回**——用开发方自己的原参数也取不到图 |
| partImages_list（imageIds=10097483 + carBrandId=BMW） | 200：extraList、冷却液泵、5220.00 等 | ⚠️ 200 但**字段全空** | 同上；**carBrandId=carBrandCode("BMW") 用法被开发方截图证实**（此前猜想正确）；modal 实为**车型名**而非品牌 id |

**综合结论**：
1. `partno` 真实用法是 **「VIN + 配件名称 → OE 码」**（AI 报价链路核心：extract_parts_demand 的 part_name → partno → partImages），文档未写明；
2. `carBrandId` 传 carBrandCode（"BMW"/"BENZ"）为官方用法；
3. 服务端**状态随时间漂移**：截图时段正常的数据，现在 vininfo 对特定 VIN 500、图片双接口静默空返回——图片库上游当前不可用。

### 4.10 故障稳定性画像（连打复测，2026-11-17）

翻页矩阵 + 同组合连打 3~4 次的结论：

| 接口 | 连打结果 | 故障性质 |
|---|---|---|
| purchaseHistory_list 各组合（p1l10/p2l1/p2l5/p3l5） | 同参数时而正常、时而空、偶发 500 | **随机间歇故障**（上游不稳定），与 page/limit 取值无关；此前"page=2 必 500"实为随机故障的偶发表现。截图原参 p2l5 亦复现 5 行→空→空。【✓ 2026-11-17 服务方修复：p2l5 复测 6/6 稳定，见 §5.1】 |
| platform_api/jqr | 500 ×4（累计 **16/16**） | **确定性故障**，彻底挂死 |
| platform_api/zpy | 500 ×4（累计 **16/16**） | 同上 |
| vininfo | 正常 VIN（奔驰/宝马525/宝马X3 …69597）全部 200；仅误读字符串 `…G0L68597` 触发 500×5+502 | **非对接故障**：vininfo 健康；脏数据字符串会崩属边缘行为，对接 500 兜底即可 |
| partImages（宝马 OE） | 502 ×2 + 500 ×2 | **间歇故障**：三种形态轮换（502/500/静默空），上游取图链路不稳 |

**对接风险定级**：jqr/zpy 为硬故障（必须服务方修）；purchaseHistory、partImages 为稳定性问题（需服务方加超时/重试/降级，我方对接也必须做重试与空值容错）；vininfo 经勘误确认健康（勘误详见 §4.9）。

### 4.11 jqr / zpy 修复后复测（2026-11-17，服务方修复 + 提供 Postman 截图证实）

服务方反馈已修复并给出截图（原参 `number=11538635689` 宝马节温器，200 OK）。按同一参数矩阵复测，每用例连测 2 次：

| 用例 | 结果 | 稳定性 |
|---|---|---|
| jqr `number=11538635689`（截图原参） | 200 code=0，`jy_data` **230 条** | ✅ 2/2 一致 |
| jqr `number=1665000075`（奔驰 OE） | 200 code=0，`jy_data` **469 条** | ✅ 2/2 一致 |
| zpy `number=11538635689` | 200 code=0，list **9 条**（北京/杭州/武汉…） | ✅ 2/2 一致 |
| zpy `number=1665000075` | 200 code=0，list **8 条**（上海/武汉/北京…） | ✅ 2/2 一致 |

**jqr 返回结构**（与截图一致）：`data = { jy_data: [...], xj_data: [...] }`（竞价数据 + 询价数据）。
`jy_data` 条目字段：`_score`（如 10060100.0）、`brand_images_url`（cdn.jiqirenai.com 图片）、
`brand_initial`、`brand_name`（依纳/马勒）、`circle_name`/`circle_prod_id`（null）、
`city_name`（杭州）、`country_code`（"CN"）、`credit_score`、`custom_brand_name`
（"依纳(INA)INA"）、`datelastupdate`（ISO 时间）、`default_code`（"PRD025071"）、
`description`、`en_brand_name`、`en_quality_name`、`enquiry_count`、`level_code`（"L002"）、
`level_flag`、`make`（数组：{id, images…} 车型适配）等。`xj_data` 结构待业务联调时展开。

**zpy 返回结构**（与截图一致）：`data = [...]` 扁平数组，每条字段（中文键名）：
`4S含税售价`（字符串 "1270.00"）、`4S含税进价`（字符串 "800.10"）、`发货说明`
（"服务站下订后3~4个工作日内发货"）、`含税售价`（**数字** 648.08）、`品牌`（宝马/奔驰）、
`城市`、`库存`（数字 131）、`折扣`（数字 0.81）、`物料组`（"115040"）、`配件名称`
（节温器/冷却液软管）、`配件编号`（"11538635689" / "A1665000075"）。
⚠️ 混合类型注意：`4S含税售价`/`4S含税进价` 是字符串，`含税售价`/`库存`/`折扣` 是数字——前端取值需统一转换。

**附带发现**：zpy 返回的 `配件编号` 自动归一化为 `A1665000075`（A+OE store 形态），
且不同城市报价/折扣/库存各不相同——按城市报价是天然多行，对接按列表逐行展示或择优。

**至此 11/11 接口全部拿到真实业务数据。**

### 4.12 partImages 修复复测 + partImages_list 串联闭环（2026-11-17，用户提供参数）

参数：`openid=5A8D…B53`、`vin=WBAWX3100G0L69597`、`oeCode=11538635689`（宝马节温器）：

| 用例 | 结果 |
|---|---|
| partImages ×3 连测 | ✅ **200 全部稳定**（此前 502/超时/静默空，已修复） |
| partImages_list（imageIds=10097483 + carBrandId=BMW） | ✅ **闭环打通**：返回 4 条爆炸图明细，与开发方截图完全一致 |

**partImages 返回结构**：`data = [ {...} ]` **数组**（注意：空档案时为 dict 空对象，两种形态需兼容）。
条目字段：`count`("1")、`extraCode`、`imageId`("10097483")、标注四角坐标
`lableTop/Bottom/Left/Right`("229"/"251"/"151"/"162")、`modal`("X3 20iX" 车型名)、
`oeCode`、`partNumber`、`position`("2" 图上标号)、`vin`、`x_img_url`（**相对路径**
`/static/imgfile/…png`，每次调用生成随机后缀副本，拼接 `http://wx_api.fsbbr.net` 前缀访问）。

**partImages_list 闭环返回**（imageIds=partImages.imageId，carBrandId=carBrandCode"BMW" ✅ 最终证实）：
`data = [...]` 每条：`imageLabel`(1~4 图上标号)、`images_position`、标注四角坐标
(`images_lableTop/Bottom/Left/Right`)、`oeCode`（格式化 "11 53 8 635 689"）、`oeCodeTrim`
（紧凑 "11538635689"）、`oeName`（冷却液泵/节温器/螺栓/ISA 螺栓）、`stdName`（电子水泵…）、
`price4s`（"5220.00"/"1270.00"/"18.00"/"30.00"）、`count`（用量，字符串）、`extraList`
（[{key:补充说明,value:"200W-2013-04-01"},{key:生产起始日期},{key:备注}]）、`x_img_url`。
字段与开发方截图逐一吻合。

**AI 报价完整链路全部验证通过**：
`extract_parts_demand`(聊天→VIN+件名) → `vininfo`(VIN→车型) → `partno`(VIN+件名→OE)
→ `partImages`(VIN+OE→图 id) → `partImages_list`(图 id→全件清单+坐标+价) → `zpy/jqr`(比价)。

### 4.13 联调期补测（2026-11-18，多模态端到端 + xj_data）

> 配套业务端同日验证：pytest 443 绿；真实链路冒烟 5/5（vininfo / product_list / partno / jqr / zpy 两条已知参数全部对上历史值）。

**① chat_content 多模态条目端到端（隔离变量法）**：

| 用例 | 输入要点 | 结果 |
|---|---|---|
| A 纯文本对照 | 1 条文本（奔驰 VIN + 节温器） | ✅ 1 场景，vin/part 提取正确——服务当日健康 |
| B 图片+备注+指代追问 | 文本仅「这个多少钱」+ gg.png + 系统备注 | ✅ **1 场景，vin=`LBV5S3104GSN16986`（图内 VIN）**——AI 从图片读出 VIN，「图+文合并理解」端到端打通；part=null（图上无件名） |
| C 图片+坏音频 | B 再加 1 条不可达 `input_audio`（URL 404） | ❌ **0 场景静默归零**，无错误码 |
| D 全混排 | 文本+图片+audio+file+video 共 10 条（后三类 URL 均不可达） | ❌ 0 场景——坏媒体条目毒化整次调用 |

**对接红线**：`input_audio / input_file / input_video` 条目只要带不可达 URL，**整个 extract
调用静默返回空 list**（连好图片场景一起丢）。组装器规则：媒体条目只放「已确认可公网拉取」
的 URL，不可达宁可降级为占位文本备注——业务端 V1 现行实现即如此
（`backend/services/quote_context.py` 只发占位备注，不发媒体直链）。另：`quoted` 字段
实测可为 null（非恒为 bool）。

**② jqr 的 `xj_data` 结构**：OE `1665000075`（jy_data 464 条）与 `11538635689`
（jy_data 230 条）的 `xj_data` 均**恒为空 list**——正常比价路径不产出询价数据，
对接按空列表处理即可，无需展开结构。

## 5. 异常与问题标注

### 5.1 接口调用失败原因

- **[已解决] openid 鉴权拦截**（历史，见 §4.2~4.4）：快捷报价服务维护**独立 openid 注册表**
  （支持「已关闭」状态），与中间方设备 openid 不通用；换用服务方签发的专用 id 后放行。
- **[已解决 2026-11-17] platform_api/jqr、platform_api/zpy 稳定 HTTP 500**：返回 Flask HTML 错误页
  （非 JSON，违反「统一返回 JSON」约定）。共 6 次复现（885625662 / A0005400017 /
  真实 OE 1665000075 均触发），与 OE 是否存在无关、同服务其余接口正常——判定为
  服务端缺陷（疑其对接机汽人/兆配云上游异常）。**服务方已于 2026-11-17 修复，
  复测 4 用例（截图原参 + 奔驰 OE）全部 200 code=0 且两连测稳定，结构详见 §4.11。**
- **[已解决 2026-11-17] decoding_api/partImages 真实数据场景 502/超时**：空 OE 秒回 200（字段全空）；
  真实 OE 1665000075 触发 502 Bad Gateway（nginx）→ ReadTimeout(60s) → 502，共 3 次。
  疑其调用开思上游取图挂起。partImages_list 的串联验证被阻塞。
  **后续状态漂移（§4.9）**：图片上游一度改为**静默空返回**。**服务方已于 2026-11-17 修复，
  复测（宝马 VIN+节温器 OE）3 连测全部 200 稳定，且 partImages_list 用真实 imageId +
  carBrandId=BMW 串联闭环打通，与开发方截图完全一致——详见 §4.12。**
- **[勘误] vininfo 健康正常**：此前"特定 VIN 500"系截图 VIN 第 14 位 `9` 误读为
  `8` 所致。真实截图 VIN `WBAWX3100G0L69597` 复测稳定 200 完整译码。误读字符串
  `WBAWX3100G0L68597` 稳定 500/502——服务端对个别脏数据字符串会崩，对接按 500
  兜底 catch 即可，不列为服务方待修项（勘误详见 §4.9）。
- **[已修复 2026-11-17] purchaseHistory_list 随机间歇故障**：此前同一参数连打结果漂移——
  `page=1&limit=10` 前两次正常返回 10 行，第三次返回空；`page=2&limit=5`（开发方
  截图原参）复测 5 行→空→空；偶发 HTTP 500（§4.8、§4.10）。与 page/limit 取值
  无关，属上游不稳定。**服务方修复后按用户提供的同参数（p2l5）复测 6/6 连打全部
  稳定返回真实数据。**
- **[勘误] purchaseHistory_list 响应层级**：此前记录将分页字段扁平化（误记为
  `data.{current_page,data,…,totalprice}`）。真实层级为三层嵌套：
  `data.{status:200, msg:"返回成功", data:{total:{purchase_quantity,totalprice 全量汇总},
  list:{current_page, data[], last_page, per_page, total:81}}}`，`current_page`/`per_page`
  为字符串，订单行约 69 字段——标准化文档已按真实层级修正。
- **[低风险] ocr_api/local_vin 识别失败仅返回空串** `data:""`：无错误码区分「识别失败」与
  「图片无 VIN」，对接时只能按空串判断；建议优先用 tx_vin。

### 5.2 文档与实际行为差异

| # | 文档描述 | 实际行为 | 影响 |
|---|---|---|---|
| 1 | 未写部署域名 | 真实地址 `http://wx_api.fsbbr.net/wechat_x/`；`wxapi.pandas.ltd` 无此路由 | 对接配置基址必须用前者 |
| 2 | 「任一为空返回空data」 | 空/缺 openid 返回 **HTTP 401** `{"code":401,"msg":"缺少openid"}`，非空 data | 前端需按 401 处理，不能指望空 data 兜底 |
| 3 | 「统一返回 code 固定 0，无业务错误码分支」 | 实际存在 **401 错误分支**（缺少openid / openid不存在或已关闭），且 HTTP 状态码同步为 401 | 客户端须处理 code=401 |
| 4 | -（未提 HTTPS） | HTTPS 证书 hostname 不匹配，仅 HTTP 可用 | 不建议走 https（或需服务方修证书）；传输为明文 |
| 5 | 「错误码」列缺失 | 401 为已观测错误码（缺少openid / openid不存在或已关闭） | 客户端须处理 code=401 |
| 6 | 统一返回示例 `"data": []` | 实际 data 类型按接口分三种：ai/decoding 返回 **list**、ocr 返回 **str**、crm 返回 **dict**（内嵌上游信封 `data.data{msg,status}`） | 对接方须按接口分别适配 |
| 7 | 未给 OCR 返回示例 | OCR 的 data 是**字符串**（识别出的 VIN），失败为 `""` | 同上 |
| 8 | 「无业务错误码分支」 | 业务层空结果不报错：partno/partImages 空档案返回**字段全空的对象**（非空数组）；product_list 用 `no_exist_oe` 数组提示 OE 不存在 | 判空逻辑按字段做，不能只判数组长度 |
| 9 | - | purchaseHistory_list 数字字段（current_page/total/per_page 等）均为**字符串** | 取值需转型 |
| 10 | - | purchaseHistory_list 的 `create_date`/`expected_delivery_date` 是 **Unix 时间戳字符串**（1792060695 ≈ 2026-10-15） | 前端需格式化 |
| 11 | - | product_list 的 `auto_quote:["1280","91327","32464"]` 语义未知（91327=product_id，另两个疑似价格/库存 id） | 待服务方说明 |
| 12 | - | 编号归一化行为：服务侧匹配 OE 会剥前缀字母（A0005400017→0005400017），译码输出反而补 A 前缀（A1665000075）；store 编号 = `A` + OE | 我方传 OE 前不必清洗 |
| 13 | 文档未写明 `partno.originalPartsNos` 可传**配件名称** | 实测+开发方截图证实：`节温器`+VIN → 直接返回该车型对应 OE 码（跨品牌可用）——**「VIN+名称→OE」是 AI 报价链路核心用法**（part_name → partno → partImages） | 对接直接传 extract 结果的 part_name |

### 5.3 参数层面的未知项（文档未定义，待确认）

- `number` 语义：`product_list` 实测按 **OE 件号**检索（返回 `display_number key="OE"`、
  `search_number`、`no_exist_oe`）；`purchaseHistory_list` 的 number 亦为 **OE**
  （**用户已确认**）；两个样本 OE（885625662 / A0005400017）均不在服务产品库中
  （`no_exist_oe`），故采购历史为空属正常，非空路径待真实 OE 补测。
  **行为发现**：OE 会被归一化——`A0005400017` 在 `no_exist_oe` 中显示为
  `0005400017`（前缀字母被剥离）；`jqr`/`zpy` ✅ **已验证**（§4.11）：number 按 OE 检索，
  `1665000075` → jqr 469 条竞价 / zpy 8 条报价，`11538635689` → 230 条 / 9 条——
  两平台按任意 OE 全量返回比价数据，无"档案不存在"概念（查不到时应为空列表/空data）。
  **`xj_data` 补测（§4.13）**：两个 OE 均恒空 list，对接按空列表处理。
- `purchaseHistory_list` 的 `page`/`limit`：实测接受 `page=1&limit=10` 并回显
  `per_page:"10"`（字符串）；默认值与上限未知；**`page=2` 服务端 500**（§4.8）。
- `partno` 的 `originalPartsNos` 多值分隔方式：✅ **已关闭**——逗号分隔有效，
  返回逐 OE 一条对象（§4.8）。
- `product_list` 的 `number`：✅ **已关闭**——同时接受 OE / store 号(`A+OE`) /
  PARTENT 号(`frey_no`)三种编号检索。
- `partImages_list` 的 `imageIds`/`carBrandId` 来源：✅ **全部闭环证实**（§4.12）——
  `imageIds` 取自 `partImages` 返回的 `imageId`；`carBrandId` 传 vininfo 的
  `carBrandCode`（"BMW"）。早期 7 种组合全空的原因即 partImages 上游故障拿不到
  真实 imageId，修复后一次打通。

### 5.4 按要求未测的场景

- `chat_content` 的 input_image / input_audio（音频文件）/ input_video（视频）条目（用户要求排除）
- OCR 用真实 VIN 车照片（用了文档示例图 gg.png——实为含 BMW 车架号的图，tx_vin 识别成功，见 §4.5-9）

## 6. 后续待办

1. **[服务方] 上游故障修复进展**：jqr/zpy 500（✓ 已修复，§4.11）、partImages 502
   （✓ 已修复，§4.12）、purchaseHistory_list 间歇故障（✓ 已修复，p2l5 复测 6/6 稳定，
   §5.1）均已解决。剩余待办：auto_quote 语义说明。
2. **[服务方] 说明 product_list 的 `auto_quote` 数组语义**。
   （imageIds←partImages.imageId、carBrandId=carBrandCode 均已闭环证实 ✓，见 §4.12。）
3. **[对接] `.env` 增加 `QQ_API_BASE_URL = http://wx_api.fsbbr.net/wechat_x/` 与
   `QQ_OPENID`（专用 id `5A8D08A1A292061C4B52B3E5DF035B53`，勿与中间方 openid 混用）**——
   ✅ 已落地（`backend/config.py` 键名 `QQ_API_BASE_URL` / `QQ_OPENID` / `QQ_TIMEOUT_SECONDS`，
   实测前记的 `QUICK_QUOTE_*` 键名为勘误），docs/quick-quote-api.md 部署地址已补记（✓ 见「统一约定」）。
4. ~~音频/视频/文件场景（chat_content 的 input_audio / input_video / input_image / input_file）
   按本次要求未测~~ ✅ **2026-11-18 已补测（§4.13）**：input_image 端到端打通（图内 VIN
   提取成功）；input_audio/file/video 带不可达 URL 时**整次调用静默返回空 list**——
   组装器只放可达媒体 URL 或降级占位备注（现行实现已遵循）。
5. OCR 建议优先 tx_vin（local_vin 对样图识别失败）；如有真实 VIN 车照片可补测 local_vin。
6. 若走 HTTPS 需求成立，请服务方修正证书（当前 hostname mismatch）。
