<script setup>
/** 中栏：聊天窗 + 输入框。气泡方向=direction；状态只区分 发送中/已发送/失败。 */
import { nextTick, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useChatStore } from '../stores/chat'

const chat = useChatStore()
const input = ref('')
const scroller = ref(null)

const TYPE_LABEL = { 2: '[图片]', 3: '[文件]', 4: '[视频]', 5: '[链接]' }
const STATUS_LABEL = { 0: '发送中', 1: '已发送', 2: '失败' }

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
    <div class="head">{{ chat.currentConv ? (chat.currentConv.name || chat.currentConv.wxid) : '选择左侧会话' }}</div>

    <el-scrollbar ref="scroller" class="scroll" @scroll="({ scrollTop }) => scrollTop === 0 && chat.loadOlderMessages()">
      <div v-if="chat.loadingMore" class="tip">加载更早的消息…</div>
      <el-empty v-if="!chat.currentId" description="← 先选一个会话" :image-size="80" />
      <div v-else class="msgs">
        <div v-for="m in chat.currentMessages" :key="m.id" class="msg" :class="m.direction === 2 ? 'out' : 'in'">
          <div class="bubble">
            <div v-if="m.msg_type !== 1" class="content type-label">{{ TYPE_LABEL[m.msg_type] || '[未知类型]' }}</div>
            <div v-else class="content">{{ m.content }}</div>
            <div class="meta">
              <span v-if="m.direction === 2" :class="['st', { fail: m.status === 2 }]">{{ STATUS_LABEL[m.status] }}</span>
              <span>{{ m.create_time?.slice(11, 16) }}</span>
            </div>
          </div>
        </div>
      </div>
    </el-scrollbar>

    <div class="editor">
      <el-input
        v-model="input"
        type="textarea"
        :rows="3"
        :disabled="!chat.currentId"
        placeholder="输入消息，Ctrl+Enter 发送"
        @keydown.ctrl.enter.prevent="onSend"
      />
      <el-button type="primary" :disabled="!chat.currentId || !input.trim()" @click="onSend">发送</el-button>
    </div>
  </div>
</template>

<style scoped>
.chat { display: flex; flex-direction: column; height: 100%; }
.head {
  padding: 14px 20px; font-weight: 600;
  border-bottom: 1px solid var(--c-border);
}
.scroll { flex: 1; }
.tip { text-align: center; color: var(--c-text-sub); font-size: 12px; padding: 8px; }

.msgs { padding: 16px 20px; }
.msg { display: flex; margin-bottom: 14px; }
.msg.out { justify-content: flex-end; }
.bubble {
  max-width: 70%;
  padding: 8px 12px;
  border-radius: var(--r-lg);
  background: var(--c-bg);
}
.msg.out .bubble { background: #e8f0ff; }
.content { white-space: pre-wrap; word-break: break-word; }
.type-label { color: var(--c-primary); }
.meta {
  margin-top: 4px; font-size: 11px; color: var(--c-text-sub);
  display: flex; gap: 8px; justify-content: flex-end;
}
.st.fail { color: var(--c-danger); }

.editor {
  padding: 12px 20px; border-top: 1px solid var(--c-border);
  display: flex; gap: 12px; align-items: flex-end;
}
.editor .el-button { height: 54px; }
</style>
