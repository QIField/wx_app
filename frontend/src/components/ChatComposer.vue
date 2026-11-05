<script setup>
/** 输入区：工具栏 + 可拖高输入框 + 发送（Enter 发送 / Shift+Enter 换行）。
 *  消息列表/滚动锚定等职责在 ChatPanel，本组件只管"输入与发送"。
 *  撤回消息"重新编辑"由父组件经 ref 调 fillAndFocus 回填聚焦。 */
import { nextTick, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useChatStore } from '../stores/chat'

const chat = useChatStore()
const input = ref('')
const composerEl = ref(null)
const composerH = ref(72) // 底部要给悬浮发送按钮留位，最小高度随之加大

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

async function onSend() {
  const content = input.value.trim()
  if (!content) return
  input.value = ''
  try {
    await chat.sendText(content)
  } catch (e) {
    ElMessage.error(e.message)
  }
}

/* Enter 发送 / Shift+Enter 换行（换行交还默认行为）。
   isComposing / keyCode 229：输入法选词时的回车不算发送 */
function onEnterKey(e) {
  if (e.shiftKey) return
  if (e.isComposing || e.keyCode === 229) return
  e.preventDefault()
  onSend()
}

/* 原文回填输入框并聚焦（父组件经 ref 调用） */
async function fillAndFocus(content) {
  input.value = content
  await nextTick()
  composerEl.value?.focus()
}
defineExpose({ fillAndFocus })
</script>

<template>
  <div class="editor">
    <div class="grab-bar" title="拖拽调整输入框高度" @mousedown.prevent="onGrabDown"><i></i></div>
    <div class="tools">
      <svg viewBox="0 0 24 24" class="ticon"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M8.5 10h.01M15.5 10h.01M8.5 14.5c1 1.2 2.2 1.8 3.5 1.8s2.5-.6 3.5-1.8" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
      <svg viewBox="0 0 24 24" class="ticon"><rect x="4" y="4" width="16" height="16" rx="2" fill="none" stroke="currentColor" stroke-width="1.6"/><circle cx="9.5" cy="9.5" r="1.6" fill="currentColor"/><path d="M5 17l4.5-4.5L13 16l3-3 3 3.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>
      <svg viewBox="0 0 24 24" class="ticon"><path d="M13 5H7a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><path d="M12 12l7-7m-4 0h4v4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
      <span class="hint">Enter 发送 · Shift+Enter 换行</span>
    </div>
    <div class="input-row">
      <div class="input-wrap">
        <textarea
          ref="composerEl"
          v-model="input"
          class="composer"
          :style="{ height: composerH + 'px' }"
          :disabled="!chat.currentId"
          placeholder="输入消息，Enter 发送…"
          @keydown.enter="onEnterKey"
        ></textarea>
        <button type="button" class="send" :disabled="!chat.currentId || !input.trim()" @click="onSend">发送(Enter)</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.editor { border-top: 1px solid var(--c-border); background: var(--c-panel); padding: 0 12px 10px; }
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
.ticon { width: 16px; height: 16px; color: var(--c-text-sub); cursor: pointer; transition: color 0.15s; }
.ticon:hover { color: var(--c-primary); }
.hint { margin-left: auto; font-size: 10px; color: var(--c-border-strong); }
.input-row { display: flex; }

/* 输入框 + 悬浮发送按钮（企业微信风格）：按钮叠在输入框右下角，
   textarea 底部留出等高 padding，文字不会滚到按钮底下 */
.input-wrap { position: relative; flex: 1; }

/* 高度由顶部拖拽条控制，禁用原生 resize 手柄 */
.composer {
  display: block;
  width: 100%;
  font-family: var(--font-ui);
  font-size: 13px;
  color: var(--c-text);
  line-height: 1.5;
  padding: 7px 10px 36px;
  border: 1px solid var(--c-border-strong);
  border-radius: var(--r-md);
  background: var(--c-panel);
  resize: none;
  outline: none;
  overflow-y: auto;
  transition: border-color 0.15s;
}
.composer:focus { border-color: var(--c-primary); }
.composer:disabled { background: #f5f7fa; cursor: not-allowed; }
.composer::placeholder { color: var(--c-border-strong); }
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
