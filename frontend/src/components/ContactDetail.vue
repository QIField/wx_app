<script setup>
/** 联系人/群聊详情卡：账号信息 + 备注标签编辑（业务自建）+ 发消息入口。 */
import { computed, onUnmounted, ref, watch } from 'vue'
import { useContactsStore } from '../stores/contacts'
import { useChatStore } from '../stores/chat'
import { displayNameOf, fmtTime, nameResolved } from '../utils/format'
import AnonAvatar from './AnonAvatar.vue'

const emit = defineEmits(['enter-chat'])
const contacts = useContactsStore()
const chat = useChatStore()

const contact = computed(() => contacts.selectedContact)
const typeName = computed(() => (contact.value?.chat_type === 2 ? '群聊' : '好友'))
const hint = ref('')
let hintTimer = null
onUnmounted(() => clearTimeout(hintTimer))

/* ---------- 备注与标签编辑（业务自建，不写回微信） ---------- */
const editing = ref(false)
const saving = ref(false)
const draftRemark = ref('')
const draftTags = ref([])
const tagInput = ref('')
const editErr = ref('')

// 切换选中联系人：退出编辑态并拉取档案（按通讯录行 id，不传 wxid——脱敏契约）
watch(() => contact.value?.id, (id) => {
  editing.value = false
  editErr.value = ''
  if (id) contacts.loadProfile(id)
}, { immediate: true })

function startEdit() {
  draftRemark.value = contacts.profile?.remark || ''
  draftTags.value = [...(contacts.profile?.tags || [])]
  tagInput.value = ''
  editErr.value = ''
  editing.value = true
}

function addTag() {
  const t = tagInput.value.trim()
  if (!t) return
  if (t.length > 12) { editErr.value = '单个标签不能超过 12 字'; return }
  if (draftTags.value.length >= 10) { editErr.value = '标签最多 10 个'; return }
  if (!draftTags.value.includes(t)) draftTags.value.push(t)
  tagInput.value = ''
  editErr.value = ''
}

function removeTag(i) {
  draftTags.value.splice(i, 1)
  editErr.value = ''
}

async function saveEdit() {
  if (draftRemark.value.trim().length > 100) {
    editErr.value = '备注不能超过 100 字'
    return
  }
  saving.value = true
  try {
    await contacts.saveProfile(contact.value.id, {
      remark: draftRemark.value.trim(),
      tags: [...draftTags.value],
    })
    editing.value = false
  } catch (e) {
    editErr.value = e.message || '保存失败'
  } finally {
    saving.value = false
  }
}

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
        <img v-if="contact.avatar" class="avatar img" :src="contact.avatar" alt="" referrerpolicy="no-referrer">
        <AnonAvatar v-else-if="!nameResolved(contact)" :alias="contact.alias" class="avatar" />
        <span v-else class="avatar" :class="{ group: contact.chat_type === 2 }">{{ displayNameOf(contact).slice(0, 1) }}</span>
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

      <div class="d-sec sec-flex">
        <span>备注与标签</span>
        <button v-if="!editing" class="edit-link" @click="startEdit">编辑</button>
      </div>
      <div class="kv">
        <template v-if="!editing">
          <div class="kv-row"><span class="k">备注</span><span>{{ contacts.profile?.remark || '暂无备注' }}</span></div>
          <div class="kv-row">
            <span class="k">标签</span>
            <span class="tag-list">
              <span v-for="t in contacts.profile?.tags || []" :key="t" class="chip">{{ t }}</span>
              <span v-if="!(contacts.profile?.tags || []).length" class="none">暂无标签</span>
            </span>
          </div>
        </template>
        <template v-else>
          <div class="edit-row">
            <input v-model="draftRemark" class="text-input" placeholder="备注（≤100 字）" maxlength="100">
          </div>
          <div class="edit-row">
            <span class="tag-list">
              <span v-for="(t, i) in draftTags" :key="t" class="chip">
                {{ t }}<button class="chip-x" title="删除标签" @click="removeTag(i)">×</button>
              </span>
              <span v-if="!draftTags.length" class="none">暂无标签</span>
            </span>
          </div>
          <div class="edit-row">
            <input
              v-model="tagInput"
              class="text-input"
              placeholder="输入标签后回车添加（≤12 字）"
              @keydown.enter.prevent="addTag"
            >
            <span class="cnt num">{{ draftTags.length }}/10</span>
          </div>
          <div class="edit-actions">
            <el-button size="small" type="primary" :loading="saving" @click="saveEdit">保存</el-button>
            <el-button size="small" @click="editing = false">取消</el-button>
            <span v-if="editErr" class="hint">{{ editErr }}</span>
          </div>
        </template>
      </div>

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

/* 备注与标签 */
.sec-flex { display: flex; align-items: center; justify-content: space-between; }
.edit-link {
  border: none; background: none; cursor: pointer;
  font-size: 11.5px; color: var(--c-primary);
}
.edit-link:hover { color: var(--c-primary-deep); text-decoration: underline; }
.tag-list { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; min-width: 0; }
.chip {
  display: inline-flex; align-items: center; gap: 3px;
  font-size: 11px; line-height: 20px;
  padding: 0 8px; border-radius: 3px;
  background: var(--c-primary-soft); color: var(--c-primary-deep);
  border: 1px solid #b9d0ff;
}
.chip-x {
  border: none; background: none; cursor: pointer;
  font-size: 13px; line-height: 1; color: var(--c-primary-deep);
  padding: 0; opacity: 0.6;
}
.chip-x:hover { opacity: 1; color: var(--c-danger); }
.none { font-size: 12px; color: var(--c-text-sub); }
.edit-row { display: flex; align-items: center; gap: 8px; padding: 6px 0; }
.text-input {
  flex: 1; min-width: 0; height: 28px; padding: 0 8px;
  border: 1px solid var(--c-border); border-radius: var(--r-sm);
  font-family: inherit; font-size: 12.5px; color: var(--c-text);
  outline: none; background: #fff;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.text-input:focus { border-color: var(--c-primary); box-shadow: 0 0 0 2px rgba(29, 93, 228, 0.12); }
.cnt { font-size: 11px; color: var(--c-text-sub); flex-shrink: 0; }
.edit-actions { display: flex; align-items: center; gap: 8px; padding-top: 8px; }

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
