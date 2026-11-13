/* ===== mock.js · 语音气泡原型假数据 =====
 * duration 单位秒；真实数据取 payload.voicelength（毫秒）÷1000，
 * 原型里直接写秒。state：ready 待播 / done 已听完 / expired 微信侧过期。
 * audio 字段指向真实转码 mp3（仅第一条有，演示真实播放）。
 */
window.MOCK_VOICES = [
  {
    id: 1, dir: "in", sender: "zzy971003", avatarText: "z",
    duration: 4.8, state: "ready",
    audio: "assets/voice_2468.mp3",
    note: "真实文件：silk → mp3 转码产物，点击可播",
  },
  {
    id: 2, dir: "in", sender: "张瑞", avatarText: "张",
    duration: 12, state: "done",
    note: "已听完：波形转实色，可复听",
  },
  {
    id: 3, dir: "out", sender: "客服小陈", avatarText: "陈",
    duration: 3, state: "ready",
    note: "出向语音：软蓝底，右侧收口",
  },
  {
    id: 4, dir: "in", sender: "未知联系人", avatarText: "?",
    duration: 0, state: "expired",
    note: "微信侧已过期（BaseResponse.ret=-2），只能标记，不能伪装成可播",
  },
];
