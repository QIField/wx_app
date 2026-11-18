<script setup>
/** AI 对话子页：文字走真实 extract-parts（AI 询价要素提取），识别结果以场景卡列出。
 *
 * 图片 / 文件输入为原型预留：V1 需公网可访问的媒体直链，按钮置灰标注待后端支持。
 * 消息区自动滚底；Enter 发送、Shift+Enter 换行（与原型一致）。
 */
import { nextTick, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { qqExtractParts } from '../../api'

const log = ref([]) // { role: 'user'|'bot', text, scenes?: [...] }
const input = ref('')
const sending = ref(false)
const msgsEl = ref(null)

async function scrollBottom() {
  await nextTick()
  const el = msgsEl.value
  if (el) el.scrollTop = el.scrollHeight
}

onMounted(scrollBottom)

function sceneLine(s) {
  const bits = []
  if (s.part_name) bits.push(`配件：${s.part_name}`)
  if (s.oem_no) bits.push(`OE：${s.oem_no}`)
  if (s.vin) bits.push(`VIN：${s.vin}`)
  if (s.quoted) bits.push('跟进旧报价')
  return bits.length ? bits.join(' · ') : '（未提取到要素）'
}

async function send() {
  const text = input.value.trim()
  if (!text) {
    ElMessage.warning('请输入内容')
    return
  }
  if (sending.value) return
  sending.value = true
  input.value = ''
  log.value.push({ role: 'user', text })
  scrollBottom()
  try {
    const data = await qqExtractParts(text)
    const scenes = Array.isArray(data) ? data : (data && data.list) || []
    const body = scenes.length
      ? `识别到 ${scenes.length} 个询价场景：\n` + scenes.map(sceneLine).join('\n')
      : '未识别到询价要素，可补充配件名 / OE / VIN 后重试'
    log.value.push({ role: 'bot', text: body, need: !scenes.length, scenes })
  } catch (e) {
    log.value.push({ role: 'bot', text: `解析失败：${e.message || 'AI 服务异常'}`, need: true })
  } finally {
    sending.value = false
    scrollBottom()
  }
}

function onKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}
</script>

<template>
  <div class="ai-chat">
    <div ref="msgsEl" class="msgs">
      <div v-if="!log.length" class="empty">支持文字输入（图片 / 文件待后端支持），解析询价需求</div>
      <div v-for="(m, i) in log" :key="i" class="msg" :class="m.role">
        <div class="who">{{ m.role === 'user' ? '我' : 'AI' }}</div>
        <div class="bubble" :class="{ need: m.need }">{{ m.text }}</div>
      </div>
      <div v-if="sending" class="msg bot"><div class="who">AI</div><div class="bubble">解析中…</div></div>
    </div>

    <div class="inputs">
      <div class="attach">
        <button class="btn sm" disabled title="待后端支持：需公网可访问的图片直链（OCR 识别 VIN）">🖼 图片</button>
        <button class="btn sm" disabled title="待后端支持：文件解析暂未开放">📎 文件</button>
      </div>
      <div class="inputbox">
        <textarea
          v-model="input" class="ta"
          placeholder="输入聊天记录 / 询价内容…"
          rows="2"
          @keydown="onKeydown"
        ></textarea>
        <div class="sendrow">
          <span class="hint">Enter 发送 · Shift+Enter 换行</span>
          <button class="send" :disabled="sending" title="发送（Enter）" @click="send">
            <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
              <path d="M12 19V5M5.5 11.5 12 5l6.5 6.5" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ai-chat {
  height: 100%; min-height: 320px;
  display: flex; flex-direction: column; overflow: hidden;
  border: 1px solid var(--c-border); border-radius: var(--r-md);
}
.msgs {
  flex: 1; min-height: 0; overflow-y: auto;
  padding: 8px 10px; display: flex; flex-direction: column; gap: 6px;
  background: #f9fafd;
}
.msg { display: flex; gap: 6px; max-width: 92%; animation: msg-in 0.25s ease both; }
.msg.user { align-self: flex-end; flex-direction: row-reverse; }
.who {
  flex: none; width: 22px; height: 22px;
  border-radius: var(--r-sm); background: #cfd8e6; color: #fff;
  font-size: 10px; display: grid; place-items: center;
}
.msg.user .who { background: var(--c-primary); }
.bubble {
  padding: 6px 9px; border-radius: var(--r-md); font-size: 11px;
  white-space: pre-wrap; word-break: break-all; line-height: 1.6;
}
.msg.user .bubble { background: var(--c-primary-soft); border: 1px solid #c7d8ff; }
.msg.bot .bubble { background: var(--c-panel); border: 1px solid var(--c-border); }
.bubble.need { background: var(--c-warn-soft); border-color: rgba(240, 130, 30, 0.3); }
@keyframes msg-in {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: none; }
}
.empty { padding: 22px 10px; text-align: center; color: var(--c-text-sub); font-size: 11px; }

.inputs {
  flex: none; padding: 8px 10px 10px;
  border-top: 1px solid var(--c-border); background: var(--c-panel);
  display: flex; flex-direction: column; gap: 6px;
}
.attach { display: flex; gap: 5px; }
.btn.sm {
  padding: 3px 8px; font-size: 11px; border-radius: var(--r-sm);
  border: 1px solid var(--c-border-strong); background: var(--c-panel);
  color: var(--c-text-sub); cursor: not-allowed;
}
.inputbox { display: flex; flex-direction: column; }
.ta {
  display: block; width: 100%;
  min-height: 44px; max-height: 160px;
  padding: 6px 8px;
  font: inherit; line-height: 1.5;
  color: var(--c-text); background: transparent;
  border: 1px solid var(--c-border-strong); border-radius: var(--r-md);
  outline: none; resize: none; overflow-y: auto;
}
.ta:focus { border-color: var(--c-primary); }
.sendrow { display: flex; align-items: center; justify-content: space-between; margin-top: 6px; }
.hint { font-size: 10px; color: var(--c-text-sub); }
.send {
  width: 32px; height: 32px;
  display: grid; place-items: center;
  background: var(--c-primary); color: #fff;
  border: none; border-radius: 8px; cursor: pointer;
  transition: background 0.15s, transform 0.1s;
}
.send:hover:not(:disabled) { background: var(--c-primary-deep); }
.send:active:not(:disabled) { transform: scale(0.93); }
.send:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
