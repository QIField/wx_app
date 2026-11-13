<script setup>
/** 语音气泡：自绘播放控件替代原生 <audio>（浏览器解不了 SILK，原生控件只会显示 0:00/0:00）。
 *
 * 播放地址走媒体接口（后端已把 silk 转码成 mp3，返回 audio/mpeg）。
 * 四态（交互原型 prototypes/voice-bubble 为视觉规格来源）：
 * - 待播：灰波形 + 未读红点 + 蓝色圆钮
 * - 播放中：钮变暂停，主色进度扫过波形，未读部分轻微律动
 * - 已听完：波形整体转绿、未读点熄灭，可复听
 * - 已过期：媒体请求失败（中间方 ret=-2 / 下载失败）时降级为虚线灰卡，诚实告知不可播
 * 单实例互斥：模块级 currentStop，同一时刻全局只有一条语音在响。
 */
import { computed, onBeforeUnmount, ref } from 'vue'
import { mediaUrlOf } from '../utils/media'

const props = defineProps({
  msg: { type: Object, required: true }, // timeline 展开后的单条语音消息
})

/* ---------- 时长：payload.voicelength（毫秒）优先，content xml 属性兜底 ---------- */
const dur = computed(() => {
  const p = Number(props.msg.payload?.voicelength ?? props.msg.payload?.VoiceLength)
  if (p > 0) return p / 1000
  const m = /voicelength="(\d+)"/.exec(props.msg.content || '')
  return m ? Number(m[1]) / 1000 : 0
})
const durLabel = computed(() => (dur.value > 0 ? `${Math.round(dur.value)}″` : ''))
/* 气泡宽度按时长线性映射：90px 起步，封顶 260px */
const width = computed(() => `${Math.min(260, 90 + dur.value * 12)}px`)

/* ---------- 波形：24 根圆头竖条，按消息 id 确定性伪随机（同一条形状稳定不跳变） ---------- */
const BAR_COUNT = 24
const bars = computed(() => {
  const seed = Number(props.msg.id) || 1
  return Array.from({ length: BAR_COUNT }, (_, i) => {
    const x = Math.sin(seed * 37.7 + i * 5.3) * 0.5 + 0.5
    return 6 + Math.round(x * 14)
  })
})

/* ---------- 四态与播放控制 ---------- */
const isOut = computed(() => props.msg.direction === 2) // 收发方向只判一次
const playing = ref(false)
const done = ref(false)
const expired = ref(false)
const unread = ref(true)
const progress = ref(0)

let audio = null

/* 主色进度双层波形的裁剪比例：fill 层从右往左扫 */
const fillStyle = computed(() => ({
  clipPath: `inset(0 ${100 - progress.value * 100}% 0 0)`,
}))

/* 单实例互斥：指向当前在响那一条的暂停函数（模块级，跨组件实例生效） */
let currentStop = null

function pause() {
  audio?.pause()
  playing.value = false
  if (currentStop === mine) currentStop = null
}
const mine = () => pause()

/* 媒体请求失败（下载失败/语音过期/silk 未转码）→ 诚实降级为过期态 */
function onError() {
  playing.value = false
  expired.value = true
  if (currentStop === mine) currentStop = null
}

function toggle() {
  if (expired.value) return
  if (playing.value) {
    pause()
    return
  }
  // 停掉别的气泡（含其本地状态），再起自己
  if (currentStop && currentStop !== mine) currentStop()

  if (!audio) {
    audio = new Audio(mediaUrlOf(props.msg))
    audio.preload = 'metadata'
    audio.addEventListener('timeupdate', () => {
      // mp3 元数据未加载时 duration 可能是 Infinity/NaN，退回 xml 时长兜底
      const d = audio.duration && isFinite(audio.duration) ? audio.duration : dur.value
      if (d > 0) progress.value = Math.min(1, audio.currentTime / d)
    })
    audio.addEventListener('ended', () => {
      playing.value = false
      done.value = true // 听完标记：波形转绿、未读点熄灭
      progress.value = 1
      if (currentStop === mine) currentStop = null
    })
    audio.addEventListener('error', onError)
  }

  progress.value = 0
  unread.value = false // 点过即视为已读（会话内本地状态，不落库）
  if (audio.readyState >= 1) audio.currentTime = 0
  audio.play().then(() => {
    playing.value = true
    currentStop = mine
  }).catch(onError)
}

/* 离开会话时停掉还在响的语音，避免声音跨页面残留 */
onBeforeUnmount(() => {
  if (playing.value) pause()
})
</script>

<template>
  <!-- 已过期：虚线灰卡，绝不伪装成可播 -->
  <span v-if="expired" class="voice expired">
    <span class="v-exp-icon">✕</span>
    <span class="v-exp-text">语音已过期</span>
  </span>

  <span
    v-else
    class="voice"
    :class="[isOut ? 'out' : 'in', { playing, done }]"
    :style="{ width }"
    @click="toggle"
  >
    <button class="v-play" type="button" aria-label="播放语音" @click.stop="toggle">
      <svg class="i-play" viewBox="0 0 12 12"><path d="M3 1.5v9l7-4.5z" fill="currentColor" /></svg>
      <svg class="i-pause" viewBox="0 0 12 12"><path d="M2.5 1.5h2.6v9H2.5zM6.9 1.5h2.6v9H6.9z" fill="currentColor" /></svg>
    </button>
    <span class="v-wave">
      <span class="bars"><i v-for="(h, i) in bars" :key="i" :style="{ height: h + 'px' }"></i></span>
      <span class="bars-fill" :style="fillStyle"><i v-for="(h, i) in bars" :key="'f' + i" :style="{ height: h + 'px' }"></i></span>
    </span>
    <span class="v-dur">{{ durLabel }}</span>
    <span v-if="unread && !isOut" class="v-unread"></span>
  </span>
</template>

<style scoped>
/* 视觉规格对齐 prototypes/voice-bubble/styles.css；颜色全部复用工作台 tokens */
.voice {
  display: flex; align-items: center; gap: 10px;
  height: 44px; padding: 0 12px;
  border-radius: var(--r-md);
  cursor: pointer;
  user-select: none;
  -webkit-tap-highlight-color: transparent;
  transition: background 0.15s;
}
.voice.in { background: #f4f6fa; }
.voice.out { background: rgba(255, 255, 255, 0.65); }
.voice.in:hover { background: var(--c-primary-soft); }
.voice.out:hover { background: #fff; }

.v-play {
  width: 28px; height: 28px; border-radius: 50%;
  border: none; flex-shrink: 0; cursor: pointer;
  padding: 0;
  background: var(--c-primary); color: #fff;
  display: flex; align-items: center; justify-content: center;
  transition: background 0.15s, transform 0.1s;
}
.v-play:hover { background: var(--c-primary-deep); }
.v-play:active { transform: scale(0.92); }
.v-play svg { width: 12px; height: 12px; display: block; }
.v-play .i-pause { display: none; }
.voice.playing .v-play .i-play { display: none; }
.voice.playing .v-play .i-pause { display: block; }

/* 波形：底色层 + 主色进度层（clip-path 从右往左扫） */
.v-wave {
  position: relative;
  display: flex; align-items: center; gap: 2px;
  height: 22px; flex: 1;
  min-width: 0;
}
.v-wave .bars, .v-wave .bars-fill {
  position: absolute; inset: 0;
  display: flex; align-items: center; gap: 2px;
  overflow: hidden;
}
.v-wave .bars-fill { clip-path: inset(0 100% 0 0); }
.v-wave i {
  width: 3px; border-radius: 2px;
  background: #c3cede;
  flex-shrink: 0;
}
.v-wave .bars-fill i { background: var(--c-primary); }
/* 播放中：未读部分奇数条轻微律动 */
.voice.playing .v-wave .bars i:nth-child(odd) { animation: wob 0.7s ease-in-out infinite alternate; }
@keyframes wob {
  from { transform: scaleY(0.72); }
  to { transform: scaleY(1.12); }
}

/* 已听完：整条波形转绿（对齐 --c-ok 语义色） */
.voice.done .v-wave .bars-fill { clip-path: inset(0 0 0 0); }
.voice.done .v-wave .bars-fill i { background: var(--c-ok); }

.v-dur {
  font-size: 12px; color: var(--c-text-sub);
  font-variant-numeric: tabular-nums;
  flex-shrink: 0; min-width: 26px; text-align: right;
}
.voice.out .v-dur { color: var(--c-primary-deep); }

/* 未读红点：仅收方向且未播过 */
.v-unread {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--c-danger);
  flex-shrink: 0; margin-left: -2px;
}
.voice.done .v-unread, .voice.playing .v-unread { visibility: hidden; }

/* 过期态：降饱和 + 虚线 */
.voice.expired {
  cursor: not-allowed;
  background: #f2f3f6;
  border: 1px dashed var(--c-border);
}
.v-exp-icon {
  width: 28px; height: 28px; border-radius: 50%; flex-shrink: 0;
  background: #dde1e9; color: #8b95a7;
  display: flex; align-items: center; justify-content: center;
  font-size: 13px;
}
.v-exp-text { font-size: 12px; color: var(--c-text-sub); line-height: 1.4; }
</style>
