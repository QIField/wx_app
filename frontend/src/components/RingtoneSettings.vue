<script setup>
/** 设置弹窗 · 消息提示音选择。
 *  铃声库来自 utils/ringtones（Web Audio 序列合成，零音频文件），
 *  试听/换铃声经 utils/notify（复用同一个 AudioContext 与解锁策略），
 *  选择即持久化 localStorage。交互元素统一 user-select:none 防误选中。 */
import { ref, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { RINGTONES, DEFAULT_RING } from '../utils/ringtones'
import { currentRingtone, setRingtone, previewRingtone, stopPreview } from '../utils/notify'

const visible = ref(false)
const current = ref(currentRingtone())
const previewingId = ref('') // 正在试听的铃声 id（'' = 无）
let resetTimer = null // 试听动画自动复位定时器

/** 打开弹窗：每次都按最新持久化状态渲染（顶栏齿轮调用）。 */
function open() {
  current.value = currentRingtone()
  visible.value = true
}

function close() {
  stopPreviewNow()
  visible.value = false
}

function stopPreviewNow() {
  if (resetTimer) { clearTimeout(resetTimer); resetTimer = null }
  stopPreview()
  previewingId.value = ''
}

/** 试听：再次点击同一条 = 停止；换听别的会先停掉上一条（互斥）。 */
function onPreview(id) {
  if (previewingId.value === id) { stopPreviewNow(); return }
  stopPreviewNow()
  const dur = previewRingtone(id)
  if (!dur) return // 静音无试听
  previewingId.value = id
  // 播完自动复位按钮动画（后端接口无此问题，纯前端状态）
  resetTimer = setTimeout(() => { previewingId.value = '' }, (dur + 0.2) * 1000)
}

/** 选中即生效：持久化 + 刷新「当前」标签。 */
function onSelect(id) {
  if (id === current.value) return
  stopPreviewNow()
  setRingtone(id)
  current.value = id
  ElMessage.success(`已将「${nameOf(id)}」设为消息提示音`)
}

/** 恢复默认铃声。 */
function onReset() {
  if (current.value === DEFAULT_RING) {
    ElMessage.info(`当前已是默认提示音「${nameOf(DEFAULT_RING)}」`)
    return
  }
  stopPreviewNow()
  setRingtone(DEFAULT_RING)
  current.value = DEFAULT_RING
  ElMessage.success(`已恢复默认提示音「${nameOf(DEFAULT_RING)}」`)
}

function nameOf(id) {
  return RINGTONES.find((r) => r.id === id)?.name || ''
}

// 弹窗关闭路径收口：遮罩点击 / ESC 都停掉试听，避免声音残留
onUnmounted(stopPreviewNow)
defineExpose({ open, close })
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="mask" @click.self="close" @keydown.esc="close">
      <div class="modal" role="dialog" aria-label="设置">
        <div class="m-head">
          <span class="m-ic">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>
          </span>
          <span class="m-title">设置</span>
          <button class="m-close" title="关闭" aria-label="关闭" @click="close">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
          </button>
        </div>

        <div class="m-body">
          <div class="sec-head">
            <span>消息提示音</span>
            <button class="reset-btn" @click="onReset">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>
              恢复默认
            </button>
          </div>

          <ul class="ring-list">
            <li v-for="r in RINGTONES" :key="r.id" class="ring-row" :class="{ playing: previewingId === r.id }">
              <label class="pick" :title="`设为消息提示音`">
                <input v-model="current" type="radio" name="ringtone" :value="r.id" @change="onSelect(r.id)">
                <span class="radio-ui"></span>
              </label>
              <div class="meta">
                <div class="name">
                  {{ r.name }}
                  <span v-if="r.isDefault" class="tag def">默认</span>
                  <span v-if="r.id === current" class="tag cur">当前</span>
                </div>
                <div class="desc">{{ r.desc }}</div>
              </div>
              <button class="play" @click="onPreview(r.id)">
                <span class="wave"><i /><i /><i /><i /></span>
                <svg v-if="previewingId !== r.id" width="12" height="12" viewBox="0 0 24 24" fill="currentColor" stroke="none"><polygon points="6 3 20 12 6 21 6 3"/></svg>
                <svg v-else width="12" height="12" viewBox="0 0 24 24" fill="currentColor" stroke="none"><rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/></svg>
                {{ previewingId === r.id ? '停止' : '试听' }}
              </button>
            </li>
          </ul>
          <p class="tip">选中即生效 · 新消息按所选铃声提醒</p>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
/* 遮罩 + 弹窗：tokens 与全局 style.css 一致；整体禁止文本选中（纯点选场景防误选） */
.mask {
  position: fixed;
  inset: 0;
  z-index: 50;
  background: rgba(20, 38, 77, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  animation: m-fade 0.2s ease both;
  user-select: none;
}
@keyframes m-fade { from { opacity: 0; } to { opacity: 1; } }
.modal {
  width: 400px;
  max-width: calc(100vw - 32px);
  max-height: calc(100vh - 64px);
  overflow: auto;
  background: var(--c-panel);
  border-radius: var(--r-lg);
  box-shadow: 0 12px 40px rgba(20, 38, 77, 0.3);
  animation: m-pop 0.25s cubic-bezier(0.22, 0.8, 0.36, 1) both;
}
@keyframes m-pop { from { opacity: 0; transform: scale(0.94) translateY(8px); } to { opacity: 1; transform: none; } }

.m-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 13px 16px;
  border-bottom: 1px solid var(--c-border);
}
.m-ic { display: inline-flex; color: var(--c-primary); }
.m-title { flex: 1; font-weight: 600; font-size: 14px; }
.m-close {
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  border-radius: var(--r-sm);
  color: var(--c-text-sub);
  cursor: pointer;
  user-select: none;
}
.m-close:hover { background: var(--c-bg); color: var(--c-text); }

.m-body { padding: 12px 16px 16px; }
.sec-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 8px;
  user-select: none;
}
.sec-head span { font-size: 12px; font-weight: 600; color: var(--c-text-sub); letter-spacing: 1px; }
.reset-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 24px;
  padding: 0 8px;
  font-size: 11px;
  color: var(--c-text-sub);
  background: none;
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
  cursor: pointer;
  user-select: none;
  transition: color 0.15s, border-color 0.15s, background 0.15s;
}
.reset-btn:hover { color: var(--c-primary); border-color: var(--c-primary); background: var(--c-primary-soft); }

.ring-list { list-style: none; margin: 0; padding: 0; }
.ring-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 8px;
  border-radius: var(--r-md);
  user-select: none; /* 铃声行是纯点选场景，禁止选中防误划选 */
  transition: background 0.15s;
}
.ring-row:hover { background: #f7f9fc; }

/* 单选圆点 */
.pick { display: flex; align-items: center; cursor: pointer; flex-shrink: 0; }
.pick input { position: absolute; opacity: 0; width: 0; height: 0; }
.radio-ui {
  display: block;
  width: 16px;
  height: 16px;
  border: 1.5px solid var(--c-border-strong);
  border-radius: 50%;
  position: relative;
  transition: border-color 0.15s;
}
.pick:hover .radio-ui { border-color: var(--c-primary); }
.pick input:checked + .radio-ui { border-color: var(--c-primary); }
.pick input:checked + .radio-ui::after {
  content: '';
  position: absolute;
  inset: 3px;
  background: var(--c-primary);
  border-radius: 50%;
}
.pick input:focus-visible + .radio-ui { outline: 2px solid var(--c-primary); outline-offset: 2px; }

.meta { flex: 1; min-width: 0; }
.name { font-size: 13px; font-weight: 600; display: flex; align-items: center; gap: 6px; }
.desc { font-size: 11px; color: var(--c-text-sub); margin-top: 2px; }

.tag {
  font-size: 10px;
  font-weight: 400;
  letter-spacing: 0.5px;
  border-radius: 3px;
  padding: 0.5px 6px;
  flex-shrink: 0;
}
.tag.def { color: var(--c-ok); background: #e7f6ee; border: 1px solid #bfe8d1; }
.tag.cur { color: var(--c-primary); background: var(--c-primary-soft); border: 1px solid #c9dcff; }

/* 试听按钮 + 播放波形动画：min-width + nowrap 自适应，
 * 播放中「波形+图标+文字」变宽也不折行、不挤压 */
.play {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-width: 74px;
  height: 30px;
  flex-shrink: 0;
  padding: 0 10px;
  font-size: 12px;
  white-space: nowrap;
  color: var(--c-text-sub);
  background: var(--c-bg);
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
  cursor: pointer;
  user-select: none;
  transition: color 0.15s, border-color 0.15s, background 0.15s;
}
.play:hover { color: var(--c-primary); border-color: var(--c-primary); background: var(--c-primary-soft); }
.play:focus-visible { outline: 2px solid var(--c-primary); outline-offset: 1px; }
.wave { display: none; align-items: flex-end; gap: 2px; height: 14px; }
.wave i { width: 3px; border-radius: 1px; background: var(--c-primary); animation: wv 0.7s ease-in-out infinite; }
.wave i:nth-child(1) { height: 6px; }
.wave i:nth-child(2) { height: 12px; animation-delay: 0.15s; }
.wave i:nth-child(3) { height: 8px; animation-delay: 0.3s; }
.wave i:nth-child(4) { height: 13px; animation-delay: 0.45s; }
@keyframes wv { 0%, 100% { transform: scaleY(0.4); } 50% { transform: scaleY(1); } }
.ring-row.playing .wave { display: flex; }
.ring-row.playing .play { color: var(--c-primary); border-color: var(--c-primary); background: var(--c-primary-soft); }

.tip { margin: 10px 0 0; font-size: 11px; color: var(--c-border-strong); text-align: center; user-select: none; }

@media (max-width: 480px) {
  .play { min-width: 62px; }
}
</style>
