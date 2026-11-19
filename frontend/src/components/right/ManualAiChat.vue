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
const taEl = ref(null)

function autoGrow() {
  const el = taEl.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 160) + 'px'
}

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
  nextTick(() => autoGrow())
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
      <div v-if="!log.length" class="qq-empty">支持文字输入（图片 / 文件待后端支持），解析询价需求</div>
      <div v-for="(m, i) in log" :key="i" class="msg" :class="m.role">
        <div class="who">{{ m.role === 'user' ? '我' : 'AI' }}</div>
        <div class="bubble" :class="{ need: m.need }">{{ m.text }}</div>
      </div>
      <div v-if="sending" class="msg bot"><div class="who">AI</div><div class="bubble">解析中…</div></div>
    </div>

    <div class="inputs">
      <div class="attach">
        <button class="qq-btn-sm" disabled title="待后端支持：需公网可访问的图片直链（OCR 识别 VIN）">🖼 图片</button>
        <button class="qq-btn-sm" disabled title="待后端支持：文件解析暂未开放">📎 文件</button>
      </div>
      <div class="inputbox">
        <textarea
          ref="taEl" v-model="input" class="ta"
          placeholder="输入聊天记录 / 询价内容…"
          rows="1"
          @input="autoGrow"
          @keydown="onKeydown"
        ></textarea>
        <div class="sendrow">
          <span class="hint">Enter 发送 · Shift+Enter 换行</span>
          <button class="send" :disabled="sending" title="发送（Enter）" @click="send">
            <svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true">
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
  flex: 1 1 auto; min-height: 320px;
  display: flex; flex-direction: column; overflow: hidden;
  border: 1px solid var(--c-border); border-radius: var(--r-lg);
  background: var(--c-panel);
  box-shadow: 0 2px 10px rgba(31, 45, 61, 0.05);
}
.msgs {
  flex: 1; min-height: 0; overflow-y: auto;
  padding: 10px 11px; display: flex; flex-direction: column; gap: 7px;
  background: var(--c-bg);
}
.msg { display: flex; gap: 6px; max-width: 92%; animation: msg-in 0.25s ease both; }
.msg.user { align-self: flex-end; flex-direction: row-reverse; }
.who {
  flex: none; width: 22px; height: 22px;
  border-radius: 7px; background: #cfd8e6; color: #fff;
  font-size: 10px; display: grid; place-items: center;
}
.msg.user .who { background: var(--c-primary); }
.bubble {
  padding: 6px 9px; border-radius: 10px; font-size: 11px;
  white-space: pre-wrap; word-break: break-all; line-height: 1.6;
}
.msg.user .bubble { background: var(--c-primary-soft); border: 1px solid #f9c7c5; border-top-right-radius: 4px; }
.msg.bot .bubble { background: var(--c-panel); border: 1px solid var(--c-border); border-top-left-radius: 4px; }
.bubble.need { background: var(--c-warn-soft); border-color: rgba(240, 130, 30, 0.3); }
@keyframes msg-in {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: none; }
}

.inputs {
  flex: none; padding: 6px 10px 7px;
  border-top: 1px solid var(--c-border); background: var(--c-panel);
  display: flex; flex-direction: column; gap: 4px;
}
.attach { display: flex; gap: 5px; }
/* 预留按钮：常置灰（待后端支持），覆盖公共款的可交互态 */
.attach .qq-btn-sm { color: var(--c-text-sub); cursor: not-allowed; }
.inputbox { display: flex; flex-direction: column; }
/* 输入框无感化：无边框无底色，融入底部操作栏（原型 .ai-textarea 同款） */
.ta {
  display: block; width: 100%;
  min-height: 60px; max-height: 160px;
  padding: 6px 8px;
  font: inherit; line-height: 1.5;
  color: var(--c-text); background: transparent;
  border: none; outline: none; resize: none; overflow-y: auto;
  transition: background 0.15s;
}
.ta:focus { background: rgba(31, 45, 61, 0.03); border-radius: var(--r-md); }
.sendrow { display: flex; align-items: center; justify-content: space-between; margin-top: 2px; }
.hint { font-size: 10px; color: var(--c-text-sub); }
.send {
  width: 26px; height: 26px;
  display: grid; place-items: center;
  background: var(--c-primary); color: #fff;
  border: none; border-radius: 8px; cursor: pointer;
  box-shadow: 0 1px 4px rgba(232, 32, 22, 0.28);
  transition: background 0.15s, transform 0.1s, box-shadow 0.15s;
}
.send:hover:not(:disabled) { background: var(--c-primary-deep); }
.send:active:not(:disabled) { transform: scale(0.93); }
.send:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
