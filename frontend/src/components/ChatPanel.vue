<script setup>
/** 中栏：聊天窗 + 输入框。消息行渲染见 MessageRow.vue（气泡/灰条/卡片），输入与发送见 ChatComposer.vue。 */
import { computed, nextTick, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useChatStore } from '../stores/chat'
import { displayNameOf } from '../utils/format'
import { msgTextOf } from '../utils/message'
import { mediaUrlOf } from '../utils/media'
import { copyImageFromUrl, copyText } from '../utils/clipboard'
import { buildTimeline } from '../utils/timeline'
import MessageRow from './MessageRow.vue'
import ContextMenu from './ContextMenu.vue'
import ChatComposer from './ChatComposer.vue'

const chat = useChatStore()
const scroller = ref(null)
const composerRef = ref(null)
const previewUrl = ref('') // 图片全屏预览地址

/* 骨架屏气泡宽度序列（错落更像真实对话） */
const SK = [200, 128, 168, 224, 96, 176]

const timeline = computed(() => buildTimeline(chat.currentMessages))

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

/* 撤回消息的"重新编辑"：原文回填输入框并聚焦（回填逻辑在 ChatComposer） */
function onReEdit(content) {
  composerRef.value?.fillAndFocus(content)
}

/* ---------- 消息右键菜单 ---------- */
const menu = ref(null) // { msg, x, y }；null 即收起

/* 菜单项随消息能力启停：图片走"复制图片"，其余文本类"复制"，
 * 语音/视频/表情暂无可复制内容（置灰），后续按需追加（转发/撤回/引用…） */
const menuItems = computed(() => {
  const m = menu.value?.msg
  if (!m) return []
  if (m.msg_type === 2) return [{ key: 'copy', label: '复制图片' }]
  return [{ key: 'copy', label: '复制', disabled: !msgTextOf(m) }]
})

/* 复制：文本写文本剪贴板，图片取原图转 PNG 写位图剪贴板；失败统一 toast */
async function onMenuSelect(key) {
  const m = menu.value?.msg
  menu.value = null
  if (!m || key !== 'copy') return
  try {
    if (m.msg_type === 2) {
      await copyImageFromUrl(mediaUrlOf(m, 1))
      ElMessage.success('已复制图片')
    } else {
      await copyText(msgTextOf(m))
      ElMessage.success('已复制')
    }
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

    <!-- 输入与发送（可拖高、Enter 发送），重新编辑经 ref 回填 -->
    <ChatComposer ref="composerRef" />
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
/* S1 滚动锚定：上方媒体加载改变高度时，浏览器原生把位移补偿回 scrollTop，
   视野不动（无宽高预占位的历史消息走此兜底；Safari 不支持时退化为现状） */
.scroll :deep(.el-scrollbar__wrap) { overflow-anchor: auto; }
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
</style>
