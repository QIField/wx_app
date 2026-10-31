<script setup>
/** 中栏：聊天窗 + 输入框。消息行渲染见 MessageRow.vue（气泡/灰条/卡片）。 */
import { computed, nextTick, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useChatStore } from '../stores/chat'
import MessageRow from './MessageRow.vue'

const chat = useChatStore()
const input = ref('')
const scroller = ref(null)
const composerEl = ref(null)
const composerH = ref(52)
const previewUrl = ref('') // 图片全屏预览地址

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

/* 置底：直接赋值 scrollTop，瞬时到位（不做平滑滚动） */
function stickBottom() {
  const w = scroller.value?.wrapRef
  if (w) w.scrollTop = w.scrollHeight
}

/* 切会话→定位到最新一条；追加新消息→跟到底；上翻加载旧消息→保持视野不动。
   监听数组引用而非仅长度：切会话时新旧消息数量常相同，只看长度不会触发。
   flush 默认 pre：DOM 更新前先量旧高度，供加载旧消息后做高度补偿。 */
watch(
  () => [chat.currentId, chat.currentMessages, chat.currentMessages.length],
  async ([id, msgs], [prevId, prevMsgs] = []) => {
    if (!id) return
    const wrap = scroller.value?.wrapRef
    if (!wrap) return
    const switched = id !== prevId
    const appended =
      !switched && msgs[msgs.length - 1]?.id !== prevMsgs?.[prevMsgs.length - 1]?.id
    if (switched || appended) {
      await nextTick()
      stickBottom()
    } else if (msgs[0]?.id !== prevMsgs?.[0]?.id) {
      const prevH = wrap.scrollHeight
      const prevTop = wrap.scrollTop
      await nextTick()
      const w = scroller.value?.wrapRef
      if (w) w.scrollTop = w.scrollHeight - prevH + prevTop
    }
  },
  { immediate: true }
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

/* 撤回消息的"重新编辑"：原文回填输入框并聚焦 */
async function onReEdit(content) {
  input.value = content
  await nextTick()
  composerEl.value?.focus()
}
</script>

<template>
  <div class="chat">
    <div class="head">
      <template v-if="chat.currentConv">
        <span class="peer">{{ chat.currentConv.name || chat.currentConv.wxid }}</span>
        <el-tag v-if="chat.currentConv.chat_type === 2" size="small" type="info" effect="plain">群聊</el-tag>
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
          <MessageRow
            v-else
            :msg="row"
            :conv="chat.currentConv"
            @preview="previewUrl = $event"
            @reedit="onReEdit"
          />
        </template>
      </div>
    </el-scrollbar>

    <!-- 图片全屏预览 -->
    <el-image-viewer
      v-if="previewUrl"
      :url-list="[previewUrl]"
      hide-on-click-modal
      @close="previewUrl = ''"
    />

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
          ref="composerEl"
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
.peer { font-weight: 600; font-size: 14px; user-select: none; }
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
