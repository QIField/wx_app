<script setup>
/** 左栏：会话列表。置顶优先 + 时间倒序由后端排好，这里直接渲染。 */
import { useChatStore } from '../stores/chat'

const chat = useChatStore()

function fmtTime(t) {
  if (!t) return ''
  return t.slice(5, 16) // MM-DD HH:MM
}
</script>

<template>
  <div class="conv-list">
    <div class="head">
      <span class="title">会话</span>
      <el-button text size="small" @click="chat.loadConversations()">刷新</el-button>
    </div>

    <el-scrollbar class="scroll">
      <div
        v-for="c in chat.conversations"
        :key="c.id"
        class="item"
        :class="{ active: c.id === chat.currentId }"
        @click="chat.selectConversation(c.id)"
      >
        <div class="row1">
          <span class="name">
            {{ c.name || c.wxid }}
            <el-tag v-if="c.chat_type === 2" size="small" type="info" effect="plain">群</el-tag>
          </span>
          <span class="time">{{ fmtTime(c.last_msg_at) }}</span>
        </div>
        <div class="row2">
          <span class="preview">{{ c.last_msg || '（暂无消息）' }}</span>
          <span v-if="c.unread_count > 0" class="badge">{{ c.unread_count > 99 ? '99+' : c.unread_count }}</span>
        </div>
      </div>

      <el-empty v-if="!chat.conversations.length" description="暂无会话" :image-size="60" />
    </el-scrollbar>
  </div>
</template>

<style scoped>
.conv-list { display: flex; flex-direction: column; height: 100%; }
.head {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 16px 10px;
}
.title { font-weight: 600; }
.scroll { flex: 1; }

.item {
  padding: 10px 16px; cursor: pointer;
  border-left: 3px solid transparent;
}
.item:hover { background: var(--c-bg); }
.item.active { background: var(--c-bg); border-left-color: var(--c-primary); }

.row1 { display: flex; justify-content: space-between; align-items: center; }
.name { font-weight: 500; }
.time { font-size: 12px; color: var(--c-text-sub); }
.row2 { display: flex; justify-content: space-between; margin-top: 4px; }
.preview {
  color: var(--c-text-sub); font-size: 13px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  max-width: 210px;
}
.badge {
  min-width: 18px; height: 18px; padding: 0 5px;
  border-radius: 9px; background: var(--c-danger); color: #fff;
  font-size: 12px; line-height: 18px; text-align: center; flex-shrink: 0;
}
</style>
