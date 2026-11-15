/* =========================================================
 * api.js — 接口桩层（stub）
 * 函数签名 = 未来真实接口形态；接入后端时按 TODO 注释替换实现即可，
 * 页面代码无需改动（请求/响应结构不变）。
 * ========================================================= */

// 模拟网络时延，让 loading / saving 状态真实可见
function _delay(ms) {
  return new Promise(function (resolve) { setTimeout(resolve, ms); });
}

var api = {

  /**
   * 拉取当前铃声设置
   * TODO: 替换为 GET /api/me/settings/ringtone
   * 返回: { ringtoneId: 'ding-dong' }
   */
  fetchRingtone: async function () {
    await _delay(500);
    // TODO: replace with fetch('/api/me/settings/ringtone')
    return { ringtoneId: DB.settings.ringtoneId };
  },

  /**
   * 选择消息提示音（选中即保存）
   * TODO: 替换为 PUT /api/me/settings/ringtone
   * 请求: { ringtone_id: 'ding-dong' }
   */
  updateRingtone: async function (ringtoneId) {
    await _delay(420);
    // TODO: replace with fetch('/api/me/settings/ringtone', { method: 'PUT', body: JSON.stringify({ ringtone_id: ringtoneId }) })
    DB.settings.ringtoneId = ringtoneId;
    return { ringtoneId: DB.settings.ringtoneId };
  }
};
