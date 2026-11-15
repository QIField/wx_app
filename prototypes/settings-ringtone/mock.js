/* =========================================================
 * mock.js — 数据单一来源（原型演示用，无真实后端）
 * 精简版：只保留当前铃声 + 经典铃声库
 * ========================================================= */

var DB = {
  settings: {
    ringtoneId: 'ding-dong' // 当前铃声，默认「轻快叮咚」
  }
};

// 默认铃声 id（「恢复默认」按钮的目标）
var DEFAULT_RING = 'ding-dong';

/* ---------------------------------------------------------
 * 经典铃声库：notes 为 Web Audio 合成序列（零音频文件，离线可用）
 * note 字段: t 起始秒 | f 起始频率Hz | to 滑向频率 | dur 时长秒
 *            type 波形(sine/triangle/square) | g 音量 | h 加泛音
 * --------------------------------------------------------- */
var RINGTONES = [
  {
    id: 'ding-dong', name: '轻快叮咚', desc: '温和清脆，久听不腻', isDefault: true,
    notes: [
      { t: 0,    f: 880,    dur: 0.16, g: 0.2 },
      { t: 0.18, f: 659.25, dur: 0.42, g: 0.18 }
    ]
  },
  {
    id: 'tri-tone', name: '经典三全音', desc: '熟悉的下降三连音',
    notes: [
      { t: 0,     f: 1046.5, dur: 0.11, type: 'triangle', g: 0.18 },
      { t: 0.115, f: 830.61, dur: 0.11, type: 'triangle', g: 0.18 },
      { t: 0.23,  f: 698.46, dur: 0.11, type: 'triangle', g: 0.18 },
      { t: 0.345, f: 466.16, dur: 0.38, type: 'triangle', g: 0.18 }
    ]
  },
  {
    id: 'marimba', name: '马林巴晨曲', desc: '木琴琶音，明快不刺耳',
    notes: [
      { t: 0,    f: 261.63, dur: 0.4,  type: 'triangle', g: 0.1 },
      { t: 0,    f: 523.25, dur: 0.2,  type: 'triangle', g: 0.16 },
      { t: 0.09, f: 659.25, dur: 0.2,  type: 'triangle', g: 0.16 },
      { t: 0.18, f: 783.99, dur: 0.2,  type: 'triangle', g: 0.16 },
      { t: 0.27, f: 1046.5, dur: 0.2,  type: 'triangle', g: 0.16 },
      { t: 0.42, f: 783.99, dur: 0.2,  type: 'triangle', g: 0.14 },
      { t: 0.51, f: 659.25, dur: 0.26, type: 'triangle', g: 0.14 }
    ]
  },
  {
    id: 'drop', name: '水滴落盘', desc: '一滴水声，轻巧低调',
    notes: [
      { t: 0,    f: 1250, to: 520, dur: 0.24, g: 0.24 },
      { t: 0.26, f: 1000, to: 420, dur: 0.3,  g: 0.18 }
    ]
  },
  {
    id: 'music-box', name: '八音盒', desc: '细碎铃音，安静氛围', h: true,
    notes: [
      { t: 0,    f: 1318.5, dur: 0.3,  g: 0.13 },
      { t: 0.15, f: 1046.5, dur: 0.3,  g: 0.13 },
      { t: 0.3,  f: 880,    dur: 0.3,  g: 0.13 },
      { t: 0.5,  f: 1318.5, dur: 0.3,  g: 0.12 },
      { t: 0.65, f: 1568,   dur: 0.55, g: 0.11 }
    ]
  },
  {
    id: 'beep', name: '电子嘀嘀', desc: '复古双音，业务感强',
    notes: [
      { t: 0,    f: 1318.5, dur: 0.09, type: 'square', g: 0.09 },
      { t: 0.18, f: 1318.5, dur: 0.09, type: 'square', g: 0.09 }
    ]
  },
  {
    id: 'bird', name: '鸟鸣晨曦', desc: '两声短促鸟叫，自然轻快',
    notes: [
      { t: 0,    f: 2100, to: 2900, dur: 0.12, g: 0.16 },
      { t: 0.15, f: 2400, to: 1650, dur: 0.16, g: 0.14 }
    ]
  },
  {
    id: 'chime', name: '空灵风铃', desc: '一串渐弱高音，余韵绵长',
    notes: [
      { t: 0,    f: 2093,   dur: 0.5,  g: 0.1 },
      { t: 0.12, f: 1760,   dur: 0.5,  g: 0.09 },
      { t: 0.24, f: 1568,   dur: 0.55, g: 0.09 },
      { t: 0.36, f: 1318.5, dur: 0.6,  g: 0.08 },
      { t: 0.5,  f: 1046.5, dur: 0.7,  g: 0.07 }
    ]
  }
];
