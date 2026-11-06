# 微信表情方案 · wx_app 对接契约

## 结论先行

| 需求 | 实现方式 | 后端改动 |
| --- | --- | --- |
| 前端正常显示别人的 emoji | ① `[微笑]` 等微信表情码 → 本地表情图渲染；② Unicode emoji 系统字体原生显示（已天然支持）；③ msg_type=7 自定义表情图片（已支持） | **无** |
| 我可以发出 emoji | 表情面板选 `[码]`/Unicode 字符插入输入框，随现有 `POST /conversations/{id}/messages` 以 msg_type=1 文本上行，客户微信端自动还原为表情 | **无** |

## 1. 数据契约（已被现有 API 覆盖，零后端改动）

- 微信文本消息里的表情即 `[名称]` 转义码（官方静态表情共 113 个：`[微笑]`…`[蜡烛]`）。
  收到的消息 content 原样含码，无需解码入库。
- 发送：`content` 直接带码，如 `您好～[愉快]`。真实微信客户端渲染为表情；
  未识别码双方都按普通文本显示（微信原生兜底行为，安全）。
- Unicode emoji（😀 等）是 UTF-8 文本，现有链路原样透传，无新增契约。

## 2. 前端集成步骤（原型 → wx_app/frontend）

1. **资源**：把原型 `public/wx-faces/`（113 张 64×64 PNG，约 320KB）拷到
   `frontend/public/wx-faces/`。来源为腾讯官方 CDN `wxa.wxs.qq.com/wxad-design/emojis/smiley_{i}.png`
   （0-104）及对照表源（105-112，`[嘿哈]`…`[蜡烛]`），已与
   「微信文本消息静态表情转义对照表」逐张核验。注意：素材版权归腾讯，建议本地打包
   （不要线上热链），内部工作台使用可行；如需规避风险可换 OpenMoji 等开源同位映射素材。
2. **数据层**：拷 `src/data/wxEmojis.js` → `frontend/src/data/wxEmojis.js`（113 名称数组 + 序号映射）。
3. **工具层**：拷 `src/utils/emoji.js` → `frontend/src/utils/emoji.js`
   （renderEmojiHtml / insertAtCursor / 最近使用；纯函数无依赖）。
4. **展示改造**：[MessageRow.vue](../../frontend/src/components/MessageRow.vue)
   文本分支（`<div v-else class="content">{{ msg.content }}</div>`）改为
   `<div v-else class="content" v-html="renderEmojiHtml(msg.content)"></div>`；
   在其 `<style scoped>` 追加 `.wx-emoji { width:24px; height:24px; vertical-align:-6px; }`
   （scoped 样式：v-html 内容需用 `:deep(.wx-emoji)` 选择器）。
   工具层已先转义再替换，防 XSS；未识别 `[xxx]` 原样显示。
5. **发送改造**：[ChatComposer.vue](../../frontend/src/components/ChatComposer.vue)
   - 输入区换成 `contenteditable` div（微信同款：光标处直接显示表情图，而非 `[码]` 文本）；
   - 工具栏笑脸按钮绑定开关：`<EmojiPicker :visible="pickerVisible" @select="onEmojiSelect" />`
     放入 `.editor`（position:relative 已就绪），面板绝对定位弹在输入框上方；
   - `onEmojiSelect(payload)` 调 `insertEmojiAtCursor(composerEl.value, payload)`：wx 码插入
     `img[data-name]`（光标处显示表情图），unicode 插入字符文本；发送前 `serializeComposer`
     把 img 还原为 `[名称]` 码、`<br>` 还原为 `\n`，随现有 `sendText` 的 msg_type=1 上行；
   - 回车发送（`isComposing`/`keyCode 229` 时放行输入法）、Shift+Enter 用 `insertBreakAtCursor`
     手动插 `<br>`、paste 事件用 `insertPlainTextAtCursor` 只收纯文本。
6. **引用消息（可选）**：`quoteInfoOf` 的 `referLabelOf` 已把引用表情显示为 `[表情]`，
   如需显示被引用文本里的表情码，同样对 quote 文本走 `renderEmojiHtml`。

## 3. 后续扩展（本期不做，接口预留）

- **发送自定义表情（收藏表情）**：需后端新增发送能力
  `POST /conversations/{id}/messages`，`msg_type: 7`，body 携带 emoji CDN 参数或
  先经上传接口取得 media_id——微信发送通道按 msg_type=7 组包。前端把 MessageRow
  现有的 msg_type=7 展示直接复用即可。
- **更多表情码**：微信新版表情（[让我看看][裂开] 等）不在 113 静态集内，落到
  「未识别码原样显示」兜底；如需支持，往 `wx-faces/` 加图并在 `WX_FACES` 数组追加名称即可（渲染/面板自动生效）。

## 4. 验收口径

- 收到的 `[微笑]` 在消息气泡中渲染为微信同款表情图；`[裂开]` 等未知码原样文本。
- 面板选择 `[愉快]` 发送 → 气泡显示表情图；用微信真实客户端给绑定号发同样文本可还原表情。
- Unicode emoji（输入法打出）双向显示正常。
- msg_type=7 消息维持现有贴边大图展示。
