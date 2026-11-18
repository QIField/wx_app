# 快捷报价模块重构变更说明

- 日期：2026-11-18
- 范围：提交 `3ab4fed` 以来快捷报价模块全部变更文件
- 性质：`refactor`，不改变业务功能逻辑与对外接口契约（路由、出参结构、状态机、错误码均不变）

## 一、待重构文件清单梳理结论

对 `3ab4fed..HEAD` 涉及的 36 个变更文件做了行数与函数长度审计：

- 文件行数全部 ≤ 400 行规范上限（最大 `backend/services/quote_pricing.py` 313 行、`frontend/src/components/right/SettingsView.vue` 286 行）；
- 全部函数 ≤ 80 行；
- `frontend/src/api/index.js` 222 行，未超限，**无需拆分**。

因此本次重构聚焦：重复逻辑消除、边界缺陷修复、执行效率与可读性优化，而非结构拆分。

## 二、调整内容与优化点

### 后端

| 文件 | 调整 | 类型 |
| --- | --- | --- |
| `backend/api/quote_query.py` | 5 个端点各自重复的 `取参 → 判空 → 400` / `try → 502` 样板收敛为 `_require()` 助手 + `_query_endpoint` 装饰器统一错误映射（缺参 400 / 编排失败与上游异常 502）；错误响应文案统一为异常原文 | 消除重复逻辑 |
| `backend/api/quote_stats.py` | `_aggregate` 分桶由逐行 `next()` 线性扫描桶（O(n×buckets)）改为 `bisect` 二分定位（O(n×log buckets)），桶升序不重叠前提成立 | 执行效率 |

### 前端

| 文件 | 调整 | 类型 |
| --- | --- | --- |
| `frontend/src/utils/quoteQuery.js` | 新增纯函数 `ts2date()`（秒级时间戳 → 本地日期）与 `fmtValue()`（空值兜底 '-'），供比价/采购历史表格共用 | 消除重复逻辑 |
| `frontend/src/components/right/ManualHistory.vue` | **修复边界缺陷**：原 `ts2date` 用 `toISOString().slice(0,10)` 按 UTC 取日期，中国时区 UTC+8 下 0~8 点的采购记录日期会显示为前一天；改用 utils 本地日期实现 | Bug 修复 |
| `frontend/src/components/right/ManualThirdParty.vue` / `ManualHistory.vue` | 各自内联的 `fmt` 空值兜底函数收敛为 utils `fmtValue` | 消除重复逻辑 |
| `frontend/src/components/right/AnalysisView.vue` | 删除 `cols` 计算属性中从未渲染的 vin 柱数据（死代码，VIN 仅进 KPI）；注释同步说明 | 消除冗余代码 |
| `frontend/src/composables/useQuoteConfig.js`（新增） | 抽取自动报价视图与设置视图重复的 `GET /quote/config` 回填逻辑（`ai_enabled !== false` / `quote_mode \|\| 'preview'` 映射与默认值），扩展字段经 `onLoaded` 回调回填；容错语义仍由各视图自定 | 消除重复逻辑 |
| `frontend/src/components/right/AutoFeedView.vue` / `SettingsView.vue` | 接入 `useQuoteConfig`；SettingsView 变量重命名 `aiEnabled→aiOn` 与公共契约统一 | 消除重复逻辑 |
| `frontend/src/style.css` | 新增「快捷报价面板公共样式」段（`qq-` 前缀隔离）：`qq-box / qq-row / qq-input / qq-btn-primary / qq-btn-sm / qq-skel / qq-empty / qq-table / qq-switch / qq-badge` | 消除重复逻辑 |
| `right/` 9 个组件 | scoped CSS 中逐字重复的查询卡/输入框/主按钮/小按钮/加载骨架/空态/数据表/开关/徽章样式迁移至公共类，组件内只保留差异覆盖（如 ThirdParty「最低」实底绿徽章、QuoteResultCard 定宽改价输入框、ManualView 查询卡去 margin） | 消除重复逻辑 |

**有意统一的视觉微差**（此前各组件 ±1~2px 漂移，已在 style.css 注释标注）：

- 输入框 padding 统一 `6px 9px`，统一 focus 光晕与 placeholder 灰色；
- 主按钮 padding 统一 `6px 14px`；
- 空态 padding 统一 `22px 10px`；
- 徽章公共类不带外边距，间距由使用处控制。

### 注释同步

- `quote_query.py` 模块 docstring 改为描述统一错误映射；
- `_aggregate`、`ts2date`、`useQuoteConfig`、qq-* 公共样式段均补齐意图说明；
- `AnalysisView.vue` 的 cols 注释说明 VIN 仅进 KPI 不出柱。

## 三、文件范围

新增：

- `frontend/src/composables/useQuoteConfig.js`
- `docs/refactor-quick-quote-20261118.md`

修改：

- 后端：`backend/api/quote_query.py`、`backend/api/quote_stats.py`
- 前端：`frontend/src/style.css`、`frontend/src/utils/quoteQuery.js`、
  `frontend/tests/utils/quoteQuery.test.js`、
  `frontend/src/components/right/{ManualView,ManualAiChat,ManualThirdParty,ManualHistory,QuoteResultCard,AnalysisView,SettingsView,AutoFeedView}.vue`

未改动（审计后确认无需重构）：其余全部范围内文件，含 `backend/services/*`、`backend/api/quote_{config,inquiry}.py`、`frontend/src/api/index.js` 等。

## 四、验证结果

| 验证项 | 结果 |
| --- | --- |
| 后端全量 pytest | 472 passed, 1 skipped（与重构前基线一致；全量跑时 `test_message_sync` teardown 偶现 SQLite 锁 error，经 stash 基线对照确认为存量问题，与本次重构无关） |
| 前端全量 vitest | 94 passed / 1 failed——失败项为存量 `mention.test.js`（重构前即失败，不在范围）；本次新增 ts2date/fmtValue 用例全过（含深夜 23:30 不偏移用例） |
| 前端生产构建 `npm run build` | 通过（19.6s） |
| 浏览器端到端 | 4 视图渲染/切换正常、无卡死 spinner；报价分析 KPI/趋势/TOP 正常加载（day 15 桶 / month 10 桶），日/月切换正常；`/api/quote/stats` 真实出参冒烟通过 |
