<script setup>
/** 单条消息气泡：msg_type=1 文本经 renderEmojiHtml 渲染（[码]→微信表情图，
 *  Unicode 原生显示），msg_type=7 走贴边图片气泡（对应 wx_app 已有能力）。
 *  平移到 wx_app 时：MessageRow.vue 的 `<div class="content">{{ msg.content }}</div>`
 *  替换为 `<div class="content" v-html="renderEmojiHtml(msg.content)"></div>` 即可。
 */
import { computed } from 'vue'
import { renderEmojiHtml } from '../utils/emoji'

const props = defineProps({
  msg: { type: Object, required: true },
})

const isOut = computed(() => props.msg.direction === 2)
const html = computed(() =>
  props.msg.msg_type === 1 ? renderEmojiHtml(props.msg.content) : ''
)
const avatar = computed(() => (props.msg.sender || '?').slice(0, 1))
const STATUS_LABEL = { 0: '发送中', 1: '已发送', 2: '失败' }
</script>

<template>
  <div class="msg" :class="isOut ? 'out' : 'in'">
    <span class="avatar" :class="isOut ? 'agent' : 'client'">{{ avatar }}</span>
    <div class="body">
      <div class="name">{{ msg.sender }}</div>
      <div class="bubble" :class="{ tight: msg.msg_type === 7 }">
        <div v-if="msg.msg_type === 1" class="content" v-html="html"></div>
        <img v-else-if="msg.msg_type === 7" class="sticker" :src="msg.content" alt="表情" />
        <div v-else class="content type-label">[未知类型]</div>
        <div v-if="isOut && msg.status !== undefined" class="meta">
          <span :class="['st', { fail: msg.status === 2 }]">{{ STATUS_LABEL[msg.status] || '' }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.msg { display: flex; gap: 8px; margin-bottom: 14px; animation: pop 0.22s both; }
@keyframes pop {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: none; }
}
.msg.out { flex-direction: row-reverse; }

.avatar {
  width: 32px; height: 32px; flex-shrink: 0;
  border-radius: var(--r-sm);
  color: #fff; font-size: 13px; font-weight: 600;
  display: flex; align-items: center; justify-content: center;
  margin-top: 16px; user-select: none;
}
.avatar.client { background: var(--c-ok); }
.avatar.agent { background: var(--c-primary); }

.body { max-width: 72%; display: flex; flex-direction: column; }
.msg.out .body { align-items: flex-end; }
.name { font-size: 11px; color: var(--c-text-sub); margin-bottom: 2px; user-select: none; }
.msg.out .name { color: var(--c-primary); font-weight: 600; }

.bubble {
  padding: 7px 10px;
  border-radius: var(--r-lg);
  background: var(--c-panel);
  border: 1px solid var(--c-border);
  width: fit-content;
}
.msg.in .bubble { border-top-left-radius: 3px; }
.msg.out .bubble { background: var(--c-primary-soft); border-color: #c9dbff; border-top-right-radius: 3px; }
.bubble.tight { padding: 0; background: none; border: none; }

.content { white-space: pre-wrap; word-break: break-word; line-height: 1.55; font-size: 14px; }
.type-label { color: var(--c-primary); }
.sticker { display: block; width: 100px; image-rendering: auto; }

.meta { margin-top: 3px; font-size: 10px; color: var(--c-text-sub); display: flex; justify-content: flex-end; }
.st.fail { color: var(--c-danger); font-weight: 600; }
</style>
