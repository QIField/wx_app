<script setup>
/** 联系人/群聊详情卡（Phase 1 字段）：账号信息 + 发消息入口。 */
import { computed, onUnmounted, ref } from 'vue'
import { useContactsStore } from '../stores/contacts'
import { useChatStore } from '../stores/chat'
import { fmtTime } from '../utils/format'

const emit = defineEmits(['enter-chat'])
const contacts = useContactsStore()
const chat = useChatStore()

const contact = computed(() => contacts.selectedContact)
const typeName = computed(() => (contact.value?.chat_type === 2 ? '群聊' : '好友'))
const hint = ref('')
let hintTimer = null
onUnmounted(() => clearTimeout(hintTimer))

/** 发消息：按 wxid+类型 匹配现有会话并切换；无会话时行内提示。 */
async function enterChat() {
  const c = contact.value
  if (!c) return
  const conv = chat.conversations.find(
    (x) => x.wxid === c.wxid && x.chat_type === c.chat_type)
  if (!conv) {
    hint.value = '该联系人暂无会话记录'
    clearTimeout(hintTimer)
    hintTimer = setTimeout(() => (hint.value = ''), 2200)
    return
  }
  await chat.selectConversation(conv.id)
  emit('enter-chat')
}
</script>

<template>
  <div class="contact-detail">
    <template v-if="contact">
      <div class="d-head">
        <img v-if="contact.avatar" class="avatar img" :src="contact.avatar" alt="" referrerpolicy="no-referrer">
        <span v-else class="avatar" :class="{ group: contact.chat_type === 2 }">{{ contact.name.slice(0, 1) }}</span>
        <div class="d-title">
          <div class="d-name">{{ contact.name }}</div>
          <div class="d-sub num">微信号：{{ contact.wxid }}</div>
        </div>
        <span class="type-chip">{{ typeName }}</span>
      </div>

      <div class="d-sec">账号信息</div>
      <div class="kv">
        <div class="kv-row"><span class="k">类型</span><span>{{ typeName }}</span></div>
        <div class="kv-row"><span class="k">最近活跃</span><span class="num">{{ fmtTime(contact.last_msg_at) || '—' }}</span></div>
        <div class="kv-row"><span class="k">未读消息</span><span class="num">{{ contact.unread_count }}</span></div>
        <div class="kv-row"><span class="k">置顶</span><span>{{ contact.pinned ? '已置顶' : '否' }}</span></div>
      </div>

      <div class="d-sec">最后消息</div>
      <div class="d-note">{{ contact.last_msg || '（暂无消息）' }}</div>

      <div class="d-actions">
        <el-button type="primary" size="small" @click="enterChat">发消息</el-button>
        <span v-if="hint" class="hint">{{ hint }}</span>
      </div>
    </template>

    <div v-else class="empty">
      <svg viewBox="0 0 24 24" width="38" height="38" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" />
      </svg>
      <p>在左侧选择好友或群聊查看资料</p>
      <p class="kbd-tip">按 <kbd>/</kbd> 快速搜索联系人</p>
    </div>
  </div>
</template>

<style scoped>
.contact-detail { height: 100%; overflow-y: auto; }

.d-head {
  display: flex; align-items: center; gap: 14px;
  padding: 18px 20px;
  border-bottom: 1px solid var(--c-border);
  background: linear-gradient(180deg, #fafbfd, #fff);
}
.avatar {
  width: 52px; height: 52px; flex-shrink: 0;
  border-radius: var(--r-md);
  background: var(--c-primary);
  color: #fff; font-size: 20px; font-weight: 600;
  display: flex; align-items: center; justify-content: center;
}
.avatar.group { background: var(--c-ok); }
.avatar.img { object-fit: cover; background: var(--c-surface); }
.d-title { flex: 1; min-width: 0; }
.d-name { font-size: 17px; font-weight: 600; }
.d-sub { margin-top: 3px; font-size: 12px; color: var(--c-text-sub); }
.type-chip {
  flex-shrink: 0;
  font-size: 11px; line-height: 18px;
  padding: 0 8px; border-radius: 3px;
  background: var(--c-primary-soft); color: var(--c-primary-deep);
  border: 1px solid #b9d0ff;
}

.d-sec {
  padding: 12px 20px 6px;
  font-size: 11px; font-weight: 700; letter-spacing: 1px;
  color: var(--c-text-sub);
}
.kv { padding: 0 20px; }
.kv-row {
  display: flex; gap: 12px;
  padding: 6px 0;
  border-bottom: 1px dashed #eef1f6;
  font-size: 12.5px;
}
.kv-row:last-child { border-bottom: none; }
.k { width: 64px; flex-shrink: 0; color: var(--c-text-sub); }

.d-note {
  margin: 0 20px;
  padding: 8px 10px;
  font-size: 12.5px; line-height: 1.6;
  color: var(--c-text);
  background: #f8fafd;
  border-radius: var(--r-sm);
  border-left: 3px solid var(--c-border-strong);
}

.d-actions {
  display: flex; align-items: center; gap: 10px;
  padding: 16px 20px 20px;
  margin-top: 10px;
  border-top: 1px solid var(--c-border);
  background: #fafbfd;
}
.hint { font-size: 11.5px; color: var(--c-warn); }

.empty {
  height: 100%;
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px;
  color: var(--c-text-sub);
}
.empty p { margin: 0; font-size: 12.5px; }
.kbd-tip kbd {
  font-family: var(--font-num, 'Bahnschrift');
  font-size: 11px;
  border: 1px solid var(--c-border-strong);
  border-bottom-width: 2px; border-radius: 3px;
  padding: 0 5px; color: var(--c-text-sub);
  background: #f8fafd;
}
</style>
