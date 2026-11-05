<script setup>
/** 中栏：聊天窗 + 输入框。消息行渲染见 MessageRow.vue（气泡/灰条/卡片）。 */
import { computed, nextTick, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useChatStore } from '../stores/chat'
import { displayNameOf } from '../utils/format'
import { msgTextOf } from '../utils/message'
import MessageRow from './MessageRow.vue'
import ContextMenu from './ContextMenu.vue'

const chat = useChatStore()
const input = ref('')
const scroller = ref(null)
const composerEl = ref(null)
const composerH = ref(72) // 底部要给悬浮发送按钮留位，最小高度随之加大
const previewUrl = ref('') // 图片全屏预览地址

/* 骨架屏气泡宽度序列（错落更像真实对话） */
const SK = [200, 128, 168, 224, 96, 176]

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

/* 时间分隔线：相邻消息间隔超过 5 分钟才插一条（此前按分钟变化就插，导致刷屏重复）。
   气泡上不再逐条显示时分，完整时间戳悬停气泡可见；标签按远近智能显示。 */
const TIME_GAP = 5 * 60 * 1000
const WEEK_CN = '日一二三四五六'

function timeLabel(t) {
  const d = new Date(String(t).replace(' ', 'T'))
  const now = new Date()
  const hm = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  const dayDiff = Math.floor(
    (new Date(now.getFullYear(), now.getMonth(), now.getDate()) -
      new Date(d.getFullYear(), d.getMonth(), d.getDate())) / 86400000
  )
  if (dayDiff <= 0) return hm
  if (dayDiff === 1) return `昨天 ${hm}`
  if (dayDiff < 7) return `星期${WEEK_CN[d.getDay()]} ${hm}`
  const md = `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  return d.getFullYear() === now.getFullYear() ? `${md} ${hm}` : `${d.getFullYear()}-${md} ${hm}`
}

const timeline = computed(() => {
  const out = []
  let last = null
  for (const m of chat.currentMessages) {
    const t = m.create_time ? Date.parse(String(m.create_time).replace(' ', 'T')) : NaN
    if (!Number.isNaN(t) && (last === null || t - last >= TIME_GAP)) {
      out.push({ type: 'time', id: 't' + m.id, label: timeLabel(m.create_time) })
    }
    out.push({ type: 'msg', ...m })
    if (!Number.isNaN(t)) last = t
  }
  return out
})

/* 置底：直接赋值 scrollTop，瞬时到位（不做平滑滚动） */
function stickBottom() {
  const w = scroller.value?.wrapRef
  if (w) w.scrollTop = w.scrollHeight
}

/* 是否贴在底部（±120px 容差）：媒体异步加载撑高时，只有贴底才重新锚定 */
let nearBottom = true
function maybeStickBottom() {
  if (nearBottom) stickBottom()
}

function onScroll({ scrollTop }) {
  if (scrollTop === 0) chat.loadOlderMessages()
  const w = scroller.value?.wrapRef
  if (w) nearBottom = w.scrollHeight - scrollTop - w.clientHeight < 120
}

/* 媒体加载完成由 MessageRow emit mediaload 通知，贴底锚定见 maybeStickBottom */

/* 切会话→定位到最新一条；追加新消息→贴底才跟随；上翻加载旧消息→保持视野不动。
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
      if (switched) nearBottom = true
      await nextTick()
      switched ? stickBottom() : maybeStickBottom()
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

/* Enter 发送 / Shift+Enter 换行（换行交还默认行为）。
   isComposing / keyCode 229：输入法选词时的回车不算发送 */
function onEnterKey(e) {
  if (e.shiftKey) return
  if (e.isComposing || e.keyCode === 229) return
  e.preventDefault()
  onSend()
}

/* 撤回消息的"重新编辑"：原文回填输入框并聚焦 */
async function onReEdit(content) {
  input.value = content
  await nextTick()
  composerEl.value?.focus()
}

/* ---------- 消息右键菜单 ---------- */
const menu = ref(null) // { msg, x, y }；null 即收起

/* 菜单项随消息能力启停：目前仅"复制"，后续按需追加（转发/撤回/引用…） */
const menuItems = computed(() => {
  const m = menu.value?.msg
  if (!m) return []
  return [{ key: 'copy', label: '复制', disabled: !msgTextOf(m) }]
})

/* 复制：写剪贴板 + toast；纯媒体消息置灰进不来这里 */
async function onMenuSelect(key) {
  const m = menu.value?.msg
  menu.value = null
  if (!m || key !== 'copy') return
  try {
    await navigator.clipboard.writeText(msgTextOf(m))
    ElMessage.success('已复制')
  } catch {
    ElMessage.error('复制失败，请重试')
  }
}
</script>

<template>
  <!-- 鼠标在会话窗口内任意位置按下即算已读（含标题栏、消息区、空白、输入框、拖拽条） -->
  <div class="chat" @mousedown="chat.markCurrentRead()">
    <div class="head">
      <template v-if="chat.currentConv">
        <span class="peer">{{ displayNameOf(chat.currentConv) }}</span>
        <el-tag v-if="chat.currentConv.chat_type === 2" size="small" type="info" effect="plain">群聊</el-tag>
      </template>
      <span v-else>选择左侧会话</span>
    </div>

    <el-scrollbar ref="scroller" class="scroll" @scroll="onScroll">
      <div v-if="chat.loadingMore" class="tip">加载更早的消息…</div>
      <div v-if="chat.loadingMessages" class="skeleton" aria-hidden="true">
        <div v-for="(s, i) in SK" :key="i" class="sk-row" :class="i % 2 ? 'out' : 'in'">
          <span class="sk-ava"></span>
          <span class="sk-bubble" :style="{ width: s + 'px' }"></span>
        </div>
      </div>
      <el-empty v-else-if="!chat.currentId" description="← 先选一个会话" :image-size="80" />
      <div v-else class="msgs" :key="chat.currentId">
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
            @mediaload="maybeStickBottom"
            @menu="menu = $event"
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

    <!-- 消息右键菜单：弹层职责在 ContextMenu（定位翻转/收起生命周期） -->
    <ContextMenu :pos="menu" :items="menuItems" @select="onMenuSelect" @close="menu = null" />

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

/* 时间分隔线：居中小胶囊，只在时间断层出现（与 badge 同风格），不再通栏压线 */
.time-line { display: flex; justify-content: center; margin: 14px 0 10px; }
.time-line span {
  font-size: 11px; line-height: 1;
  color: var(--c-primary);
  background: var(--c-primary-soft);
  padding: 4px 10px;
  border-radius: 999px;
  user-select: none;
}

/* 骨架屏：进会话先给呼吸占位，避免白屏后整批气泡突现 */
.skeleton { padding: 18px 16px 4px; }
.sk-row { display: flex; gap: 8px; margin-bottom: 18px; }
.sk-row.out { flex-direction: row-reverse; }
.sk-ava { width: 30px; height: 30px; flex-shrink: 0; border-radius: var(--r-sm); }
.sk-bubble { height: 34px; border-radius: var(--r-lg); }
.sk-ava, .sk-bubble {
  background: linear-gradient(100deg, #e2e8f2 40%, #f3f6fb 50%, #e2e8f2 60%);
  background-size: 200% 100%;
  animation: shimmer 1.1s linear infinite;
}
@keyframes shimmer { to { background-position: -200% 0; } }

/* 数据到位后容器整体淡入（:key 切会话重挂载触发）；之后单条新消息仍走 .msg 的 pop */
.msgs { padding: 4px 16px 16px; animation: list-in 0.18s ease-out; }
@keyframes list-in { from { opacity: 0; } to { opacity: 1; } }

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
