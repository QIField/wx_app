# 聊天窗口自定义文本选中交互系统 — 实施方案

## Context（背景）

当前聊天气泡文本使用浏览器原生选区，存在两个交互痛点：

1. **痛点 A**：在气泡内选中文本后，点击气泡的非文本区域（padding、头像、空白），原生选区被浏览器折叠，已选内容消失。
2. **痛点 B**：未精准选中文本（或选区跨气泡）时，右键复制行为不精确；且原生选区的消失/残留不可控。

此外原生选区样式（::selection）与整体 UI 风格不统一，表情图片在选区中的表现不可控。本方案用自定义选区引擎完全接管聊天区的文本选中交互：禁用原生选择，拖拽产生自定义高亮，右键仅复制实际选中的片段（无选中兜底全文），点击非文本区域保留已有选中。

## 技术选型

| 决策点 | 选择 | 理由 |
|---|---|---|
| 高亮渲染 | CSS Custom Highlight API（`CSS.highlights` + `::highlight()`） | 零 DOM 侵入（不包裹 span，不破坏 v-html/表情图结构），Range 自动跟随滚动/缩放，性能好。支持线：Chrome/Edge 105+、Firefox 139+、Safari 17.2+，覆盖桌面主流环境 |
| 降级策略 | 不支持 Highlight API 时引擎不激活，复制退化为全文兜底 | 避免两套选中路径并存；项目部署于局域网 Win 桌面 Chrome/Edge，降级场景极少 |
| 命中计算 | `caretPositionFromPoint`（标准）优先，`caretRangeFromPoint`（Chromium 遗留）兜底，统一归一为 `{node, offset}` | 兼容不同浏览器 API 差异；offsetNode 可能是 Element（命中 img），建 Range 前做 nodeType/包含校验 |
| 选中范围 | 起始容器内 clamp（不支持跨气泡拖选） | 对齐需求「气泡内精准选中」；全局同一时刻唯一选中 |

## 分步实施清单

### 1. `frontend/src/style.css` — 禁用原生选区 + 高亮样式

```css
/* 聊天消息区禁用浏览器原生选择（自定义选区引擎接管） */
.msgs, .msgs * { user-select: none; -webkit-user-select: none; }
/* 自定义选中高亮：主色透底，入/出方向气泡通吃 */
::highlight(chat-text-sel) { background-color: rgba(29, 93, 228, .28); }
```

### 2. 新建 `frontend/src/utils/textSelection.js` — 选区引擎（模块级单例）

导出接口：

```js
isSupported()                        // typeof Highlight !== 'undefined' && !!CSS.highlights
onTextMouseDown(e, msgId)            // MessageRow 文本容器 mousedown 入口：button===0 才处理
onTextDblClick(e, msgId)             // 双击选词
attachTextSelection() / detachTextSelection()   // ChatPanel 生命周期：document 级 Esc/blur；
                                     // mousemove/mouseup 仅拖动期间临时挂载（避免全局常驻开销）
getSelectionState()                  // → { msgId, text, range, containerEl } | null（内部校验 isConnected）
clearSelection()                     // 清状态 + CSS.highlights.delete('chat-text-sel')
copyFragmentOf(msgId)                // 右键复制取值：选中归属该 msg 才返回片段文本，否则空串
```

内部要点：

- **拖动状态机**：空闲 →（mousedown 命中文本容器）→ 记录 anchor caret →（mousemove）→ 终点 caret 构造 Range，`setStart/setEnd` 按 document order 排序，clamp 在起始容器文本首尾 → 实时 `CSS.highlights.set('chat-text-sel', new Highlight(range))` →（mouseup）定型并快照 `text`
- **点击 vs 拖动**：mouseup 时位移 < 3px 视为纯点击 → 清除选中；位移达标才形成选中（需求 4：仅主动拖动产生高亮）
- **双击选词**：`wordRangeAt(text, offset)` 纯函数：连续 `[A-Za-z0-9_]` 或连续 CJK 字符扩展为词；英文单词/编号型号（如 `WDCDA5HB3DA250327`）整段选中，符合业务查件号习惯
- **文本提取** `extractRangeText(range)`：遍历 `range.cloneContents()`，文本节点直接取；`img.wx-emoji` 读 `alt` 还原为 `[微笑]` 码（alt 已含方括号，勿再包裹）——**比原生 toString 更优，表情码不丢失**；`span.msg-mention`（@提及）内是普通文本节点，直接取
- **caret 封装** `caretFromPoint(x, y)`：优先 `caretPositionFromPoint`（返回 `{offsetNode, offset}`，offsetNode 可能是 Element，offset 为子节点索引，`setStart` 合法）；退化 `caretRangeFromPoint`（取 startContainer/startOffset）；命中 Element（img）时夹到相邻文本边界，emoji 作为原子段整体选中/取消
- **失效自愈**：`getSelectionState()` 每次读取校验 `containerEl.isConnected`，失效自动清空（防 Range 悬挂引用）

### 3. `frontend/src/components/MessageRow.vue` — 接入引擎

- 三处文本容器绑定事件（`selectable`（多选模式）短路，不激活拖选）：
  - L261 引用回复 `.content`：`@mousedown="onTextDown($event)"` `@dblclick="onTextDbl($event)"`
  - L281 引用名称 `.q-text`
  - L326 正文 `.content`
- `onMenu`（L180-189）移除 `selectedTextWithin` 快照，恢复为只 emit `{ msg, x, y }`（选中归属判断改由 ChatPanel 用 msg.id 对比引擎状态）
- 移除 `import { selectedTextWithin } from '../utils/selection'`

### 4. `frontend/src/components/ChatPanel.vue` — 分发与生命周期

- `onMounted` / `onUnmounted`：`attachTextSelection()` / `detachTextSelection()`
- `watch(() => chat.currentId)` → `clearSelection()`（切会话 `.msgs :key` 重建 DOM，Range 必失效）
- `enterMulti()` → `clearSelection()`（多选模式与文本拖选互斥）
- `onMenuSelect` 复制分支（L226-227）改为：

```js
await copyText(copyFragmentOf(m.id) || msgTextOf(m))
ElMessage.success('已复制')
// 片段复制成功后 clearSelection()（对齐原生复制后选区消失的习惯）；全文兜底不清
```

### 5. `frontend/tests/utils/selection.test.js` → 改写为 `textSelection.test.js`

纯 node 环境（注入 fake 节点/段序列，与现有测试风格一致）：

- `wordRangeAt`：英文词边界、行首/行尾、CJK 连续串、中英混合、offset 落空白、越界 offset
- `extractRangeText`：纯文本段、emoji 段还原 alt 码、多段拼接、空 range
- `copyFragmentOf`：msgId 匹配返回片段、不匹配返回空串
- 有效性校验：isConnected=false → null（走全文兜底）

### 6. 删除 `frontend/src/utils/selection.js`（上一轮的原生选区快照实现，被引擎完全替代）

## 交互规则总表（边界场景处理）

| 场景 | 行为 |
|---|---|
| 在文本区域拖动 | 产生自定义高亮，clamp 在起始气泡容器内（跨行原生支持） |
| 纯点击文本区域（<3px） | 清除已有选中 |
| 点击气泡非文本区域（padding/头像/空白/卡片） | **保留**已有选中（解决痛点 A） |
| 双击 | 选词（英文词/连续数字/CJK 连续串） |
| 右键有选中的气泡 | 菜单「复制」= 选中片段，复制后清除选中 |
| 右键无选中的气泡 / 右键其他气泡 | 复制该气泡全文（兜底，不清除已有选中） |
| 右键拖选中（只按右键无拖动） | 选中保持，不清除（mousedown 只认左键） |
| Esc | 清除选中（菜单关闭逻辑在 ContextMenu，互不冲突） |
| 切会话 / 进入多选模式 | 清除选中 |
| 上翻加载历史消息 | v-for :key 复用节点，Range 仍有效（复制用快照文本，不依赖 Range） |
| 拖出窗口 / window blur | 冻结最后有效端点，强制定型 |
| 气泡内无文本（图片/语音/表情大图） | 引擎不激活，右键走原有复制图片/置灰逻辑，行为不变 |
| 不支持 Highlight API | 引擎不激活，仅全文复制（可接受的降级） |
| emoji 在选中范围内 | 复制还原为 `[微笑]` 码 |

## 验证方案

1. **单测**：`cd frontend && npm test`——textSelection 新用例全过；现有其余测试不回归（mention.test.js 存量 1 个失败与本次无关）
2. **浏览器自验**（用户自行操作，dev server 由用户管理）：
   - 无选中右键复制 → 全文
   - 拖选部分文本（单行/跨行）→ 高亮出现 → 右键复制 → 仅片段
   - 选中文本后点击气泡 padding/头像 → 高亮保留；点击文本 → 高亮消失
   - 双击选词（件号 `WDCDA5HB3DA250327`、中文串）→ 右键复制 → 词被复制
   - 含表情消息拖选 → 复制含 `[微笑]` 码
   - 右键期间选中保持；复制后选中清除
   - 多选模式（多选/转发）下拖选不激活；退出后恢复
   - 引用消息：回复正文与引用块均可拖选
3. **提交**：按规范 `feat:` 单独提交（重构不涉及）

## 明确不做（防止范围蔓延）

- 不支持跨气泡拖选（需求限定气泡内精准选中）
- 不在合并转发回看（ForwardRecord，不复用 MessageRow）落地此能力
- 不做触屏/移动端适配（桌面端业务）
- 不做拖动中的滚动边缘自动滚动（v1 不需要，上翻加载已覆盖长会话场景）
