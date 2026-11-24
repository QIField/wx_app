/* ==========================================================================
   Shared Components & Mock Data — Mutex Protocol Architecture Prototype
   ========================================================================== */

/* ---------- Lucide Icon SVGs (inline, no external deps) ---------- */
const ICONS = {
  layers: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2 2 7l10 5 10-5-10-5z"/><path d="m2 17 10 5 10-5"/><path d="m2 12 10 5 10-5"/></svg>`,
  gitBranch: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><line x1="6" x2="6" y1="3" y2="15"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/></svg>`,
  code2: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2"/><path d="m9 8-4 4 4 4"/><path d="m15 8 4 4-4 4"/></svg>`,
  checkCircle: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`,
  link2: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 17H7A5 5 0 0 1 7 7h2"/><path d="M15 7h2a5 5 0 0 1 0 10h-2"/><line x1="8" x2="16" y1="12" y2="12"/></svg>`,
  shield: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/></svg>`,
  activity: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>`,
  cpu: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect width="16" height="16" x="4" y="4" rx="2"/><rect width="6" height="6" x="9" y="9" rx="1"/><path d="M15 2v2"/><path d="M15 20v2"/><path d="M2 15h2"/><path d="M2 9h2"/><path d="M20 15h2"/><path d="M20 9h2"/><path d="M9 2v2"/><path d="M9 20v2"/></svg>`,
  search: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>`,
  zap: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>`,
};

/* ---------- Navigation Shell ---------- */
function renderNav(activePage) {
  const navItems = [
    { label: "架构总览", icon: ICONS.layers, href: "index.html", key: "overview" },
    { label: "核心流程", icon: ICONS.gitBranch, href: "sequence.html", key: "sequence" },
    { label: "接口定义", icon: ICONS.code2, href: "api.html", key: "api" },
    { label: "异常处理", icon: ICONS.shield, href: "error.html", key: "error" },
    { label: "测试方案", icon: ICONS.checkCircle, href: "testing.html", key: "testing" },
  ];
  return `
    <nav class="app-nav">
      <div class="nav-brand">
        <div class="nav-brand-logo">
          ${ICONS.shield}
          <span>MUTEX<br/>PROTOCOL</span>
        </div>
        <div class="nav-brand-sub">互斥控制插件 · v1.0</div>
      </div>
      <div class="nav-section">
        <div class="nav-section-label">架构文档</div>
        <ul class="nav-list">
          ${navItems.map(item => `
            <li>
              <a href="${item.href}" class="nav-link ${activePage === item.key ? 'active' : ''}" data-nav="${item.key}">
                ${item.icon}
                <span>${item.label}</span>
              </a>
            </li>
          `).join('')}
        </ul>
      </div>
      <div class="nav-footer">
        BACKEND · PYTHON · FLASK<br/>
        低侵入 · 零 downtime
      </div>
    </nav>
  `;
}

/* ---------- Page Shell Wrapper ---------- */
function createPage(activePage, title, subtitle, contentHTML) {
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>${title} · Mutex Protocol</title>
  <link rel="stylesheet" href="styles.css" />
</head>
<body data-page="${activePage}">
  <div class="app-wrapper">
    ${renderNav(activePage)}
    <main class="app-content">
      <header>
        <h1>${title}</h1>
        <div class="subtitle">${subtitle}</div>
      </header>
      ${contentHTML}
    </main>
  </div>
  <script src="components.js"></script>
</body>
</html>`;
}

/* ---------- Mock Data ---------- */
const MOCK_DEVICES = [
  { id: "DEV-001", name: "销售-张伟", openid: "wxid_device_zhang_01", online: true },
  { id: "DEV-002", name: "销售-李娜", openid: "wxid_device_li_02",   online: true },
  { id: "DEV-003", name: "销售-王强", openid: "wxid_device_wang_03", online: false },
  { id: "DEV-004", name: "销售-陈芳", openid: "wxid_device_chen_04", online: true },
];

const MOCK_GROUPS = [
  { id: "grp_A", wxid: "xxx_sales_group_01@chatroom", name: "客户询价大群" },
  { id: "grp_B", wxid: "xxx_aftersales_02@chatroom", name: "售后技术群" },
];

const GROUP_CONFIG = {
  "grp_A": {
    leader: "DEV-001",
    followers: ["DEV-002", "DEV-004"],
    lease_expires: "2026-11-24T12:35:00Z",
    config_version: 3,
  },
  "grp_B": {
    leader: null,
    followers: ["DEV-001", "DEV-002"],
    lease_expires: null,
    config_version: 1,
  },
};

/* ---------- Sequence Diagram Mock Steps ---------- */
const SEQUENCE_SCENARIOS = {
  normal: {
    title: "正常报价流程",
    participants: ["设备A (Leader)", "互斥锁插件", "设备B (Follower)", "核心报价引擎"],
    steps: [
      { label: "设备A 收到群消息 → 触发 on_new_message", detail: "消息同步链路照常触发，插件拦截入口" },
      { label: "插件调用 LockManager.check_leader()", detail: "Redis SET NX → A 是群内唯一 Leader → 检查通过" },
      { label: "插件调用 auto_quote.analyze_conversation()", detail: "放行到原有业务逻辑，不做修改" },
      { label: "执行规则提取 + AI 兜底 + dispatch 落表", detail: "核心业务逻辑原样执行，完全无感" },
      { label: "设备B 也收到同一条群消息", detail: "因为同一群消息会被每个设备独立拉取" },
      { label: "B 的插件 check_leader() → 失败", detail: "Redis lock 已被 A 持有 → 返回 NOT_LEADER" },
      { label: "B 静默丢弃消息，不做任何报价", detail: "这就是互斥的核心效果" },
    ],
  },
  election: {
    title: "Leader 离线触发选举",
    participants: ["设备A (原Leader)", "互斥锁插件", "设备B (候选)", "设备C (候选)"],
    steps: [
      { label: "正常运行中：A 是 Leader，锁 TTL=30s，每 10s 续租", detail: "心跳机制保证锁不会意外过期" },
      { label: "设备A 突然离线（网络断了）", detail: "续租心跳停止" },
      { label: "30s 后锁自动过期", detail: "TTL 机制兜底释放" },
      { label: "下一轮消息到达：B 和 C 同时 check_leader()", detail: "B 和 C 都发现 leader 已失效" },
      { label: "B 和 C 同时尝试抢锁 SET NX", detail: "Redis 原子性保证只有一个能成功" },
      { label: "B 抢到锁 → B 成为新 Leader", detail: "SET NX 返回 1，写入 device_id + timestamp" },
      { label: "C 抢锁失败 → C 降级为 Follower", detail: "读取锁的 owner → 发现是 B → 静默" },
      { label: "新 Leader B 开始执行自动报价", detail: "功能无缝切换，0 downtime" },
    ],
  },
  splitbrain: {
    title: "防脑裂：网络分区后恢复",
    participants: ["设备A (分区1)", "互斥锁插件", "设备B (分区2)", "Redis (锁中心)"],
    steps: [
      { label: "A 持有锁，正常工作", detail: "锁内容：{owner: A, term: 5, lease: T1+30s}" },
      { label: "网络分区：A 连不上 Redis", detail: "A 的续租心跳连续 3 次失败" },
      { label: "A 本地判定自己被剥夺 → 降级为被动模式", detail: "A 不再尝试报价，等待分区恢复" },
      { label: "分区内的 B 可以连上 Redis", detail: "锁已过期（TTL 到了）" },
      { label: "B 抢到锁，term=6", detail: "新任期号，epoch 提升" },
      { label: "网络恢复，A 再次连上 Redis", detail: "A 读取锁的 term → 发现自己的 term=5 < 6" },
      { label: "A 识别出脑裂状态 → 立即放弃报价", detail: "即使 A 认为自己还是 Leader，也按较低任期号主动降级" },
    ],
  },
};

/* ---------- Syntax Highlighting (simple) ---------- */
function highlightPython(code) {
  // Very basic Python highlighting
  let html = code
    .replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/("""[\s\S]*?"""|'''[\s\S]*?''')/g, '<span class="tok-str">$1</span>')
    .replace(/#[^\n]*/g, '<span class="tok-comment">$&</span>')
    .replace(/\b(import|from|as|def|class|if|elif|else|try|except|finally|return|with|yield|async|await|for|while|in|not|and|or|is|None|True|False|raise|pass|break|continue|lambda|global|nonlocal)\b/g, '<span class="tok-keyword">$1</span>')
    .replace(/\b(\d+\.?\d*)\b/g, '<span class="tok-num">$1</span>')
    .replace(/\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(/g, '<span class="tok-func">$1</span>(')
    .replace(/@[a-zA-Z_][a-zA-Z0-9_.]*/g, '<span class="tok-decorator">$&</span>')
    .replace(/("[^"]*"|'[^']*')/g, '<span class="tok-str">$1</span>');
  return html;
}

function renderCodeBlock(lang, code, filename) {
  let highlighted = code;
  if (lang === 'python') highlighted = highlightPython(code);
  return `
    <div class="code-block">
      <div class="code-block-header">
        <span class="code-block-lang">${filename || lang}</span>
        <div class="code-block-actions">
          <button class="code-block-btn" onclick="copyCode(this)">COPY</button>
        </div>
      </div>
      <pre><code>${highlighted}</code></pre>
    </div>
  `;
}

function copyCode(btn) {
  const pre = btn.closest('.code-block').querySelector('pre');
  const text = pre.textContent;
  navigator.clipboard?.writeText(text);
  btn.textContent = 'COPIED';
  setTimeout(() => btn.textContent = 'COPY', 1500);
}

/* ---------- Intersection Observer for scroll animations ---------- */
document.addEventListener('DOMContentLoaded', () => {
  // No-op; animations handled by CSS
});
