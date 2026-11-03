<script setup>
/** 通讯录面板：好友/群聊双 Tab + 实时搜索（本地过滤高亮）+ 字母分组列表。 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useContactsStore } from '../stores/contacts'
import { displayNameOf, fmtTime, highlight } from '../utils/format'
import ContactAvatar from './ContactAvatar.vue'
import UnreadBadge from './UnreadBadge.vue'

const contacts = useContactsStore()
const qInput = ref(null)

/** 第二行预览（脱敏契约替代 wxid）：已命名 → 匿名标识；未命名 → 资料未同步提示。 */
function previewOf(c) {
  return c.name ? `匿名标识 ${c.alias}` : '资料未同步'
}

onMounted(() => contacts.load())

/** 全局快捷键 "/" 聚焦搜索（仅本面板挂载期间生效）。 */
function onGlobalKey(e) {
  const tag = document.activeElement?.tagName
  if (e.key === '/' && tag !== 'INPUT' && tag !== 'TEXTAREA') {
    e.preventDefault()
    qInput.value?.focus()
  }
}
window.addEventListener('keydown', onGlobalKey)
onUnmounted(() => window.removeEventListener('keydown', onGlobalKey))

/** 好友按字母分组（后端已按 letter 排好，保持顺序）。 */
const letterGroups = computed(() => {
  const map = new Map()
  for (const c of contacts.filteredList) {
    if (!map.has(c.letter)) map.set(c.letter, [])
    map.get(c.letter).push(c)
  }
  return [...map.entries()]
})

/** 渲染行（统一好友/群聊两套模板）：好友为「字母头 + 条目」扁平序列，群聊为纯条目。 */
const rows = computed(() => {
  const sel = contacts.tab === 'friends' ? 'friend' : 'group'
  const out = []
  if (sel === 'friend') {
    for (const [letter, list] of letterGroups.value) {
      out.push({ key: `h-${letter}`, header: letter })
      list.forEach((c, i) =>
        out.push({ key: `f-${c.id}`, sel, contact: c, delay: Math.min(i * 25, 250) }))
    }
  } else {
    contacts.filteredList.forEach((c, i) =>
      out.push({ key: `g-${c.id}`, sel, contact: c, delay: Math.min(i * 25, 250) }))
  }
  return out
})

const crossHint = computed(() =>
  contacts.crossHintCount > 0 && contacts.filteredList.length === 0)

const emptyText = computed(() =>
  `没有找到与「${contacts.keyword.trim()}」相关的${contacts.tab === 'friends' ? '好友' : '群聊'}`)

function clearKeyword() {
  contacts.setKeyword('')
  qInput.value?.focus()
}

function jumpCross() {
  contacts.setTab(contacts.tab === 'friends' ? 'groups' : 'friends')
}

function isSelected(type, id) {
  return contacts.selected?.type === type && contacts.selected?.id === id
}
</script>

<template>
  <div class="contacts">
    <div class="head">
      <span class="title">通讯录</span>
    </div>

    <div class="tabs">
      <button :class="{ on: contacts.tab === 'friends' }" @click="contacts.setTab('friends')">
        好友 <em class="num">{{ contacts.friends.length }}</em>
      </button>
      <button :class="{ on: contacts.tab === 'groups' }" @click="contacts.setTab('groups')">
        群聊 <em class="num">{{ contacts.groups.length }}</em>
      </button>
    </div>

    <div class="search">
      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" />
      </svg>
      <input
        ref="qInput"
        :value="contacts.keyword"
        placeholder="搜索好友 / 群聊（按 / 聚焦）"
        @input="contacts.setKeyword($event.target.value)"
      >
      <button v-show="contacts.keyword" class="s-clear" title="清空" @click="clearKeyword">
        <svg viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round">
          <path d="M18 6 6 18" /><path d="m6 6 12 12" />
        </svg>
      </button>
    </div>

    <div v-if="crossHint" class="cross-hint" @click="jumpCross">
      <span>在{{ contacts.tab === 'friends' ? '群聊' : '好友' }}中找到
        <b class="num">{{ contacts.crossHintCount }}</b> 条结果，点击切换</span>
      <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
        <path d="m9 18 6-6-6-6" />
      </svg>
    </div>

    <el-scrollbar class="scroll">
      <!-- 加载骨架 -->
      <div v-if="contacts.loading">
        <div v-for="i in 6" :key="i" class="skel">
          <span class="b1"></span>
          <div class="col"><span class="b2"></span><span class="b3"></span></div>
        </div>
      </div>

      <!-- 空态 -->
      <el-empty v-else-if="!contacts.filteredList.length" :description="emptyText" :image-size="60" />

      <!-- 好友字母分组 / 群聊平铺：归一为扁平行序列，单循环渲染 -->
      <template v-else>
        <template v-for="row in rows" :key="row.key">
          <div v-if="row.header" class="letter-head num">{{ row.header }}</div>
          <div
            v-else
            class="item"
            :class="{ active: isSelected(row.sel, row.contact.id) }"
            :style="{ animationDelay: row.delay + 'ms' }"
            @click="contacts.select(row.sel, row.contact.id)"
          >
            <ContactAvatar
              :name="row.contact.name"
              :alias="row.contact.alias"
              :avatar="row.contact.avatar"
              :chat-type="row.contact.chat_type"
              class="avatar"
            />
            <div class="body">
              <div class="row1">
                <span class="name" v-html="highlight(displayNameOf(row.contact), contacts.keyword)"></span>
                <span class="flags">
                  <span v-if="row.contact.pinned" class="pin">置顶</span>
                  <span class="time num">{{ fmtTime(row.contact.last_msg_at) }}</span>
                </span>
              </div>
              <div class="row2">
                <span class="preview num" v-html="highlight(previewOf(row.contact), contacts.keyword)"></span>
                <UnreadBadge :count="row.contact.unread_count" />
              </div>
            </div>
          </div>
        </template>
      </template>
    </el-scrollbar>
  </div>
</template>

<style scoped>
.contacts { display: flex; flex-direction: column; height: 100%; }
.head {
  padding: 10px 12px 8px;
  user-select: none;
  border-bottom: 1px solid var(--c-border);
}
.title { font-weight: 600; font-size: 13px; }

.tabs {
  display: flex; gap: 4px; padding: 6px 10px 0;
  border-bottom: 1px solid var(--c-border);
}
.tabs button {
  flex: 1;
  padding: 6px 0;
  margin-bottom: -1px;
  font-size: 13px; color: var(--c-text-sub);
  background: none; border: none; cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: color 0.15s, border-color 0.15s;
}
.tabs button em { font-style: normal; font-size: 12px; opacity: 0.75; }
.tabs button:hover { color: var(--c-text); }
.tabs button.on {
  color: var(--c-primary); font-weight: 600;
  border-bottom-color: var(--c-primary);
}

.search {
  display: flex; align-items: center; gap: 7px;
  margin: 8px 10px;
  padding: 0 8px;
  height: 30px;
  color: var(--c-text-sub);
  background: #f4f6fa;
  border: 1px solid var(--c-border);
  border-radius: var(--r-sm);
  transition: border-color 0.15s, background 0.15s, box-shadow 0.15s;
}
.search:focus-within {
  background: #fff; border-color: var(--c-primary);
  box-shadow: 0 0 0 2px rgba(29, 93, 228, 0.12);
}
.search input {
  flex: 1; min-width: 0;
  border: none; outline: none; background: none;
  font-family: inherit; font-size: 12px; color: var(--c-text);
}
.search input::placeholder { color: var(--c-text-sub); opacity: 0.7; }
.s-clear {
  display: flex; align-items: center; justify-content: center;
  width: 16px; height: 16px; padding: 0;
  border: none; border-radius: 50%;
  background: var(--c-border-strong); color: #fff;
  cursor: pointer; transition: background 0.15s;
}
.s-clear:hover { background: var(--c-text-sub); }

.cross-hint {
  margin: 0 10px 6px;
  padding: 5px 8px;
  font-size: 11px; color: var(--c-primary-deep);
  background: var(--c-primary-soft);
  border-radius: var(--r-sm);
  cursor: pointer;
  display: flex; align-items: center; justify-content: space-between;
}
.cross-hint:hover { background: #dce8ff; }

.scroll { flex: 1; }

.letter-head {
  position: sticky; top: 0; z-index: 2;
  padding: 3px 12px;
  font-size: 11px; font-weight: 700;
  user-select: none;
  color: var(--c-primary-deep);
  background: #f4f6fa;
  border-top: 1px solid var(--c-border);
  border-bottom: 1px solid var(--c-border);
}
.letter-head:first-child { border-top: none; }

.item {
  display: flex; gap: 9px; align-items: center;
  padding: 7px 12px;
  cursor: pointer; user-select: none; position: relative;
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
.name :deep(mark), .preview :deep(mark) {
  background: rgba(29, 93, 228, 0.18);
  color: var(--c-primary-deep);
  padding: 0 1px; border-radius: 2px;
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

/* 骨架屏 */
.skel {
  display: flex; gap: 9px; align-items: center;
  padding: 9px 12px;
  border-bottom: 1px solid #f2f4f8;
}
.skel .b1 { width: 32px; height: 32px; border-radius: var(--r-sm); flex-shrink: 0; }
.skel .col { flex: 1; display: flex; flex-direction: column; gap: 6px; }
.skel .b2 { height: 11px; width: 55%; }
.skel .b3 { height: 10px; width: 80%; }
.skel .b1, .skel .b2, .skel .b3 {
  background: linear-gradient(90deg, #eef1f6 25%, #f8fafd 50%, #eef1f6 75%);
  background-size: 200% 100%;
  animation: shimmer 1.1s infinite;
}
@keyframes shimmer { from { background-position: 200% 0; } to { background-position: -200% 0; } }
</style>
