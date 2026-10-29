<script setup>
/** 左栏：会话列表（紧凑密度）。置顶优先 + 时间倒序由后端排好，这里直接渲染。 */
import { useChatStore } from '../stores/chat'

const chat = useChatStore()

function fmtTime(t) {
  if (!t) return ''
  return t.slice(5, 16) // MM-DD HH:MM
}

function first(c) {
  const s = c.name || c.wxid || '?'
  return s.slice(0, 1).toUpperCase()
}
</script>

<template>
  <div class="conv-list">
    <div class="head">
      <span class="title">会话 <em class="num">{{ chat.conversations.length }}</em></span>
      <el-button text size="small" @click="chat.loadConversations()">刷新</el-button>
    </div>

    <el-scrollbar class="scroll">
      <div
        v-for="(c, i) in chat.conversations"
        :key="c.id"
        class="item"
        :class="{ active: c.id === chat.currentId }"
        :style="{ animationDelay: i * 35 + 'ms' }"
        @click="chat.selectConversation(c.id)"
      >
        <span class="avatar" :class="{ group: c.chat_type === 2 }">{{ first(c) }}</span>
        <div class="body">
          <div class="row1">
            <span class="name">{{ c.name || c.wxid }}</span>
            <span class="time num">{{ fmtTime(c.last_msg_at) }}</span>
          </div>
          <div class="row2">
            <span class="preview">{{ c.last_msg || '（暂无消息）' }}</span>
            <span class="flags">
              <span v-if="c.pinned" class="pin">置顶</span>
              <span v-if="c.unread_count > 0" class="badge num">{{ c.unread_count > 99 ? '99+' : c.unread_count }}</span>
            </span>
          </div>
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
  padding: 10px 12px 8px;
  border-bottom: 1px solid var(--c-border);
}
.title { font-weight: 600; font-size: 13px; }
.title em { font-style: normal; color: var(--c-text-sub); font-size: 12px; margin-left: 4px; }
.scroll { flex: 1; }

.item {
  display: flex; gap: 9px;
  padding: 8px 12px;
  cursor: pointer;
  position: relative;
  border-bottom: 1px solid #f2f4f8;
  animation: slide-in 0.28s both;
}
@keyframes slide-in {
  from { opacity: 0; transform: translateX(-8px); }
  to { opacity: 1; transform: none; }
}
.item::before {
  content: '';
  position: absolute; left: 0; top: 6px; bottom: 6px; width: 3px;
  background: var(--c-primary);
  transform: scaleY(0);
  transition: transform 0.18s;
}
.item:hover { background: #f6f8fb; }
.item.active { background: var(--c-primary-soft); }
.item.active::before { transform: scaleY(1); }

.avatar {
  width: 32px; height: 32px; flex-shrink: 0;
  border-radius: var(--r-sm);
  background: var(--c-primary);
  color: #fff; font-size: 14px; font-weight: 600;
  display: flex; align-items: center; justify-content: center;
}
.avatar.group { background: var(--c-ok); }

.body { flex: 1; min-width: 0; }
.row1 { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.name {
  font-weight: 500; font-size: 13px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.time { font-size: 11px; color: var(--c-text-sub); flex-shrink: 0; }
.row2 { display: flex; justify-content: space-between; align-items: center; margin-top: 2px; gap: 8px; }
.preview {
  color: var(--c-text-sub); font-size: 12px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.flags { display: flex; align-items: center; gap: 5px; flex-shrink: 0; }
.pin {
  font-size: 10px; color: var(--c-primary);
  border: 1px solid var(--c-primary);
  border-radius: 3px; padding: 0 3px; line-height: 14px;
}
.badge {
  min-width: 16px; height: 16px; padding: 0 4px;
  border-radius: 8px; background: var(--c-danger); color: #fff;
  font-size: 11px; line-height: 16px; text-align: center;
}
</style>
