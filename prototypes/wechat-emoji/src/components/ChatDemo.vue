<script setup>
/** 演示主页面：说明条 + 聊天窗口（消息流 / 输入区 / 表情面板）。
 *  收发契约与 wx_app 一致：发送走 sendTextMessage 桩（签名同真实 API），
 *  乐观上屏 status 0→1；收到的 msg_type=1 文本含 [码] 与 Unicode emoji。
 */
import { nextTick, onMounted, ref, watch } from 'vue'
import EmojiPicker from './EmojiPicker.vue'
import MessageBubble from './MessageBubble.vue'
import { DEMO_CONV, DEMO_MESSAGES, AUTO_REPLIES } from '../mock/messages'
import { sendTextMessage } from '../api/stub'
import {
  insertEmojiAtCursor, insertBreakAtCursor, insertPlainTextAtCursor, serializeComposer,
} from '../utils/emoji'

const messages = ref([...DEMO_MESSAGES])
const draftEmpty = ref(true)
const pickerVisible = ref(false)
const listEl = ref(null)
const composerEl = ref(null)
const sending = ref(false)

/* 新消息到底部：列表滚动锚定 */
watch(
  () => messages.value.length,
  async () => {
    await nextTick()
    const el = listEl.value
    if (el) el.scrollTop = el.scrollHeight
  }
)
onMounted(() => {
  const el = listEl.value
  if (el) el.scrollTop = el.scrollHeight
})

function togglePicker() {
  pickerVisible.value = !pickerVisible.value
}

/* 面板选中 → 光标处插入表情图（wx）/字符（unicode），发送时才还原为 [码] 文本 */
function onEmojiSelect(payload) {
  insertEmojiAtCursor(composerEl.value, payload)
  refreshDraftState()
}

function refreshDraftState() {
  const text = serializeComposer(composerEl.value)
  // 全删后浏览器常残留 <br>，清掉以恢复占位符
  if (!text && composerEl.value && composerEl.value.innerHTML !== '') {
    composerEl.value.innerHTML = ''
  }
  draftEmpty.value = text.length === 0
}

async function onSend() {
  const content = serializeComposer(composerEl.value)
  if (!content || sending.value) return
  composerEl.value.innerHTML = ''
  refreshDraftState()
  pickerVisible.value = false
  const optimistic = {
    id: Date.now(), direction: 2, msg_type: 1,
    content, sender: DEMO_CONV.agent, status: 0,
  }
  messages.value.push(optimistic)
  try {
    const res = await sendTextMessage('demo-conv', content)
    optimistic.status = res.status
    setTimeout(autoReply, 600)
  } catch (e) {
    optimistic.status = 2
  }
}

/* 演示自动回包：展示"收到的表情"渲染效果（接入真实 WS 后删除） */
function autoReply() {
  const text = AUTO_REPLIES[Math.floor(Math.random() * AUTO_REPLIES.length)]
  messages.value.push({
    id: Date.now(), direction: 1, msg_type: 1,
    content: text, sender: DEMO_CONV.name,
  })
}

function onEnterKey(e) {
  if (e.isComposing || e.keyCode === 229) return // 中文输入法组词确认
  if (e.shiftKey) {
    e.preventDefault()
    insertBreakAtCursor(composerEl.value)
    refreshDraftState()
    return
  }
  e.preventDefault()
  onSend()
}

function onPaste(e) {
  e.preventDefault()
  const text = e.clipboardData?.getData('text/plain') || ''
  if (text) {
    insertPlainTextAtCursor(composerEl.value, text)
    refreshDraftState()
  }
}
</script>

<template>
  <div class="page">
    <header class="topbar">
      <span class="brand-dot"></span>
      <span class="brand">wx_app · 微信表情消息方案</span>
      <span class="chip">Vue3 原型 · 组件可平移集成</span>
    </header>

    <!-- 三层表情体系说明 -->
    <section class="tiers">
      <div class="tier">
        <span class="t-no">01</span>
        <div>
          <div class="t-title">微信表情码 [微笑]</div>
          <div class="t-desc">收发即 `[名称]` 文本，渲染为微信同款表情图；发给客户微信原生还原，<b>后端零改动</b></div>
        </div>
      </div>
      <div class="tier">
        <span class="t-no">02</span>
        <div>
          <div class="t-title">Unicode emoji 😊</div>
          <div class="t-desc">系统字体原生渲染，收发均无需转换，输入法直接打出</div>
        </div>
      </div>
      <div class="tier">
        <span class="t-no">03</span>
        <div>
          <div class="t-title">自定义表情 msg_type=7</div>
          <div class="t-desc">贴边图片气泡，wx_app 已支持展示；发送侧后续扩展（见 contract）</div>
        </div>
      </div>
    </section>

    <section class="chatwin">
      <div class="conv-head">
        <span class="conv-name">{{ DEMO_CONV.name }}</span>
        <span class="online"><i></i>对方在线</span>
      </div>

      <div ref="listEl" class="list">
        <MessageBubble v-for="m in messages" :key="m.id" :msg="m" />
      </div>

      <div class="editor">
        <div class="tools">
          <button type="button" class="ticon-btn" title="表情" :class="{ on: pickerVisible }" @click="togglePicker">
            <svg viewBox="0 0 24 24" class="ticon"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M8.5 10h.01M15.5 10h.01M8.5 14.5c1 1.2 2.2 1.8 3.5 1.8s2.5-.6 3.5-1.8" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
          </button>
          <svg viewBox="0 0 24 24" class="ticon dim" title="图片（演示占位）"><rect x="4" y="4" width="16" height="16" rx="2" fill="none" stroke="currentColor" stroke-width="1.6"/><circle cx="9.5" cy="9.5" r="1.6" fill="currentColor"/><path d="M5 17l4.5-4.5L13 16l3-3 3 3.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>
          <span class="hint">Enter 发送 · Shift+Enter 换行</span>
        </div>
        <div class="editor-body">
          <div
            ref="composerEl"
            class="composer"
            contenteditable="true"
            data-placeholder="输入消息，点笑脸发表情…"
            spellcheck="false"
            @input="refreshDraftState"
            @keydown.enter="onEnterKey"
            @paste="onPaste"
          ></div>
          <button type="button" class="send" :disabled="draftEmpty || sending" @click="onSend">发送(Enter)</button>
        </div>

        <EmojiPicker :visible="pickerVisible" @select="onEmojiSelect" />
      </div>
    </section>

    <footer class="foot">发送的 `[码]` 随 msg_type=1 文本上行，客户微信端自动还原为表情；未识别码原样显示（与微信兜底一致）。</footer>
  </div>
</template>

<style scoped>
.page { max-width: 860px; margin: 0 auto; padding: 24px 16px 32px; }

.topbar { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; }
.brand-dot { width: 10px; height: 10px; border-radius: 50%; background: var(--c-primary); box-shadow: 0 0 0 4px var(--c-primary-soft); }
.brand { font-size: 16px; font-weight: 700; letter-spacing: 0.5px; }
.chip { margin-left: auto; font-size: 11px; color: var(--c-primary); background: var(--c-primary-soft); border-radius: 999px; padding: 3px 10px; }

.tiers { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 16px; }
.tier {
  display: flex; gap: 10px; align-items: flex-start;
  background: var(--c-panel); border: 1px solid var(--c-border);
  border-radius: var(--r-lg); padding: 12px;
  box-shadow: 0 1px 3px rgba(23, 35, 58, 0.05);
}
.t-no { font-size: 20px; font-weight: 800; color: var(--c-primary); opacity: 0.85; line-height: 1; }
.t-title { font-size: 13px; font-weight: 700; margin-bottom: 3px; }
.t-desc { font-size: 11px; color: var(--c-text-sub); line-height: 1.55; }

.chatwin {
  background: var(--c-panel);
  border: 1px solid var(--c-border);
  border-radius: var(--r-lg);
  box-shadow: 0 6px 24px rgba(23, 35, 58, 0.08);
  overflow: hidden;
}
.conv-head {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 16px; border-bottom: 1px solid var(--c-border);
  background: var(--c-panel);
}
.conv-name { font-size: 14px; font-weight: 700; }
.online { margin-left: auto; font-size: 11px; color: var(--c-ok); display: flex; align-items: center; gap: 5px; }
.online i { width: 7px; height: 7px; border-radius: 50%; background: var(--c-ok); }

.list { height: 380px; overflow-y: auto; padding: 16px 16px 6px; background: var(--c-surface); }

/* 输入区：定位上下文给表情面板（面板 absolute 弹在上方） */
.editor { position: relative; border-top: 1px solid var(--c-border); background: var(--c-panel); padding: 0 12px 10px; }
.tools { display: flex; align-items: center; gap: 10px; padding: 4px 2px 6px; }
.ticon-btn { border: none; background: none; padding: 0; cursor: pointer; line-height: 0; }
.ticon { width: 17px; height: 17px; color: var(--c-text-sub); transition: color 0.15s; }
.ticon-btn:hover .ticon, .ticon-btn.on .ticon { color: var(--c-primary); }
.ticon.dim { cursor: default; }
.hint { margin-left: auto; font-size: 10px; color: var(--c-border-strong); }

.editor-body { position: relative; }
.composer {
  width: 100%;
  font-family: var(--font-ui); font-size: 13px; color: var(--c-text);
  line-height: 1.6; padding: 8px 10px 36px;
  border: 1px solid var(--c-border-strong); border-radius: var(--r-md);
  background: var(--c-panel); outline: none; cursor: text;
  height: 84px; overflow-y: auto;
  white-space: pre-wrap; word-break: break-word;
  transition: border-color 0.15s;
}
.composer:empty::before {
  content: attr(data-placeholder);
  color: var(--c-border-strong);
  pointer-events: none;
}
.composer:focus { border-color: var(--c-primary); }
.composer img { cursor: default; }
.send {
  position: absolute; right: 8px; bottom: 8px;
  height: 26px; padding: 0 14px;
  font-size: 12px; font-family: var(--font-ui);
  color: var(--c-text); background: #eef1f6;
  border: none; border-radius: 4px; cursor: pointer;
  transition: background 0.15s;
}
.send:hover:not(:disabled) { background: var(--c-primary); color: #fff; }
.send:disabled { color: var(--c-border-strong); cursor: not-allowed; }

.foot { margin-top: 12px; font-size: 11px; color: var(--c-text-sub); text-align: center; }
</style>
