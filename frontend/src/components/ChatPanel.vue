<script setup>
/** 中栏：聊天窗 + 输入框。气泡带头像昵称；状态只区分 发送中/已发送/失败。 */
import { computed, nextTick, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useChatStore } from '../stores/chat'

const chat = useChatStore()
const input = ref('')
const scroller = ref(null)
const composerH = ref(52)

/* 顶部拖拽拉伸：按住输入框上边缘上下拖，向上拖=变高 */
let drag = null
function onGrabDown(e) {
  drag = { y: e.clientY, h: composerH.value }
  window.addEventListener('mousemove', onGrabMove)
  window.addEventListener('mouseup', onGrabUp)
}
function onGrabMove(e) {
  composerH.value = Math.min(300, Math.max(52, drag.h - (e.clientY - drag.y)))
}
function onGrabUp() {
  window.removeEventListener('mousemove', onGrabMove)
  window.removeEventListener('mouseup', onGrabUp)
  drag = null
}

const TYPE_LABEL = { 2: '[图片]', 3: '[文件]', 4: '[视频]', 5: '[链接]' }
const STATUS_LABEL = { 0: '发送中', 1: '已发送', 2: '失败' }

/* 相邻消息间隔超过 30 分钟时插一条时间分隔线（参照标准界面蓝色时间线） */
const timeline = computed(() => {
  const out = []
  let last = null
  for (const m of chat.currentMessages) {
    const t = m.create_time ? m.create_time.slice(0, 16) : null
    if (t && (!last || t !== last)) out.push({ type: 'time', id: 't' + m.id, label: m.create_time.slice(5, 16) })
    out.push({ type: 'msg', ...m })
    last = t
  }
  return out
})

/* 行头像：in=客户（群消息取发言人首字，单聊取会话名首字）；out=客服 */
function avatarOf(m) {
  if (m.direction === 2) return '客'
  const s = chat.currentConv?.chat_type === 2
    ? (m.sender_name || '客')
    : (chat.currentConv?.name || chat.currentConv?.wxid || '?')
  return s.slice(0, 1).toUpperCase()
}

/* 入方向消息的微信头像：仅单聊有（群成员头像后续接群成员接口） */
function picOf(m) {
  if (m.direction === 2) return null
  return chat.currentConv?.chat_type === 1 ? chat.currentConv?.avatar : null
}
function nameOf(m) {
  if (m.direction === 2) return '客服'
  return chat.currentConv?.chat_type === 2 ? (m.sender_name || '成员') : (chat.currentConv?.name || chat.currentConv?.wxid)
}

watch(
  () => [chat.currentId, chat.currentMessages.length],
  async () => {
    await nextTick()
    const el = scroller.value
    if (el) el.scrollTop = el.scrollHeight
  }
)

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
</script>

<template>
  <div class="chat">
    <div class="head">
      <template v-if="chat.currentConv">
        <span class="peer">{{ chat.currentConv.name || chat.currentConv.wxid }}</span>
        <el-tag v-if="chat.currentConv.chat_type === 2" size="small" type="info" effect="plain">群聊</el-tag>
        <span class="wxid num">{{ chat.currentConv.wxid }}</span>
      </template>
      <span v-else>选择左侧会话</span>
    </div>

    <el-scrollbar ref="scroller" class="scroll" @scroll="({ scrollTop }) => scrollTop === 0 && chat.loadOlderMessages()">
      <div v-if="chat.loadingMore" class="tip">加载更早的消息…</div>
      <el-empty v-if="!chat.currentId" description="← 先选一个会话" :image-size="80" />
      <div v-else class="msgs">
        <template v-for="row in timeline" :key="row.id">
          <div v-if="row.type === 'time'" class="time-line num">
            <span>{{ row.label }}</span>
          </div>
          <div v-else class="msg" :class="row.direction === 2 ? 'out' : 'in'">
            <img v-if="picOf(row)" class="avatar img" :src="picOf(row)" alt="" referrerpolicy="no-referrer" />
            <span v-else class="avatar" :class="row.direction === 2 ? 'agent' : 'client'">{{ avatarOf(row) }}</span>
            <div class="body">
              <div class="name">{{ nameOf(row) }}</div>
              <div class="bubble">
                <div v-if="row.msg_type === 2" class="img-ph">图片 {{ row.content }}</div>
                <div v-else-if="row.msg_type !== 1" class="content type-label">{{ TYPE_LABEL[row.msg_type] || '[未知类型]' }}</div>
                <div v-else class="content">{{ row.content }}</div>
                <div class="meta">
                  <span v-if="row.direction === 2" :class="['st', { fail: row.status === 2 }]">{{ STATUS_LABEL[row.status] }}</span>
                  <span class="num">{{ row.create_time?.slice(11, 16) }}</span>
                </div>
              </div>
            </div>
          </div>
        </template>
      </div>
    </el-scrollbar>

    <div class="editor">
      <div class="grab-bar" title="拖拽调整输入框高度" @mousedown.prevent="onGrabDown"><i></i></div>
      <div class="tools">
        <svg viewBox="0 0 24 24" class="ticon"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M8.5 10h.01M15.5 10h.01M8.5 14.5c1 1.2 2.2 1.8 3.5 1.8s2.5-.6 3.5-1.8" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
        <svg viewBox="0 0 24 24" class="ticon"><rect x="4" y="4" width="16" height="16" rx="2" fill="none" stroke="currentColor" stroke-width="1.6"/><circle cx="9.5" cy="9.5" r="1.6" fill="currentColor"/><path d="M5 17l4.5-4.5L13 16l3-3 3 3.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>
        <svg viewBox="0 0 24 24" class="ticon"><path d="M13 5H7a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><path d="M12 12l7-7m-4 0h4v4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
        <span class="hint">Ctrl+Enter 发送</span>
      </div>
      <div class="input-row">
        <textarea
          v-model="input"
          class="composer"
          :style="{ height: composerH + 'px' }"
          :disabled="!chat.currentId"
          placeholder="输入消息…"
          @keydown.ctrl.enter.prevent="onSend"
        ></textarea>
        <el-button type="primary" class="send" :disabled="!chat.currentId || !input.trim()" @click="onSend">发送</el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat { display: flex; flex-direction: column; height: 100%; }
.head {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--c-border);
  background: var(--c-panel);
}
.peer { font-weight: 600; font-size: 14px; }
.wxid { font-size: 11px; color: var(--c-text-sub); }
.scroll { flex: 1; background: var(--c-bg); }
.tip { text-align: center; color: var(--c-text-sub); font-size: 12px; padding: 8px; }

.time-line {
  display: flex; align-items: center; gap: 10px;
  margin: 14px 0 10px;
  color: var(--c-primary); font-size: 11px;
}
.time-line::before, .time-line::after {
  content: ''; flex: 1; height: 1px; background: #c9dbff;
}

.msgs { padding: 4px 16px 16px; }
.msg { display: flex; gap: 8px; margin-bottom: 12px; animation: pop 0.22s both; }
@keyframes pop {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: none; }
}
.msg.out { flex-direction: row-reverse; }

.avatar {
  width: 30px; height: 30px; flex-shrink: 0;
  border-radius: var(--r-sm);
  color: #fff; font-size: 13px; font-weight: 600;
  display: flex; align-items: center; justify-content: center;
  margin-top: 16px;
}
.avatar.client { background: var(--c-ok); }
.avatar.agent { background: var(--c-primary); }
.avatar.img { object-fit: cover; background: var(--c-surface); }

.body { max-width: 72%; min-width: 0; display: flex; flex-direction: column; }
.msg.out .body { align-items: flex-end; }
.name { font-size: 11px; color: var(--c-text-sub); margin-bottom: 2px; }

.bubble {
  padding: 7px 10px;
  border-radius: var(--r-lg);
  background: var(--c-panel);
  border: 1px solid var(--c-border);
  width: fit-content;
}
.msg.in .bubble { border-top-left-radius: 3px; }
.msg.out .bubble { background: var(--c-primary-soft); border-color: #c9dbff; border-top-right-radius: 3px; }
.img-ph {
  width: 150px; height: 100px;
  border-radius: var(--r-sm);
  background: linear-gradient(135deg, #dfe5ee, #c9d3e2);
  display: flex; align-items: center; justify-content: center;
  color: var(--c-text-sub); font-size: 12px;
}
.content { white-space: pre-wrap; word-break: break-word; line-height: 1.55; }
.type-label { color: var(--c-primary); }
.meta {
  margin-top: 3px; font-size: 10px; color: var(--c-text-sub);
  display: flex; gap: 8px; justify-content: flex-end;
}
.st.fail { color: var(--c-danger); font-weight: 600; }

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
.input-row { display: flex; gap: 10px; align-items: flex-end; }

/* 高度由顶部拖拽条控制，禁用原生 resize 手柄 */
.composer {
  flex: 1;
  font-family: var(--font-ui);
  font-size: 13px;
  color: var(--c-text);
  line-height: 1.5;
  padding: 7px 10px;
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
.send { min-width: 72px; height: 52px; }
</style>
