/**
 * API 桩层：签名、时延、出参形态即未来真实接口形态。
 * 接入后端时按 TODO 标注逐个替换为 fetch 调用，前端调用处无需改动。
 *
 * 与项目规范对齐：
 * - 所有删除均为软删除（写 deleted_at），回收站可恢复（见 prototypes/soft-delete 方案）。
 * - 消息接口限流 60 次/分钟、其余 120 次/分钟（backend/services/risk.py 统一入口）。
 */
const delay = (ms = 350) => new Promise((r) => setTimeout(r, ms));

window.API = {
  /**
   * 收藏一条消息
   * TODO: replace with POST /api/favorites  body: { conv_id, msg_id }
   * 出参: { id, type, content, source, time, tags }
   */
  async addFavorite({ convId, msgId }) {
    await delay(280);
    const conv = window.MOCK.conversations.find((c) => c.id === convId);
    const msgs = window.MOCK.messages[convId] || [];
    const msg = msgs.find((m) => m.id === msgId);
    if (!msg) throw new Error('message not found');
    const item = {
      id: 'f' + Date.now(),
      type: 'text',
      content: msg.text || '[消息]',
      source: `${conv ? conv.name : '未知会话'} · ${msg.sender}`,
      time: '刚刚',
      tags: [],
    };
    window.MOCK.favorites.unshift(item);
    return item;
  },

  /**
   * 收藏列表（按类型筛选）
   * TODO: replace with GET /api/favorites?type=all|text|image|voice|link|note
   * 出参: { items } —— 已过滤 deleted_at 非空的行
   */
  async listFavorites(type = 'all') {
    await delay(180);
    const items = window.MOCK.favorites.filter(
      (f) => !f.deleted && (type === 'all' || f.type === type)
    );
    return { items };
  },

  /**
   * 删除收藏（软删除：写 deleted_at，可在回收站恢复）
   * TODO: replace with DELETE /api/favorites/:id（软删除，禁物理删除）
   */
  async deleteFavorite(id) {
    await delay(240);
    const item = window.MOCK.favorites.find((f) => f.id === id);
    if (item) item.deleted = true;
    return { ok: true };
  },

  /**
   * 转发消息到目标会话
   * TODO: replace with POST /api/messages/forward
   * body: { conv_id, msg_ids | fav_id, target_ids, mode: 'single' | 'merge' }
   * - single：逐条转发（每条消息独立、普通气泡送达，非本人消息带原发送者前缀）
   * - merge ：合并转发（打包为一张聊天记录卡片，携带 snapshot 快照）
   */
  async forwardMessages({ convId, msgIds = [], favId = null, targetIds = [], mode = 'single' }) {
    await delay(420);
    const srcConv = window.MOCK.conversations.find((c) => c.id === convId);
    const srcMsgs = (window.MOCK.messages[convId] || []).filter((m) => msgIds.includes(m.id));

    let payloadMsgs = [];          // 进入卡片/逐条的内容单元
    let cardTitle = '';

    if (favId) {
      const fav = window.MOCK.favorites.find((f) => f.id === favId);
      if (!fav) throw new Error('favorite not found');
      payloadMsgs = [{ sender: '收藏', text: fav.content || fav.title || '[收藏内容]' }];
      cardTitle = `「${fav.source.split(' · ')[0]}」的收藏`;
    } else if (mode === 'merge') {
      payloadMsgs = srcMsgs;
      cardTitle = `「${srcConv ? srcConv.name : '会话'}」的聊天记录`;
    } else {
      payloadMsgs = srcMsgs;
    }

    const seq = () => 'fw-' + (window.__fwSeq = (window.__fwSeq || 0) + 1);

    for (const tid of targetIds) {
      const target = window.MOCK.messages[tid] || (window.MOCK.messages[tid] = []);
      if (favId || mode === 'merge') {
        target.push({
          id: seq(),
          dir: 2,
          type: 'forward_card',
          sender: window.MOCK.me.name,
          card: {
            title: cardTitle,
            count: payloadMsgs.length,
            preview: payloadMsgs.slice(0, 2).map((m) => `${m.sender}：${(m.text || '').replace(/\u2005/g, ' ')}`),
            snapshot: payloadMsgs.map((m) => ({ sender: m.sender, text: (m.text || '').replace(/\u2005/g, ' ') })),
          },
        });
      } else {
        // 逐条转发：每条消息独立转发，普通气泡呈现（微信行为一致）。
        // 非本人的消息在气泡内带「原发送者：」前缀，保留出处。
        for (const m of payloadMsgs) {
          const isMine = m.dir === 2 || m.sender === window.MOCK.me.name;
          target.push({
            id: seq(),
            dir: 2,
            type: 'text',
            sender: window.MOCK.me.name,
            text: isMine ? m.text : `${m.sender}：${m.text}`,
          });
        }
      }
      // 同步更新会话列表摘要（真实接口由服务端推送，WebSocket 按 id 幂等）
      const conv = window.MOCK.conversations.find((c) => c.id === tid);
      if (conv) {
        conv.last_msg = '[转发] 聊天记录';
        conv.last_msg_at = '刚刚';
        if (tid !== convId) conv.unread = (conv.unread || 0) + 1;
      }
    }
    return { ok: true, targetIds };
  },

  /**
   * 删除消息（软删除：写 deleted_at，回收站可恢复）
   * TODO: replace with DELETE /api/messages  body: { msg_ids } —— 软删除，禁物理删除
   */
  async deleteMessages(convId, msgIds) {
    await delay(260);
    const msgs = window.MOCK.messages[convId] || [];
    for (const m of msgs) if (msgIds.includes(m.id)) m._deleted = true;
    return { ok: true, count: msgIds.length };
  },
};
