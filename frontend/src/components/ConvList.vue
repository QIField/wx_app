<script setup>
/** 左栏：会话列表（微信风格搜索框 + 紧凑密度）。置顶优先 + 时间倒序由后端排好，这里直接渲染。
 *  右键菜单：置顶⇄取消置顶 / 标为未读⇄已读 / 消息免打扰；置顶仅背景加深不显示文字。 */
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useChatStore } from '../stores/chat'
import { displayNameOf, fmtTime, highlight, matchKeyword } from '../utils/format'
import ContextMenu from './ContextMenu.vue'
import ContactAvatar from './ContactAvatar.vue'
import UnreadBadge from './UnreadBadge.vue'

const chat = useChatStore()

const keyword = ref('')

/** 本地过滤：命中展示名（含「匿名 编码」）才显示（wxid 已不在前端数据里）。 */
const filtered = computed(() =>
  chat.conversations.filter((c) => matchKeyword([displayNameOf(c)], keyword.value)))

/* ---------- 右键菜单 ---------- */
const menu = ref(null) // { conv, x, y }；null 即收起

function onMenu(e, conv) {
  menu.value = { conv, x: e.clientX, y: e.clientY }
}

/** 菜单项随目标会话状态切换；免打扰为勾选开关项。 */
const menuItems = computed(() => {
  const c = menu.value?.conv
  if (!c) return []
  return [
    { key: 'pin', label: c.pinned ? '取消置顶' : '置顶' },
    { key: 'unread', label: c.unread_count > 0 ? '标为已读' : '标为未读' },
    { key: 'mute', label: '消息免打扰', checked: !!c.muted, sepBefore: true },
  ]
})

/** 菜单动作：乐观更新 → 落库（store 内失败自动回滚），这里只管提示。 */
async function onMenuSelect(key) {
  const conv = menu.value?.conv
  menu.value = null
  if (!conv) return
  let patch
  if (key === 'pin') patch = { pinned: conv.pinned ? 0 : 1 }
  else if (key === 'unread') patch = { read: conv.unread_count > 0 }
  else patch = { muted: conv.muted ? 0 : 1 }
  try {
    await chat.patchConversation(conv, patch)
  } catch (e) {
    ElMessage.error(e.message || '操作失败')
  }
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
        :class="{ active: c.id === chat.currentId, pinned: c.pinned }"
        :style="{ animationDelay: i * 35 + 'ms' }"
        @click="chat.selectConversation(c.id)"
        @contextmenu.prevent="onMenu($event, c)"
      >
        <ContactAvatar :name="c.name" :alias="c.alias" :avatar="c.avatar" :chat-type="c.chat_type" class="avatar" />
        <div class="body">
          <div class="row1">
            <!-- 命中关键词高亮（v-html 内容来自本地数据 + highlight 已转义） -->
            <span class="name" v-html="highlight(displayNameOf(c), keyword)"></span>
            <span class="time num">{{ fmtTime(c.last_msg_at) }}</span>
          </div>
          <div class="row2">
            <span class="preview">{{ c.last_msg || '（暂无消息）' }}</span>
            <span class="flags">
              <!-- 免打扰：摘要旁铃铛斜杠；未读数字退化为纯红点（微信同款） -->
              <span v-if="c.muted" class="mute" title="消息免打扰">
                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13.73 21a2 2 0 0 1-3.46 0"/><path d="M18.63 13A17.89 17.89 0 0 1 18 8"/><path d="M6.26 6.26A5.86 5.86 0 0 0 6 8c0 7-3 9-3 9h14"/><path d="M18 8a6 6 0 0 0-9.33-5"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
              </span>
              <UnreadBadge :count="c.unread_count" :dot="!!c.muted" />
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

    <!-- 会话右键菜单：弹层职责在 ContextMenu（定位翻转/收起生命周期） -->
    <ContextMenu :pos="menu" :items="menuItems" @select="onMenuSelect" @close="menu = null" />
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
/* 置顶会话：背景加深即可（不显示"置顶"文字），选中态优先 */
.item.pinned { background: #e9edf4; }
.item.pinned:hover { background: #e2e8f2; }
.item.active,
.item.active:hover,
.item.active.pinned { background: var(--c-primary-soft); }
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
.mute { display: inline-flex; color: var(--c-text-sub); }
</style>
