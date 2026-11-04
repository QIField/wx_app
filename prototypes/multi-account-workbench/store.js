/* ===== store.js · 前端状态：me / scope / 未读覆盖层 / 会话与消息缓存 ===== */
window.Store = (() => {
  const state = {
    me: null,
    myDevices: [],        // 当前登录系统账号绑定的聊天账号
    scope: null,          // 当前所在聊天账号 openid（v2：一次只看一个账号，无聚合）
    searchQuery: '',      // 会话搜索关键词（微信风格，仅当前账号范围内）
    conversations: [],
    contacts: [],         // 当前登录人绑定账号的通讯录（按 scope 再过滤）
    messagesByConv: {},   // convId -> messages[]
    activeConvId: null,
    logsOpen: false,      // 发送日志抽屉
    logsFilter: { op: 'all', dev: 'all', result: 'all' },
    incomingIdx: 0,
  };

  const dev = (openid) => window.MOCK.devices.find((d) => d.openid === openid);
  const conv = (id) => state.conversations.find((c) => c.id === id);

  /* v2：一次只看一个聊天账号，scope 恒为单个 openid */
  function scopeOpenids() {
    return state.scope ? [state.scope] : [];
  }

  /* 未读角标：rail 总数 = scope 内会话未读合计 */
  function railUnread() {
    return state.conversations
      .filter((c) => scopeOpenids().includes(c.openid))
      .reduce((n, c) => n + (c.unread_count || 0), 0);
  }

  /* 设备维度的未读（scope 切换器角标 = 该账号下会话未读合计） */
  function deviceBadge(openid) {
    return state.conversations
      .filter((c) => c.openid === openid)
      .reduce((n, c) => n + (c.unread_count || 0), 0);
  }

  return { state, dev, conv, scopeOpenids, railUnread, deviceBadge };
})();
