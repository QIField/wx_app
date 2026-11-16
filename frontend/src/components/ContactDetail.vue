<script setup>
/** 联系人/群聊详情卡：账号信息 + 统一备注编辑器（业务自建）+ 发消息入口。 */
import { computed, onUnmounted, ref } from 'vue'
import { useContactsStore } from '../stores/contacts'
import { useChatStore } from '../stores/chat'
import { displayNameOf, fmtTime, nameResolved } from '../utils/format'
import { fetchRemarkConfig, saveRemarkConfig } from '../api'
import ContactAvatar from './ContactAvatar.vue'
import RemarkEditor from './RemarkEditor.vue'

const emit = defineEmits(['enter-chat'])
const contacts = useContactsStore()
const chat = useChatStore()

const contact = computed(() => contacts.selectedContact)
const typeName = computed(() => (contact.value?.chat_type === 2 ? '群聊' : '好友'))
const hint = ref('')
let hintTimer = null
onUnmounted(() => clearTimeout(hintTimer))

/** 发消息：按 contact_id 建/取会话再进（后端校验归属；不传 wxid——脱敏契约）。 */
const opening = ref(false)
async function enterChat() {
  const c = contact.value
  if (!c || opening.value) return
  opening.value = true
  try {
    await chat.openWithContact(c.id, c.chat_type, c.conversation_id)
    emit('enter-chat')
  } catch (e) {
    hint.value = e.message || '发起会话失败'
    clearTimeout(hintTimer)
    hintTimer = setTimeout(() => (hint.value = ''), 2200)
  } finally {
    opening.value = false
  }
}
</script>

<template>
  <div class="contact-detail">
    <template v-if="contact">
      <div class="d-head">
        <ContactAvatar
          :name="contact.name"
          :alias="contact.alias"
          :avatar="contact.avatar"
          :chat-type="contact.chat_type"
          class="avatar"
        />
        <div class="d-title">
          <div class="d-name">{{ displayNameOf(contact) }}</div>
          <!-- 脱敏契约：不再展示「微信号」，改匿名标识 / 资料未同步提示 -->
          <div v-if="nameResolved(contact)" class="d-sub num">匿名标识：{{ contact.alias }}</div>
          <div v-else class="d-sub">资料未同步 · 以匿名编码代称</div>
        </div>
        <span class="type-chip">{{ typeName }}</span>
      </div>

      <div class="d-sec">账号信息</div>
      <div class="kv">
        <div class="kv-row"><span class="k">类型</span><span>{{ typeName }}</span></div>
        <div class="kv-row"><span class="k">最近活跃</span><span class="num">{{ fmtTime(contact.last_msg_at) || '—' }}</span></div>
      </div>

      <!-- 统一备注编辑器：与聊天侧栏同一组件，用户级配置全场景一致 -->
      <RemarkEditor
        :fetch="fetchRemarkConfig"
        :save="saveRemarkConfig"
        :target-key="contact.id"
        :scope-note="typeName === '群聊' ? '作用域：仅当前群' : '作用域：全局生效（私聊 + 所有群聊）'"
      />

      <div class="d-actions">
        <el-button type="primary" size="small" :loading="opening" @click="enterChat">发消息</el-button>
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
.contact-detail { height: 100%; overflow-y: auto; user-select: none; }
.contact-detail input { user-select: text; }

.d-head {
  display: flex; align-items: center; gap: 14px;
  padding: 18px 20px;
  user-select: none;
  border-bottom: 1px solid var(--c-border);
  background: linear-gradient(180deg, #fafbfd, #fff);
}
.avatar {
  width: 52px; height: 52px; flex-shrink: 0;
  border-radius: var(--r-md);
  background: var(--c-primary);
  color: #fff; font-size: 20px; font-weight: 600;
  display: flex; align-items: center; justify-content: center;
  user-select: none;
}
.avatar.group { background: var(--c-ok); }
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
