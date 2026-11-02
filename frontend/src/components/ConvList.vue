<script setup>
/** 左栏：会话列表（微信风格搜索框 + 紧凑密度）。置顶优先 + 时间倒序由后端排好，这里直接渲染。 */
import { computed, ref } from 'vue'
import { useChatStore } from '../stores/chat'
import { fmtTime, highlight, matchKeyword } from '../utils/format'
import UnreadBadge from './UnreadBadge.vue'

const chat = useChatStore()

const keyword = ref('')

/** 本地过滤：命中会话名或 wxid 才显示（微信同款即时搜索）。 */
const filtered = computed(() =>
  chat.conversations.filter((c) => matchKeyword([c.name, c.wxid], keyword.value)))

function first(c) {
  const s = c.name || c.wxid || '?'
  return s.slice(0, 1).toUpperCase()
}
</script>

<template>
  <div class="conv-list">
    <div class="head">
      <div class="search">
        <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
        <input v-model="keyword" type="text" placeholder="搜索会话">
        <button v-if="keyword" class="clear" aria-label="清空搜索" @click="keyword = ''">
          <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
        </button>
      </div>
    </div>

    <el-scrollbar class="scroll">
      <div
        v-for="(c, i) in filtered"
        :key="c.id"
        class="item"
        :class="{ active: c.id === chat.currentId }"
        :style="{ animationDelay: i * 35 + 'ms' }"
        @click="chat.selectConversation(c.id)"
      >
        <img v-if="c.avatar" class="avatar img" :src="c.avatar" alt="" referrerpolicy="no-referrer" />
        <span v-else class="avatar" :class="{ group: c.chat_type === 2 }">{{ first(c) }}</span>
        <div class="body">
          <div class="row1">
            <!-- 命中关键词高亮（v-html 内容来自本地数据 + highlight 已转义） -->
            <span class="name" v-html="highlight(c.name || c.wxid || '', keyword)"></span>
            <span class="time num">{{ fmtTime(c.last_msg_at) }}</span>
          </div>
          <div class="row2">
            <span class="preview">{{ c.last_msg || '（暂无消息）' }}</span>
            <span class="flags">
              <span v-if="c.pinned" class="pin">置顶</span>
              <UnreadBadge :count="c.unread_count" />
            </span>
          </div>
        </div>
      </div>

      <el-empty
        v-if="!filtered.length"
        :description="keyword ? '没有匹配的会话' : '暂无会话'"
        :image-size="60"
      />
    </el-scrollbar>
  </div>
</template>

<style scoped>
.conv-list { display: flex; flex-direction: column; height: 100%; }
.head {
  padding: 10px 12px 8px;
  border-bottom: 1px solid var(--c-border);
}

/* 微信风格搜索框：圆角灰底，聚焦浮起 */
.search {
  display: flex; align-items: center; gap: 6px;
  height: 28px; padding: 0 8px;
  border-radius: var(--r-sm);
  background: #eef1f6;
  color: var(--c-text-sub);
  transition: box-shadow 0.15s, background 0.15s;
}
.search:focus-within {
  background: #fff;
  box-shadow: 0 0 0 1px var(--c-primary) inset;
}
.search input {
  flex: 1; min-width: 0;
  border: none; outline: none; background: none;
  font-size: 12px; color: var(--c-text);
}
.search input::placeholder { color: var(--c-text-sub); }
.clear {
  display: flex; align-items: center; justify-content: center;
  width: 16px; height: 16px; padding: 0;
  border: none; border-radius: 50%;
  background: #c6ccd6; color: #fff;
  cursor: pointer; flex-shrink: 0;
}
.clear:hover { background: var(--c-text-sub); }
.name :deep(mark) { background: none; color: var(--c-primary); font-weight: 600; padding: 0; }

.scroll { flex: 1; }

.item {
  display: flex; gap: 9px;
  padding: 8px 12px;
  cursor: pointer;
  user-select: none;
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
.avatar.img { object-fit: cover; background: var(--c-surface); }

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
</style>
