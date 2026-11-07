<script setup>
/** 输入区：工具栏 + 可拖高输入框 + 表情面板 + 发送（Enter 发送 / Shift+Enter 换行）。
 *  消息列表/滚动锚定等职责在 ChatPanel，本组件只管"输入与发送"。
 *  撤回消息"重新编辑"由父组件经 ref 调 fillAndFocus 回填聚焦。
 *  输入区用 contenteditable：选表情在光标处显示表情图（微信同款），
 *  发送前 serializeComposer 还原为 `[名称]` 码随 msg_type=1 文本上行。 */
import { nextTick, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useChatStore } from '../stores/chat'
import EmojiPicker from './EmojiPicker.vue'
import {
  insertEmojiAtCursor, insertBreakAtCursor, insertPlainTextAtCursor,
  serializeComposer, setComposerFromText,
} from '../utils/emoji'

const chat = useChatStore()
const composerEl = ref(null)
const draftEmpty = ref(true)
const pickerVisible = ref(false)
const composerH = ref(72) // 底部要给悬浮发送按钮留位，最小高度随之加大

watch(() => chat.currentId, () => { pickerVisible.value = false })

/* 顶部拖拽拉伸：按住输入框上边缘上下拖，向上拖=变高 */
let drag = null
function onGrabDown(e) {
  drag = { y: e.clientY, h: composerH.value }
  window.addEventListener('mousemove', onGrabMove)
  window.addEventListener('mouseup', onGrabUp)
}
function onGrabMove(e) {
  composerH.value = Math.min(300, Math.max(72, drag.h - (e.clientY - drag.y)))
}
function onGrabUp() {
  window.removeEventListener('mousemove', onGrabMove)
  window.removeEventListener('mouseup', onGrabUp)
  drag = null
}

function refreshDraft() {
  draftEmpty.value = serializeComposer(composerEl.value).length === 0
}

/* 面板选中 → 光标处插入表情图（wx）/字符（unicode） */
function onEmojiSelect(payload) {
  insertEmojiAtCursor(composerEl.value, payload)
  refreshDraft()
}

/* 粘贴仅收纯文本：防富文本/图片破坏编辑器结构 */
function onPaste(e) {
  e.preventDefault()
  const text = e.clipboardData?.getData('text/plain') || ''
  if (text) {
    insertPlainTextAtCursor(composerEl.value, text)
    refreshDraft()
  }
}

async function onSend() {
  const content = serializeComposer(composerEl.value).trim()
  if (!content) return
  composerEl.value.innerHTML = ''
  refreshDraft()
  try {
    await chat.sendText(content)
  } catch (e) {
    ElMessage.error(e.message)
  }
}

/* 文件按钮：打开系统文件资源管理器，任意类型（excel/图片/视频…）。
   大小校验、MIME 分发与 payload 组装都在 chat store 的 sendFile。 */
const fileInput = ref(null)
const uploading = ref(false)

async function onFilePicked(e) {
  const file = e.target.files?.[0]
  e.target.value = '' // 清掉允许重复选同一个文件
  if (!file || !chat.currentId) return
  uploading.value = true
  try {
    await chat.sendFile(file)
  } catch (err) {
    ElMessage.error(err.message)
  } finally {
    uploading.value = false
  }
}

/* Enter 发送 / Shift+Enter 换行（手动插 <br>，避免浏览器包块级元素导致序列化歧义）。
   isComposing / keyCode 229：输入法选词时的回车不算发送 */
function onEnterKey(e) {
  if (e.isComposing || e.keyCode === 229) return
  if (e.shiftKey) {
    e.preventDefault()
    insertBreakAtCursor(composerEl.value)
    refreshDraft()
    return
  }
  e.preventDefault()
  onSend()
}

/* 原文回填输入框并聚焦（父组件经 ref 调用）：[码] 渲染为表情图，光标落末尾 */
async function fillAndFocus(content) {
  await nextTick()
  setComposerFromText(composerEl.value, content)
  refreshDraft()
}
defineExpose({ fillAndFocus })
</script>

<template>
  <div class="editor">
    <div class="grab-bar" title="拖拽调整输入框高度" @mousedown.prevent="onGrabDown"><i></i></div>
    <div class="tools">
      <button
        type="button" class="ticon-btn" :class="{ on: pickerVisible }"
        :disabled="!chat.currentId" title="表情" @click="pickerVisible = !pickerVisible"
      >
        <svg viewBox="0 0 24 24" class="ticon"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M8.5 10h.01M15.5 10h.01M8.5 14.5c1 1.2 2.2 1.8 3.5 1.8s2.5-.6 3.5-1.8" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
      </button>
      <button
        type="button" class="ticon-btn" :disabled="!chat.currentId || uploading"
        title="发送文件（任意类型）" @click="fileInput?.click()"
      >
        <svg viewBox="0 0 24 24" class="ticon"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
      </button>
      <input ref="fileInput" type="file" style="display: none" @change="onFilePicked" />
      <svg viewBox="0 0 24 24" class="ticon"><path d="M13 5H7a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><path d="M12 12l7-7m-4 0h4v4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
      <span class="hint">Enter 发送 · Shift+Enter 换行</span>
    </div>
    <div class="input-row">
      <div class="input-wrap">
        <div
          ref="composerEl"
          class="composer"
          :class="{ disabled: !chat.currentId }"
          :contenteditable="chat.currentId ? 'true' : 'false'"
          :style="{ height: composerH + 'px' }"
          data-placeholder="输入消息，Enter 发送…"
          spellcheck="false"
          @input="refreshDraft"
          @keydown.enter="onEnterKey"
          @keydown.esc="pickerVisible = false"
          @paste="onPaste"
        ></div>
        <button type="button" class="send" :disabled="!chat.currentId || draftEmpty" @click="onSend">发送(Enter)</button>
      </div>
    </div>

    <EmojiPicker :visible="pickerVisible" @select="onEmojiSelect" />
  </div>
</template>

<style scoped>
.editor { position: relative; border-top: 1px solid var(--c-border); background: var(--c-panel); padding: 0 12px 10px; }
.grab-bar {
  height: 10px; margin: 0 -12px;
  display: flex; align-items: center; justify-content: center;
  cursor: ns-resize;
  transition: background 0.15s;
}
.grab-bar:hover { background: #f0f4fb; }
.grab-bar i {
  width: 28px; height: 3px; border-radius: 2px;
  background: var(--c-border-strong);
  transition: background 0.15s, width 0.15s;
}
.grab-bar:hover i { background: var(--c-primary); width: 44px; }
.tools { display: flex; align-items: center; gap: 10px; padding: 3px 2px 6px; }
.ticon-btn { border: none; background: none; padding: 0; line-height: 0; }
.ticon { width: 16px; height: 16px; color: var(--c-text-sub); cursor: pointer; transition: color 0.15s; }
.ticon-btn:hover .ticon, .ticon-btn.on .ticon { color: var(--c-primary); }
.ticon-btn:disabled .ticon { color: var(--c-border-strong); cursor: not-allowed; }
.hint { margin-left: auto; font-size: 10px; color: var(--c-border-strong); }
.input-row { display: flex; }

/* 输入框 + 悬浮发送按钮（企业微信风格）：按钮叠在输入框右下角，
   输入框底部留出等高 padding，文字不会滚到按钮底下 */
.input-wrap { position: relative; flex: 1; }

/* 高度由顶部拖拽条控制（contenteditable div） */
.composer {
  width: 100%;
  font-family: var(--font-ui);
  font-size: 13px;
  color: var(--c-text);
  line-height: 1.5;
  padding: 7px 10px 36px;
  border: 1px solid var(--c-border-strong);
  border-radius: var(--r-md);
  background: var(--c-panel);
  outline: none;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
  cursor: text;
  transition: border-color 0.15s;
}
.composer:focus { border-color: var(--c-primary); }
.composer.disabled { background: #f5f7fa; cursor: not-allowed; }
.composer:empty::before {
  content: attr(data-placeholder);
  color: var(--c-border-strong);
  pointer-events: none;
}
.composer img { cursor: default; }
.send {
  position: absolute;
  right: 8px;
  bottom: 8px;
  height: 26px;
  padding: 0 14px;
  font-size: 12px;
  font-family: var(--font-ui);
  color: var(--c-text);
  background: #eef1f6;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.send:hover:not(:disabled) { background: #e2e8f2; }
.send:disabled { color: var(--c-border-strong); cursor: not-allowed; }
</style>
