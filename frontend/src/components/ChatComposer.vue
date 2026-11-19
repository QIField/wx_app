<script setup>
/** 输入区：工具栏 + 输入框 + 表情面板 + 发送（Enter 发送 / Shift+Enter 换行）。
 *  消息列表/滚动锚定等职责在 ChatPanel，本组件只管"输入与发送"。
 *  撤回消息"重新编辑"由父组件经 ref 调 fillAndFocus 回填聚焦。
 *  输入区用 contenteditable：选表情在光标处显示表情图（微信同款），
 *  发送前 serializeComposer 还原为 `[名称]` 码随 msg_type=1 文本上行。
 *  @提及浮层（状态/定位/名册懒加载/键盘导航）抽在 composables/useMention。 */
import { nextTick, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useChatStore } from '../stores/chat'
import EmojiPicker from './EmojiPicker.vue'
import MentionPicker from './MentionPicker.vue'
import { useMention } from '../composables/useMention'
import {
  insertEmojiAtCursor, insertBreakAtCursor, insertPlainTextAtCursor,
  serializeComposer, setComposerFromText,
} from '../utils/emoji'
import { collectMentionIds, removeMentionAtCaret } from '../utils/mention'

const chat = useChatStore()
const composerEl = ref(null)
const draftEmpty = ref(true)
const pickerVisible = ref(false)

function refreshDraft() {
  draftEmpty.value = serializeComposer(composerEl.value).length === 0
}

/* @提及逻辑抽在 useMention，这里只接线（插入片段后回调刷新可发送态） */
const {
  mentionOpen, mentionQuery, mentionItems, mentionTotal, mentionActive, mentionLoading,
  mentionLeft, mentionWidth,
  closeMention, detectMention, moveMentionActive, setMentionActive, chooseMention,
} = useMention(composerEl, { afterInsert: refreshDraft })

watch(() => chat.currentId, () => {
  pickerVisible.value = false
})

/* 输入事件：先刷新可发送态，再判断 @ 上下文 */
function onComposerInput() {
  refreshDraft()
  detectMention()
}

/* 面板选中 → 光标处插入表情图（wx）/字符（unicode） */
function onEmojiSelect(payload) {
  insertEmojiAtCursor(composerEl.value, payload)
  refreshDraft()
}

/* 表情面板与 @ 浮层互斥：开一个就关另一个 */
function toggleEmojiPicker() {
  pickerVisible.value = !pickerVisible.value
  closeMention()
}

/* 统一 sendFile 入口：错误提示收敛一处（文件按钮与粘贴图片两个入口共用） */
async function sendFileSafe(file) {
  try {
    await chat.sendFile(file)
  } catch (err) {
    ElMessage.error(err.message)
  }
}

/* 粘贴分发：图片 → 直接 sendFile（微信同款）；其余 → 维持纯文本插入。
   图片不进 contenteditable，与 @提及/表情序列化逻辑零冲突 */
function onPaste(e) {
  // ① 优先找剪贴板里的图片项（QQ/微信截图、系统截图工具、网页复制图片都走这）
  const items = e.clipboardData?.items || []
  const imgItem = [...items].find((it) => it.type.startsWith('image/'))
  if (imgItem && chat.currentId) {
    e.preventDefault()
    const file = imgItem.getAsFile()
    if (file) sendFileSafe(file)
    return
  }
  // ② 无图片：仅收纯文本，防富文本破坏编辑器结构
  e.preventDefault()
  const text = e.clipboardData?.getData('text/plain') || ''
  if (text) {
    insertPlainTextAtCursor(composerEl.value, text)
    refreshDraft()
  }
}

async function onSend() {
  // 不 trim：结尾的 U+2005 是微信 @ 的定界符，trim 掉对方就收不到提醒
  const content = serializeComposer(composerEl.value)
  if (!content.trim()) return
  const atIds = collectMentionIds(composerEl.value)
  composerEl.value.innerHTML = ''
  closeMention()
  refreshDraft()
  try {
    await chat.sendText(content, atIds)
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
    await sendFileSafe(file)
  } finally {
    uploading.value = false
  }
}

/* 统一键盘入口：浮层打开时方向键/回车/返回给浮层，其余保持原逻辑。
   isComposing / keyCode 229：输入法选词时的按键一律不处理 */
function onComposerKeydown(e) {
  if (e.isComposing || e.keyCode === 229) return

  if (mentionOpen.value) {
    if (e.key === 'ArrowDown') { e.preventDefault(); moveMentionActive(1); return }
    if (e.key === 'ArrowUp') { e.preventDefault(); moveMentionActive(-1); return }
    if ((e.key === 'Enter' || e.key === 'Tab') && mentionItems.value.length) {
      e.preventDefault()
      chooseMention(mentionItems.value[mentionActive.value])
      return
    }
  }

  if (e.key === 'Escape') {
    e.preventDefault()
    closeMention()
    pickerVisible.value = false
    return
  }

  // 退格紧贴片段：整块删除（否则会留下 "@" 或半截昵称）
  if (e.key === 'Backspace' && removeMentionAtCaret()) {
    e.preventDefault()
    refreshDraft()
    return
  }

  if (e.key === 'Enter') {
    e.preventDefault()
    if (e.shiftKey) {
      insertBreakAtCursor(composerEl.value)
      refreshDraft()
      return
    }
    onSend()
  }
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
    <div class="tools">
      <button
        type="button" class="ticon-btn" :class="{ on: pickerVisible }"
        :disabled="!chat.currentId" title="表情" @click="toggleEmojiPicker"
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
      <span class="hint">
        Enter 发送 · Shift+Enter 换行<template v-if="chat.currentConv?.chat_type === 2"> · 输入 @ 提醒群成员</template>
      </span>
    </div>
    <div class="input-row">
      <div class="input-wrap">
        <MentionPicker
          :visible="mentionOpen"
          :members="mentionItems"
          :total="mentionTotal"
          :query="mentionQuery"
          :active="mentionActive"
          :loading="mentionLoading"
          :style="{ left: mentionLeft + 'px', width: mentionWidth + 'px' }"
          @update:active="setMentionActive"
          @select="chooseMention"
        />
        <div
          ref="composerEl"
          class="composer"
          :class="{ disabled: !chat.currentId }"
          :contenteditable="chat.currentId ? 'true' : 'false'"
          data-placeholder="输入消息，Enter 发送…"
          spellcheck="false"
          @input="onComposerInput"
          @keydown="onComposerKeydown"
          @blur="closeMention"
          @paste="onPaste"
        ></div>
        <div class="sendrow">
          <button type="button" class="send" :disabled="!chat.currentId || draftEmpty" @click="onSend">发送(Enter)</button>
        </div>
      </div>
    </div>

    <EmojiPicker :visible="pickerVisible" @select="onEmojiSelect" />
  </div>
</template>

<style scoped>
.editor { position: relative; border-top: 1px solid var(--c-border); background: var(--c-panel); padding: 0 12px 10px; }
.tools { display: flex; align-items: center; gap: 10px; padding: 3px 2px 6px; }
.ticon-btn { border: none; background: none; padding: 0; line-height: 0; }
.ticon { width: 16px; height: 16px; color: var(--c-text-sub); cursor: pointer; transition: color 0.15s; }
.ticon-btn:hover .ticon, .ticon-btn.on .ticon { color: var(--c-primary); }
.ticon-btn:disabled .ticon { color: var(--c-border-strong); cursor: not-allowed; }
.hint { margin-left: auto; font-size: 10px; color: var(--c-border-strong); }
.input-row { display: flex; }

/* 输入框 + 下方发送按钮（与 AI 对话输入框同款摆放）：输入框无边框，
   高度随内容自动撑高，到上限后内部滚动 */
.input-wrap { position: relative; flex: 1; }

.composer {
  width: 100%;
  min-height: 48px;
  max-height: 300px;
  font-family: var(--font-ui);
  font-size: 13px;
  color: var(--c-text);
  line-height: 1.5;
  padding: 7px 10px;
  background: transparent;
  outline: none;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
  cursor: text;
}
.composer.disabled { background: #f5f7fa; cursor: not-allowed; }
/* @昵称原子片段由 JS 动态插入，拿不到 scoped 属性，必须 :deep */
.composer :deep(.mention) {
  color: var(--c-primary);
  background: var(--c-primary-soft);
  border-radius: 3px;
  padding: 1px 3px;
  font-weight: 600;
  user-select: all;
}
.composer:empty::before {
  content: attr(data-placeholder);
  color: var(--c-border-strong);
  pointer-events: none;
}
.composer img { cursor: default; }
.sendrow { display: flex; justify-content: flex-end; padding-top: 6px; }
.send {
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
