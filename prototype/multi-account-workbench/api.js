/* ===== api.js · stub 接口层：只 stub 不落真实后端，字段与后端 API 对齐 ===== */
window.API = (() => {
  const D = window.MOCK;
  const delay = (v) => new Promise((r) => setTimeout(() => r(v), 120));
  let sendSeq = 1000; // 发出消息的自增 id（模拟后端 BigIntPK）

  return {
    /* 登录：返回用户 + 绑定的聊天账号列表（改造后 open_id → devices[]） */
    login(username) {
      const u = D.users.find((x) => x.username === username);
      if (!u) return Promise.reject(new Error('账号不存在'));
      return delay({ user: u, devices: D.devices.filter((d) => u.devices.includes(d.openid)) });
    },

    /* 会话列表：按 scope（全部 | 单个 openid）过滤 */
    listConversations(openids) {
      const rows = D.conversations.filter((c) => openids.includes(c.openid));
      return delay(rows);
    },

    /* 会话消息（进入会话时未读清零） */
    listMessages(convId) {
      return delay(D.messages.filter((x) => x.conv_id === convId));
    },

    /* 发送：返回带 operator 的消息（后端将落 operator_id/operator_name） */
    sendMessage({ convId, content, operator, device }) {
      const conv = D.conversations.find((c) => c.id === convId);
      const msg = {
        id: ++sendSeq,
        conv_id: convId, dir: 2, msg_type: 1, sender_name: device.nickname,
        content, time: '2026-11-02 ' + new Date().toTimeString().slice(0, 5),
        status: 0, operator: { username: operator.username, name: operator.name, device: device.openid },
      };
      D.messages.push(msg);
      conv.last_msg = content;
      conv.last_msg_at = msg.time;
      return delay(msg);
    },

    /* 发送日志（含操作人快照，可按操作人/设备/结果筛选） */
    listSendLogs() { return delay(D.send_logs.slice()); },

    /* 记录一条发送日志 */
    appendSendLog(log) { D.send_logs.unshift({ id: D.send_logs.length + 1, ...log }); },

    /* ws-sim：取一条待注入的来消息 */
    pollIncoming(i) {
      const item = D.incoming_pool[i % D.incoming_pool.length];
      const conv = D.conversations.find((c) => c.id === item.conv_id);
      return { conv, ...item, time: '2026-11-02 ' + new Date().toTimeString().slice(0, 5) };
    },
  };
})();
