# Design Contract · 多账号绑定与监控工作台原型

## 需求映射（用户原话 → 原型交互）
1. 每个系统账号可绑定多个聊天账号，账号之间不互通 → user_device 一对多；会话按 openid+wxid 隔离
2. 登录后**默认进入第一个绑定账号**的工作台（v4：无独立卡片页；账号切换控件在顶栏标题右侧）
2a. 顶栏账号卡片：显示**账号名称 + 未读消息数（右上角红点）+ 设备状态（在线/离线）**，点击即切换（v4 修订：用户确认 2026-11-02）
3. 一次只看一个聊天账号，账号严格分开；账号卡片按绑定顺序排列（无「全部」项）；其他账号来消息 → toast + 对应卡片红点，点击卡片切换
4. 发消息做好日志，哪个系统账号发的可溯源 → 消息气泡操作人徽章 + 「发送日志」抽屉（账号·姓名·时间·设备·会话）

## 技术栈与交付
- vanilla HTML + CSS + vanilla JS，pure-static，离线可开（零外部依赖）
- 图标：内联 Lucide SVG；字体：系统栈（Microsoft YaHei / PingFang SC）+ Bahnschrift（数字，Windows 自带）
- 交付：`prototype/multi-account-workbench/`，index.html 单页 3 视图（login / workbench / logs，v4 账号卡片入顶栏）

## Style Tier & Aesthetic
- brand-themed：与现有 Vue 应用「工业配价风」一致——浅灰底、藏青深色顶栏、信号蓝强调、紧凑高密度、锐利小圆角
- tone：克制、高信息密度、工程师审美

## Design Tokens（取自 frontend/src/style.css）
```
--c-bg:#eef1f6  --c-panel:#fff  --c-navy:#14264d  --c-navy-2:#1b3468
--c-primary:#1d5de4  --c-primary-deep:#0f3da8  --c-primary-soft:#e9f0ff
--c-text:#17233a  --c-text-sub:#6b7a93  --c-border:#e3e8f0  --c-border-strong:#c9d2e0
--c-danger:#e5484d  --c-ok:#18a058  --c-warn:#f0821e
--r-sm:4px --r-md:6px --r-lg:10px
font-ui: 'Microsoft YaHei','PingFang SC','Noto Sans SC'  font-num: 'Bahnschrift','DIN Alternate'
字号：12 / 13(正文) / 14 / 16 / 20
```

## 设备配色（多账号区分用，≤4 个）
- 设备A wx_kf01：#1d5de4（信号蓝，主）
- 设备B wx_kf02：#0e9888（青绿）
- 设备C wx_kf03：#c2611f（暖橙）
用于：设备点、标签 chip、角标、账号卡片头像。其余保持中性。

## App Shell（3 视图共用，逐字节一致）
```
body[data-view=login|workbench|logs]
顶栏 .topbar（navy）：左=BrandLogo+SI客服系统+账号卡片组(topbar-accounts)；右=发送日志/审计/状态/用户chip/退出
logs 视图复用同一 topbar（带返回按钮）
main 由 JS 按 data-view 渲染
```
active 规则：账号卡片当前账号加 .on；rail 无导航项（视图由流程推进，非并列导航）

## 视图与职责
| 视图 | 职责 | 关键件 |
|---|---|---|
| login | 登录（演示账号一键切换：吴桐 3 设备 / 李杉 1 设备） | 账号卡、密码框、快捷登录 |
| workbench | 单账号三栏工作台：rail+会话列表 / 聊天窗 / 扩展栏 | **顶栏账号卡片（名称/消息数/设备状态）**、气泡操作人徽章、发送日志抽屉 |
| logs | 发送日志（审计视角）：谁发的·何时·用哪个聊天账号·发给谁 | 筛选（操作人/设备/结果）、表格 |

## Mock Schema
```
users: [{id,username,name,role,devices:[openid,...按绑定顺序]}]
devices 全局表: [{openid,nickname,online,unread}]
conversations: [{id,openid,wxid,chat_type,name,avatar_seed,unread_count,pinned,muted,last_msg,last_msg_at}]
messages: [{id,conv_id,dir(1收/2发),msg_type,sender_name,content,time,status(0/1/2),operator:{username,name}}]
  → dir=2 时 operator 必填（溯源核心）
send_logs: [{id,time,operator_username,operator_name,device_nickname,conv_name,action,content,result}]
```

## 交互清单（v5）
- login→workbench：登录成功按 devices 绑定顺序默认进入第一个聊天账号
- 顶栏账号卡片：只列绑定账号、按绑定顺序、无「全部」项；显示账号名称/未读红点/设备在线离线；点击切换账号
- 跨账号提醒：其他绑定账号来消息 → toast（点击切换）+ 对应账号卡片红点 +1
- ws-sim：定时器每 12~18s 模拟来消息（含当前账号外的绑定账号）
- 发送：回车发送→气泡即时上屏（operator 徽章=当前登录人）+ send_log 记录
- 气泡 hover 显示「发送人 · 时间」；日志抽屉从右侧滑出
- **会话搜索（v5，微信风格）**：「会话」标题删除，列表头部为搜索框（放大镜+占位符「搜索」）；输入即搜，结果分「联系人」（通讯录命中昵称/微信号/备注）与「会话」（命中会话名/最后一条消息）两组，命中词高亮；联系人点击→有会话则打开、无会话提示「无会话」标签；范围仅当前账号（数据隔离），切换账号自动清空搜索
- **会话右键菜单（v6，微信 PC 同构）**：右键会话条目弹出菜单（贴边自动翻转；点击任意处/Esc/滚动/失焦/再次右键收起），三项操作均为本地乐观更新→stub 落库→重排：①置顶⇄取消置顶（文字切换）②标为未读⇄标为已读（按未读状态切换）③消息免打扰（勾选态）。置顶会话仅背景加深（#e9edf4），不显示「置顶」文字，选中态优先；免打扰会话摘要旁显示铃铛斜杠图标，未读徽标退化为小红点（不显数字）
