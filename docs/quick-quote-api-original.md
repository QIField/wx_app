# 接口文档
> 请求方式：POST
> 传参类型：form / x-www-form-urlencoded
> 返回类型：JSON
> 统一返回
```json
{
  "code": 0,
  "data": [],
  "msg": "success"
}
```
| 字段 | 说明 |
| ---- | ---- |
| code | 状态码，固定0 |
| data | 业务数据 |
| msg | 提示文字 |

## 接口总表
| 模块 | 接口地址 | 接口名称 | 请求参数 | 校验规则 |
| ---- | ---- | ---- | ---- | ---- |
| crm_api | /wechat_x/crm_api/product_list | 产品列表 | openid、number | openid、number 必填，任一为空返回空data |
| crm_api | /wechat_x/crm_api/purchaseHistory_list | 采购历史 | openid、number、page、limit | openid、number 必填，任一为空返回空data |


| ai_api | /wechat_x/ai_api/extract_parts_demand | 聊天提取配件需求 | openid、chat_content | openid、chat_content 必填，任一为空返回空data；chat_content为JSON字符串 |

chat_content = [
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

测试参数
chat_content = [{"type": "input_text", "text": "2026-11-16 10:10:12\u3010\u8001\u738b\u3011\uff1aW1NFB4KB9MA569173\uff0c\u53f3\u524d\u51cf\u9707\u4e00\u652f\uff0c\u4e0d\u9650\u54c1\u8d28"}, {"type": "input_image", "image_url": "http://wx_api.fsbbr.net/static/gg.png"}, {"type": "input_text", "text": "2026-11-16 10:10:13\u3010\u7cfb\u7edf\u5907\u6ce8\u3011\uff1a\u4e0a\u4e00\u6761\u662f\u3010\u9ec4\u6653\u660e\u3011\u53d1\u7684\u56fe\u7247"}, {"type": "input_text", "text": "2026-11-16 10:15:12\u3010\u9a6c\u65af\u514b\u3011\uff1a885625662\u706b\u82b1\u585e\u591a\u5c11\u94b1"}, {"type": "input_text", "text": "2026-11-16 10:16:45\u3010\u6211\u56de\u590d\u3011\uff1a@\u9a6c\u65af\u514b 885625662 \u9a6c\u52d2 120"}, {"type": "input_text", "text": "2026-11-16 10:20:12\u3010\u9ec4\u6653\u660e\u3011\uff1a\u6cb9\u5e95\u58f3 \u8282\u6e29\u5668"}]

返回字段解释
- sender_name：询价人昵称
- vin：车架号，17 位车辆识别码，原文无则为 null
- quoted：是否为跟进询价 / 二次议价；true = 跟进旧报价，false = 全新询价
- part_name：配件名称，多个配件使用换行符 \n 分隔
- oem_no：配件 OEM 零件号，和 part_name 一一对应换行，无件号则 null
- inquiry_time：客户这条询价第一条消息的时间
- inquiry_content：客户询价原文，合并该客户全部询价内容
- is_replied：客服是否回复该询价；true 有回复，false 无回复
- first_reply_time：客服第一条回复的时间，无回复为 null
- reply_content：客服回复内容，多条序号拼接，无回复为 null



| decoding_api | /wechat_x/decoding_api/vininfo | VIN解析信息 | openid、vin | openid、vin 必填，任一为空返回空data |
| decoding_api | /wechat_x/decoding_api/partno | OE译码查询 | openid、vin、originalPartsNos | 无校验 |
| decoding_api | /wechat_x/decoding_api/partImages | 单个OE爆炸图 | openid、vin、oeCode | 无校验 |
| decoding_api | /wechat_x/decoding_api/partImages_list | 爆炸图+周边配件图 | openid、vin、imageIds、oeCode、carBrandId | 无校验 |


| ocr_api | /wechat_x/ocr_api/local_vin | 本地OCR识别VIN | openid、image_url | openid、image_url 必填，任一为空返回空data |
| ocr_api | /wechat_x/ocr_api/tx_vin | 腾讯云OCR识别VIN | openid、image_url | openid、image_url 必填，任一为空返回空data |


| platform_api | /wechat_x/platform_api/jqr | 机汽人平台查询 | openid、number | openid、number 必填，任一为空返回空data |
| platform_api | /wechat_x/platform_api/zpy | 兆配云平台查询 | openid、number | openid、number 必填，任一为空返回空data |

### 备注
1. 所有接口不支持 JSON body，仅 form 表单传参
2. 表格中标注必填的参数才有非空判断，其余参数直接透传给service层
3. 当前统一返回code=0，无业务错误码分支

