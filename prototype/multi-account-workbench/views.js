/* ===== views.js · 纯渲染函数（HTML 字符串）+ 图标 + 小工具 ===== */
window.V = (() => {
  const I = {
    chat: '<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/>',
    users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    send: '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
    file: '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/>',
    x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/>',
    back: '<path d="m15 18-6-6 6-6"/>',
    user: '<circle cx="12" cy="8" r="5"/><path d="M20 21a8 8 0 0 0-16 0"/>',
    clock: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    close: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    alert: '<circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/>',
    inbox: '<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
    pin: '<path d="M12 17v5"/><path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V6h1a2 2 0 0 0 0-4H8a2 2 0 0 0 0 4h1z"/>',
    'bell-off': '<path d="M13.73 21a2 2 0 0 1-3.46 0"/><path d="M18.63 13A17.89 17.89 0 0 1 18 8"/><path d="M6.26 6.26A5.86 5.86 0 0 0 6 8c0 7-3 9-3 9h14"/><path d="M18 8a6 6 0 0 0-9.33-5"/><line x1="1" y1="1" x2="23" y2="23"/>',
    check: '<polyline points="20 6 9 17 4 12"/>',
  };
  const icon = (name, s = 16, sw = 1.8) =>
    `<svg viewBox="0 0 24 24" width="${s}" height="${s}" fill="none" stroke="currentColor" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round">${I[name]}</svg>`;

  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const hm = (t) => (t || '').slice(11, 16);
  const ini = (n) => (n || '?').trim().slice(0, 1);
  const PALETTE = ['#1d5de4', '#0e9888', '#c2611f', '#7a5af5', '#b3325c', '#2f7f3f'];
  const hashColor = (n) => PALETTE[[...(n || '')].reduce((a, c) => a + c.charCodeAt(0), 0) % PALETTE.length];
  const dev = (openid) => window.MOCK.devices.find((d) => d.openid === openid);
  const avatar = (name, cls = '') => `<div class="avatar ${cls}" style="background:${hashColor(name)}">${esc(ini(name))}</div>`;

  const ROLE_TEXT = { developer: '开发者', admin: '管理员', agent: '客服' };

  /* ---------- 顶栏右侧（按视图） ---------- */
  function topbarRight(view, S) {
    const me = S.state.me;
    if (view === 'login') {
      return `<span class="status"><span class="dot"></span>多账号绑定 · 演示环境</span>`;
    }
    const chip = `
      <div class="user-chip">
        <div class="user-avatar num">${esc(ini(me.name))}</div>
        <div class="user-meta"><span class="user-name">${esc(me.name)}</span><span class="user-role">${ROLE_TEXT[me.role] || me.role}</span></div>
        <button class="icon-btn" data-action="logout" title="退出登录" aria-label="退出登录">${icon('logout', 15)}</button>
      </div>`;
    if (view === 'logs') {
      return `<button class="icon-btn" data-action="back-workbench">${icon('back', 14)}<span>返回工作台</span></button>${chip}`;
    }
    /* workbench：发送日志 / 审计入口（账号卡片在顶栏左侧） */
    const allOnline = S.state.myDevices.every((d) => dev(d).online);
    return `
      <button class="icon-btn" data-action="open-logs" title="发送日志（谁发的可溯源）">${icon('file', 14)}<span>发送日志</span></button>
      <button class="icon-btn" data-action="logs-page" title="审计视角·全量日志">${icon('search', 14)}<span>审计</span></button>
      <span class="status ${allOnline ? '' : 'off'}"><span class="dot"></span>${S.state.myDevices.length} 个账号${allOnline ? '在线' : '部分离线'}</span>
      ${chip}`;
  }

  /* ---------- 登录 ---------- */
  function login() {
    return `
    <div class="picker-wrap"><div class="picker rise" style="max-width:460px">
      <div class="picker-head">
        <h1>登录 SI 客服系统</h1>
        <p>一个系统账号可绑定多个聊天账号，数据相互隔离</p>
      </div>
      <div style="display:flex;flex-direction:column;gap:10px">
        <label style="font-size:12px;color:var(--c-text-sub)">登录账号</label>
        <input id="login-user" value="cs01" autocomplete="off"
          style="border:1px solid var(--c-border-strong);border-radius:6px;padding:10px 12px;font-size:13px;outline:none" />
        <label style="font-size:12px;color:var(--c-text-sub)">密码</label>
        <input id="login-pass" type="password" value="123456"
          style="border:1px solid var(--c-border-strong);border-radius:6px;padding:10px 12px;font-size:13px;outline:none" />
        <button class="btn" data-action="do-login" style="margin-top:6px">登 录</button>
      </div>
      <div style="margin-top:18px;border-top:1px dashed var(--c-border);padding-top:12px">
        <div style="font-size:11px;color:var(--c-text-sub);margin-bottom:8px">演示账号（点击直登）</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <button class="btn ghost" data-action="quick-login" data-user="cs01">吴桐 · 3 个聊天账号</button>
          <button class="btn ghost" data-action="quick-login" data-user="cs02">李杉 · 1 个聊天账号</button>
        </div>
      </div>
    </div></div>`;
  }

  /* ---------- 顶栏账号卡片（v4：标题右侧；显示账号名称/消息数/设备状态，点击切换） ---------- */
  function accountCards(S) {
    return S.state.myDevices.map((openid) => {
      const d = dev(openid);
      const unread = S.deviceBadge(openid);
      return `
      <button class="acc-card ${S.state.scope === openid ? 'on' : ''} ${d.online ? '' : 'off'}"
        data-action="set-scope" data-scope="${openid}" title="${esc(d.wxid)} · ${d.online ? '设备在线' : '设备离线'}">
        <span class="a-avatar" style="background:${d.color}">${esc(ini(d.nickname))}<span class="a-dot ${d.online ? '' : 'a-dot-off'}"></span></span>
        <span class="a-meta">
          <span class="a-name">${esc(d.nickname)}</span>
          <span class="a-status"><span class="st ${d.online ? 'st-on' : 'st-off'}"></span>${d.online ? '设备在线' : '设备离线'}</span>
        </span>
        ${unread ? `<span class="a-badge" title="未读消息 ${unread} 条">${unread > 99 ? '99+' : unread}</span>` : ''}
      </button>`;
    }).join('');
  }

  /* ---------- 会话列表（微信风格：搜索框 + 会话/联系人搜索） ---------- */
  /* 命中词高亮（大小写不敏感，首处命中） */
  function hilite(text, kw) {
    const s = String(text || '');
    const idx = s.toLowerCase().indexOf(kw.toLowerCase());
    if (!kw || idx < 0) return esc(s);
    return esc(s.slice(0, idx)) + '<mark>' + esc(s.slice(idx, idx + kw.length)) + '</mark>' + esc(s.slice(idx + kw.length));
  }

  /* 搜索结果：联系人组（通讯录）+ 会话组（会话名/最后一条消息命中） */
  function searchResults(S, kw) {
    const scope = S.state.scope;
    const ctRows = S.state.contacts
      .filter((ct) => ct.openid === scope)
      .filter((ct) => [ct.name, ct.wxid, ct.remark].some((f) => (f || '').toLowerCase().includes(kw)))
      .map((ct) => {
        const conv = S.state.conversations.find((c) => c.openid === ct.openid && c.wxid === ct.wxid && c.chat_type === 1);
        return `
        <div class="s-row" data-action="${conv ? 'search-open-conv' : 'search-open-contact'}" ${conv ? `data-id="${conv.id}"` : `data-name="${esc(ct.name)}"`} role="button" tabindex="0">
          ${avatar(ct.name)}
          <div class="s-main">
            <div class="s-name">${hilite(ct.name, kw)}</div>
            <div class="s-sub">${hilite(ct.wxid + (ct.remark ? ' · 备注 ' + ct.remark : ''), kw)}</div>
          </div>
          ${conv ? '' : '<span class="tag">无会话</span>'}
        </div>`;
      }).join('');
    const cvRows = S.state.conversations
      .filter((c) => c.openid === scope)
      .filter((c) => (c.name.toLowerCase().includes(kw) || (c.last_msg || '').toLowerCase().includes(kw)))
      .map((c) => `
      <div class="s-row" data-action="search-open-conv" data-id="${c.id}" role="button" tabindex="0">
        ${avatar(c.name)}
        <div class="s-main">
          <div class="s-name">${hilite(c.name, kw)}</div>
          <div class="s-sub">${hilite(c.last_msg || '', kw)}</div>
        </div>
        ${c.unread_count ? `<span class="badge num">${c.unread_count}</span>` : ''}
      </div>`).join('');
    return `
      ${ctRows ? `<div class="s-group">联系人</div>${ctRows}` : ''}
      ${cvRows ? `<div class="s-group">会话</div>${cvRows}` : ''}
      ${(!ctRows && !cvRows) ? `<div class="empty">${icon('search', 26)}无搜索结果</div>` : ''}`;
  }

  /* 默认会话列表（无关键词）。v6：pinned 只做背景加深不显示文字；muted 显示铃铛斜杠 + 未读变红点 */
  function convResults(S) {
    const openids = S.scopeOpenids();
    const rows = S.state.conversations
      .filter((c) => openids.includes(c.openid))
      .sort((a, b) => b.pinned - a.pinned || String(b.last_msg_at).localeCompare(String(a.last_msg_at)));
    const items = rows.map((c) => {
      const on = S.state.activeConvId === c.id;
      return `
      <div class="conv-item ${on ? 'on' : ''} ${c.pinned ? 'pinned' : ''} ${c.unread_count ? 'unread' : ''}"
        data-action="open-conv" data-id="${c.id}" role="button" tabindex="0">
        ${avatar(c.name)}
        <div class="c-main">
          <div class="c-top"><span class="c-name">${esc(c.name)}</span><span class="c-time num">${hm(c.last_msg_at)}</span></div>
          <div class="c-sub">
            <span class="c-last">${esc(c.last_msg || '')}</span>
            ${c.muted ? `<span class="c-mute" title="消息免打扰">${icon('bell-off', 12)}</span>` : ''}
            ${c.unread_count ? `<span class="badge num ${c.muted ? 'dot' : ''}" title="未读 ${c.unread_count} 条">${c.unread_count}</span>` : ''}
          </div>
        </div>
      </div>`;
    }).join('');
    return items || `<div class="empty">${icon('inbox', 28)}当前账号暂无会话</div>`;
  }

  function convList(S) {
    const head = `
      <div class="side-head search-head">
        <div class="search-box">
          ${icon('search', 13)}
          <input id="conv-search" type="text" placeholder="搜索" value="${esc(S.state.searchQuery)}" autocomplete="off" />
          ${S.state.searchQuery ? `<button class="s-clear" data-action="search-clear" title="清空搜索">${icon('close', 11)}</button>` : ''}
        </div>
      </div>`;
    const kw = S.state.searchQuery.trim().toLowerCase();
    return head + `<div class="conv-list" id="search-results">${kw ? searchResults(S, kw) : convResults(S)}</div>`;
  }

  /* v6 右键菜单（微信 PC 同构）：置顶文字切换 / 未读状态切换 / 免打扰勾选 */
  function convMenu(c, x, y) {
    return `
    <div class="ctx-menu" style="left:${x}px;top:${y}px" role="menu" aria-label="会话操作">
      <button class="ctx-item" data-action="ctx-pin" data-id="${c.id}" role="menuitem">
        ${icon('pin', 14)}<span>${c.pinned ? '取消置顶' : '置顶'}</span>
      </button>
      <button class="ctx-item" data-action="ctx-unread" data-id="${c.id}" role="menuitem">
        ${icon('check', 14)}<span>${c.unread_count ? '标为已读' : '标为未读'}</span>
      </button>
      <div class="ctx-sep"></div>
      <button class="ctx-item" data-action="ctx-mute" data-id="${c.id}" role="menuitemradio" aria-checked="${!!c.muted}">
        ${icon('bell-off', 14)}<span>消息免打扰</span>${c.muted ? `<span class="ctx-check">${icon('check', 13)}</span>` : ''}
      </button>
    </div>`;
  }

  /* ---------- 聊天窗 ---------- */
  function chat(S) {
    const conv = S.conv(S.state.activeConvId);
    if (!conv) return `<div class="empty" style="flex:1">${icon('chat', 32)}选择左侧会话开始沟通</div>`;
    const d = dev(conv.openid);
    const msgs = S.state.messagesByConv[conv.id] || [];
    const rows = msgs.map((msg) => {
      const out = msg.dir === 2;
      const opChip = out && msg.operator
        ? `<span class="op-chip" title="系统账号溯源：${esc(msg.operator.username)}">${icon('user', 10)}${esc(msg.operator.name)}</span>` : '';
      const status = out && msg.status === 0
        ? `<span class="b-status">${icon('clock', 10)} 发送中</span>` : '';
      const meta = `<div class="b-meta num">${hm(msg.time)}${msg.msg_type === 1 ? '' : ' · 附件'}${status}</div>`;
      const sub = msg.dir === 2 ? '' : `<div class="b-meta">${esc(msg.sender_name || '')} · ${hm(msg.time)}</div>`;
      return `
      <div class="msg-row ${out ? 'out' : 'in'}">
        <div class="msg-avatar" style="background:${out ? 'var(--c-primary)' : hashColor(msg.sender_name)}">${esc(ini(out ? msg.sender_name : msg.sender_name))}</div>
        <div class="bubble">
          ${opChip}
          <div class="b-text">${esc(msg.content)}</div>
          ${out ? meta : sub}
        </div>
      </div>`;
    }).join('');
    return `
    <div class="chat-head">
      ${avatar(conv.name)}
      <div style="flex:1;min-width:0">
        <div class="ch-name">${esc(conv.name)}${conv.chat_type === 2 ? ' <span class="tag">群聊</span>' : ''}</div>
        <div class="ch-sub">
          <span>${d.wxid}</span>
        </div>
      </div>
      <button class="btn ghost" data-action="open-logs" style="padding:5px 10px;font-size:12px">${icon('file', 13)} 本会话发送记录</button>
    </div>
    <div class="chat-body" id="chat-body">${rows}</div>
    <div class="chat-input">
      <div class="ci-tools">
        <button class="tool" title="表情（演示）">${icon('chat', 15)}</button>
        <button class="tool" title="图片（演示）">${icon('file', 15)}</button>
        <span style="font-size:11px;align-self:center;margin-left:4px;color:var(--c-text-sub)">发送将以 <b>${esc(S.state.me.name)}（${esc(S.state.me.username)}）</b> 身份记入发送日志</span>
      </div>
      <div class="ci-row">
        <textarea id="ci-text" placeholder="输入消息，Enter 发送…" data-enter="send"></textarea>
        <button class="btn" data-action="send">${icon('send', 15)} 发送</button>
      </div>
    </div>`;
  }

  function workbench(S) {
    return `
    <div class="layout">
      <div class="side-unit">
        <nav class="rail">
          <button class="rail-btn on" title="会话">${icon('chat', 19)}${S.railUnread() ? `<span class="badge num">${S.railUnread()}</span>` : ''}</button>
          <button class="rail-btn" title="通讯录（演示）">${icon('users', 19)}</button>
        </nav>
        <aside class="col-side">
          <div id="conv-list">${convList(S)}</div>
        </aside>
      </div>
      <main class="col-main"><div id="chat-zone" style="display:flex;flex-direction:column;flex:1;min-height:0">${chat(S)}</div></main>
    </div>`;
  }

  /* ---------- 发送日志抽屉 ---------- */
  function drawer(S, f) {
    const me = S.state.me;
    const logs = S.state.logs.filter((l) =>
      (f.op === 'all' || l.operator_username === f.op) &&
      (f.dev === 'all' || l.device === f.dev) &&
      (f.result === 'all' || l.result === f.result));
    const rows = logs.map((l) => `
      <div class="log-row">
        <div class="l-time num">${hm(l.time)}</div>
        <div class="l-main">
          <div class="l-line1">
            <span class="l-op">${esc(l.operator_name)}（${esc(l.operator_username)}）</span>
            <span class="l-act">${esc(l.action)}</span>
            <span class="l-result ${l.result === '已发送' ? 'ok' : 'fail'}">${esc(l.result)}</span>
          </div>
          <div class="l-content">${esc(l.content)}</div>
          <div class="l-meta">
            <span class="dev-tag" style="--dc:${(MOCK.devices.find((d) => d.nickname === l.device) || {}).color || '#6b7a93'}"><i></i><span>${esc(l.device)}</span></span>
            <span>会话：${esc(l.conv_name)}</span>
          </div>
        </div>
      </div>`).join('');
    const devOpts = [...new Set(MOCK.devices.map((d) => d.nickname))].map((n) => `<option value="${n}" ${f.dev === n ? 'selected' : ''}>${n}</option>`).join('');
    return `
    <div class="drawer-mask" data-action="close-logs"></div>
    <aside class="drawer" role="dialog" aria-label="发送日志">
      <div class="drawer-head">
        <h3>发送日志 · 溯源</h3>
        <span class="tag">${icon('user', 11)}当前操作人：${esc(me.name)}</span>
        <button class="icon-btn" style="border-color:var(--c-border-strong);background:#fff;color:var(--c-text)" data-action="close-logs">${icon('x', 14)}</button>
      </div>
      <div class="drawer-filters">
        <select data-filter="op">
          <option value="all" ${f.op === 'all' ? 'selected' : ''}>全部操作人</option>
          ${MOCK.users.filter((u) => u.role === 'agent').map((u) => `<option value="${u.username}" ${f.op === u.username ? 'selected' : ''}>${u.name}（${u.username}）</option>`).join('')}
        </select>
        <select data-filter="dev"><option value="all" ${f.dev === 'all' ? 'selected' : ''}>全部聊天账号</option>${devOpts}</select>
        <select data-filter="result">
          <option value="all" ${f.result === 'all' ? 'selected' : ''}>全部结果</option>
          <option value="已发送" ${f.result === '已发送' ? 'selected' : ''}>已发送</option>
          <option value="失败" ${f.result === '失败' ? 'selected' : ''}>失败</option>
        </select>
      </div>
      <div class="drawer-body">${rows || `<div class="empty">${icon('inbox', 28)}没有符合筛选的发送记录</div>`}</div>
    </aside>`;
  }

  /* ---------- 审计日志页 ---------- */
  function logsPage(S) {
    const logs = S.state.logs;
    const rows = logs.map((l) => `
      <tr>
        <td class="num">${esc(l.time)}</td>
        <td class="t-op">${esc(l.operator_name)}<div style="font-weight:400;color:var(--c-text-sub);font-size:11px">${esc(l.operator_username)}</div></td>
        <td>${esc(l.device)}</td>
        <td>${esc(l.conv_name)}</td>
        <td>${esc(l.action)}</td>
        <td class="t-content">${esc(l.content)}</td>
        <td><span class="l-result ${l.result === '已发送' ? 'ok' : 'fail'}">${esc(l.result)}</span></td>
      </tr>`).join('');
    return `
    <div class="logs-wrap"><div class="logs-panel rise">
      <div class="logs-head">
        <h2>发送日志 · 全量审计</h2>
        <span class="tag">记录到系统账号级：${esc(S.state.me.name)}（${esc(S.state.me.username)}）</span>
        <span class="tag">共 ${logs.length} 条</span>
      </div>
      <table class="log-table">
        <thead><tr><th>时间</th><th>操作人（系统账号）</th><th>聊天账号</th><th>会话</th><th>动作</th><th>内容</th><th>结果</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div></div>`;
  }

  return { icon, esc, hm, ini, hashColor, dev, avatar, topbarRight, accountCards, login, workbench, convList, convResults, searchResults, convMenu, chat, drawer, logsPage };
})();
