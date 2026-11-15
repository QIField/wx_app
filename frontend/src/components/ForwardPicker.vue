<script setup>
/** 转发目标选择器：最近转发置顶 + 当前账号全部会话 + 三路搜索（昵称/全拼/首字母）。
 *
 * 拼音数据复用通讯录接口（contact 行自带 pinyin_toks/initials，且有 conversation_id
 * 可映射回会话）；未同步资料的会话退化为纯名称子串匹配。
 * 确认后只上抛目标 id 列表，「逐条还是合并」由外层二次确认弹窗决定（见 ChatPanel）。
 */
import { computed, h, markRaw, onMounted, ref } from 'vue'
import { fetchForwardRecent } from '../api'
import { useChatStore } from '../stores/chat'
import { useContactsStore } from '../stores/contacts'
import { displayNameOf, matchName } from '../utils/format'

const emit = defineEmits(['confirm', 'close'])

const chat = useChatStore()
const contacts = useContactsStore()

/* el-input prefix-icon 需要组件引用：内联 SVG 轻量实现，markRaw 免响应式代理 */
const SearchIcon = markRaw({
  render: () => h('svg', { viewBox: '0 0 24 24', width: '1em', height: '1em', fill: 'none', stroke: 'currentColor', 'stroke-width': 2 }, [
    h('circle', { cx: 11, cy: 11, r: 7 }),
    h('path', { d: 'm20 20-3.5-3.5' }),
  ]),
})

const keyword = ref('')
const picked = ref(new Set()) // 已选目标会话 id
const recentIds = ref([])    // 最近转发：会话 id 有序列表（仅排序用）

/* conversation_id → 拼音索引（联系人行带入），拼不上的会话只做名称匹配 */
const pinyinByConv = ref({})

onMounted(async () => {
  // 最近转发（当前操作人维度，后端算好）；失败不打断主流程
  try {
    const data = await fetchForwardRecent()
    recentIds.value = (data.items || []).map((i) => i.conversation_id)
  } catch { /* 空置顶区即可 */ }

  // 拉通讯录建拼音映射（已缓存也重拉一次：转发器打开频率低，换号后必须新鲜）
  try {
    await contacts.load()
    const map = {}
    for (const c of [...contacts.friends, ...contacts.groups]) {
      if (c.conversation_id) map[c.conversation_id] = c
    }
    pinyinByConv.value = map
  } catch { /* 拼音映射缺席时退化为名称搜索 */ }
})

/** 搜索命中：昵称/匿名编码子串 + 首字母子串 + 逐字拼音边界对齐（复用 matchName）。 */
function hitConv(c, kw) {
  const contact = pinyinByConv.value[c.id]
  return matchName(
    [displayNameOf(c), contact?.initials],
    contact?.pinyin_toks,
    kw,
  )
}

/* 列表排序：命中搜索时按名称；否则最近转发置顶，其余按会话列表原顺序 */
const list = computed(() => {
  const kw = keyword.value.trim()
  const base = kw ? chat.conversations.filter((c) => hitConv(c, kw)) : chat.conversations
  if (kw || !recentIds.value.length) return base
  const rank = new Map(recentIds.value.map((id, i) => [id, i]))
  return [...base].sort((a, b) =>
    (rank.has(a.id) ? rank.get(a.id) : 99) - (rank.has(b.id) ? rank.get(b.id) : 99))
})

const isRecent = (id) => !keyword.value.trim() && recentIds.value.includes(id)

function toggle(id) {
  const next = new Set(picked.value)
  next.has(id) ? next.delete(id) : next.add(id)
  picked.value = next
}

function confirm() {
  if (!picked.value.size) return
  emit('confirm', [...picked.value])
}

function close() {
  emit('close')
}

/* 头像首字：群取前两字，单聊取一字（与左栏会话列表同款观感） */
function headOf(c) {
  const name = displayNameOf(c)
  return c.chat_type === 2 ? name.slice(0, 2) : name.slice(0, 1)
}
</script>

<template>
  <el-dialog
    :model-value="true"
    title="转发给"
    width="440px"
    :append-to-body="true"
    class="fwd-picker"
    @close="close"
  >
    <el-input
      v-model="keyword"
      placeholder="搜索：昵称 / 全拼 / 首字母"
      clearable
      :prefix-icon="SearchIcon"
    />

    <div v-if="!keyword.trim() && recentIds.length" class="sec-label">最近转发</div>
    <div class="conv-scroll">
      <button
        v-for="c in list"
        :key="c.id"
        class="row"
        :class="{ on: picked.has(c.id) }"
        @click="toggle(c.id)"
      >
        <span class="ava" :class="{ group: c.chat_type === 2 }">{{ headOf(c) }}</span>
        <span class="main">
          <span class="name">{{ displayNameOf(c) }}</span>
          <span v-if="isRecent(c.id)" class="recent-tag">最近转发</span>
        </span>
        <span class="pick-dot" :class="{ on: picked.has(c.id) }">
          <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="#fff" stroke-width="3.4"><path d="M20 6 9 17l-5-5"/></svg>
        </span>
      </button>
      <div v-if="!list.length" class="empty">没有匹配的会话</div>
    </div>

    <template #footer>
      <span class="count">已选 {{ picked.size }} 个会话</span>
      <el-button @click="close">取消</el-button>
      <el-button type="primary" :disabled="!picked.size" @click="confirm">确定</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.sec-label { margin: 10px 2px 4px; font-size: 11px; color: var(--c-text-sub); user-select: none; }
.conv-scroll { max-height: 320px; overflow: auto; margin-top: 6px; }
.row {
  display: flex; align-items: center; gap: 10px;
  width: 100%; padding: 7px 8px;
  border: none; border-radius: var(--r-sm);
  background: none; cursor: pointer; text-align: left;
  transition: background 0.12s;
}
.row:hover { background: var(--c-surface); }
.row.on { background: var(--c-primary-soft); }
.ava {
  width: 32px; height: 32px; flex-shrink: 0;
  border-radius: var(--r-sm);
  background: var(--c-ok); color: #fff;
  font-size: 13px; font-weight: 600;
  display: flex; align-items: center; justify-content: center;
  user-select: none;
}
.ava.group { background: var(--c-primary); }
.main { flex: 1; min-width: 0; display: flex; align-items: center; gap: 8px; }
.name { flex: 1; min-width: 0; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.recent-tag {
  flex-shrink: 0; font-size: 10px; color: var(--c-text-sub);
  border: 1px solid var(--c-border); border-radius: 3px; padding: 0 4px;
}
.pick-dot {
  width: 16px; height: 16px; flex-shrink: 0;
  border-radius: 50%; border: 1.5px solid var(--c-border-strong);
  display: flex; align-items: center; justify-content: center;
  transition: all 0.12s;
}
.pick-dot.on { background: var(--c-primary); border-color: var(--c-primary); }
.empty { text-align: center; color: var(--c-text-sub); font-size: 12px; padding: 26px 0; }
.count { float: left; line-height: 32px; font-size: 12px; color: var(--c-text-sub); }
</style>
