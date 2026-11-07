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
import MentionPicker from './MentionPicker.vue'
import {
  insertEmojiAtCursor, insertBreakAtCursor, insertPlainTextAtCursor,
  serializeComposer, setComposerFromText,
} from '../utils/emoji'
import {
  caretAnchorX, collectMentionIds, extractMentionQuery, insertMentionAtCursor,
  matchMembers, removeMentionAtCaret, textBeforeCaret,
} from '../utils/mention'

const chat = useChatStore()
const composerEl = ref(null)
const draftEmpty = ref(true)
const pickerVisible = ref(false)
const composerH = ref(72) // 底部要给悬浮发送按钮留位，最小高度随之加大

/* @提及浮层状态：检索词/高亮项/位置都在这里，成员名册缓存放在 chat store。
   只在群聊生效——单聊 @ 没有意义，还容易误发。 */
const mentionOpen = ref(false)
const mentionQuery = ref('')
const mentionItems = ref([])
const mentionTotal = ref(0)
const mentionActive = ref(-1)
const mentionLoading = ref(false)
const mentionLeft = ref(4)
const mentionWidth = ref(300)

watch(() => chat.currentId, () => {
  pickerVisible.value = false
  closeMention()
})

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

/* ---------------- @提及 ---------------- */

function closeMention() {
  mentionOpen.value = false
  mentionQuery.value = ''
  mentionItems.value = []
  mentionActive.value = -1
  mentionLoading.value = false
}

/** 浮层贴到 @ 所在位置：靠右时向左翻折，容器太窄时宽度自适应 */
function placeMentionPop() {
  const wrap = composerEl.value?.parentElement
  if (!wrap) return
  const wrapW = wrap.clientWidth
  const w = Math.min(320, wrapW - 8)
  mentionWidth.value = w
  const x = caretAnchorX()
  const raw = x == null ? 8 : x - wrap.getBoundingClientRect().left - 14
  mentionLeft.value = Math.max(4, Math.min(raw, wrapW - w - 4))
}

/**
 * 每次输入后重算「光标前是否处于 @ 上下文」。
 * 名册懒加载：第一次 @ 才请求接口，之后全部本地过滤（打字不打请求）；
 * 加载期间用户又改了检索词，本轮结果作废，交给更新的那一轮。
 */
async function detectMention() {
  const conv = chat.currentConv
  if (!conv || conv.chat_type !== 2) return closeMention()

  const q = extractMentionQuery(textBeforeCaret(composerEl.value))
  if (q == null) return closeMention()

  mentionQuery.value = q
  const convId = conv.id
  // undefined=没请求过；[]=请求过但名册为空（不再重复请求）
  if (!chat.membersByConv[convId]) {
    mentionLoading.value = true
    mentionOpen.value = true
    mentionItems.value = []
    mentionTotal.value = 0
    placeMentionPop()
    try {
      await chat.loadMembers(convId)
      mentionLoading.value = false
    } catch (e) {
      closeMention() // 内含 mentionLoading=false，避免浮层卡在"加载中"
      ElMessage.error(e.message)
      return
    }
    if (chat.currentId !== convId || mentionQuery.value !== q) return
  }
  mentionTotal.value = chat.currentMembers.length
  mentionItems.value = matchMembers(chat.currentMembers, q)
  mentionActive.value = mentionItems.value.length ? 0 : -1
  mentionOpen.value = true
  await nextTick()
  placeMentionPop()
}

function moveMentionActive(delta) {
  const n = mentionItems.value.length
  if (!n) return
  mentionActive.value = (mentionActive.value + delta + n) % n // 环绕，长列表也能从底部跳回顶部
}

function setMentionActive(i) {
  if (mentionOpen.value && i >= 0 && i < mentionItems.value.length) mentionActive.value = i
}

/** 选中成员：把「@检索词」替换成原子片段，光标落到片段之后可继续输入 */
function chooseMention(member) {
  if (!member) return
  insertMentionAtCursor(composerEl.value, member)
  closeMention()
  refreshDraft()
  composerEl.value?.focus()
}

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
    await chat.sendFile(file)
  } catch (err) {
    ElMessage.error(err.message)
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
    <div class="grab-bar" title="拖拽调整输入框高度" @mousedown.prevent="onGrabDown"><i></i></div>
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
          :style="{ height: composerH + 'px' }"
          data-placeholder="输入消息，Enter 发送…"
          spellcheck="false"
          @input="onComposerInput"
          @keydown="onComposerKeydown"
          @blur="closeMention"
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
