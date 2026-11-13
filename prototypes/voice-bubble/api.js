/* ===== api.js · 原型桩层 =====
 * 原型阶段不接真实后端；真实接入时把 getVoiceUrl 换成
 * `/api/messages/${id}/media?token=...`（后端转码后返回 audio/mpeg）。
 */
window.VoiceApi = {
  /** 语音播放地址（桩：真实实现走媒体接口） */
  getVoiceUrl(msg) {
    return msg.audio || "";
  },
};
