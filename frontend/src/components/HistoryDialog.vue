<script setup>
/**
 * HistoryDialog —— 历史消息搜索弹窗
 * 筛选维度：关键词 + 日期范围 + 消息类型 + 方向 + 发送人
 * 交互：点结果 → locate 事件 → ChatPanel 打开会话 + 滚动定位 + 脉冲高亮
 */
import { computed, ref, watch } from 'vue'
import { useZIndex } from 'element-plus'
import { searchMessages, fetchMessageDateMeta } from '../api'
import CustomDatePicker from './CustomDatePicker.vue'

// Element Plus z-index 体系：defaultInitialZIndex=2000，nextZIndex() 每次 +1
// HistoryDialog 打开时先占一个 z-index，后续 EP popper（日期选择器）自然比它高
const { nextZIndex } = useZIndex()
const maskZ = ref(nextZIndex())
const dialogZ = computed(() => maskZ.value + 1)

const props = defineProps({
  visible: { type: Boolean, default: false },
  convId: { type: [String, Number], default: '' },  // 限定某会话；空=跨会话
  initialQuery: { type: String, default: '' },  // 外部搜索框传入的初始关键词
})

const emit = defineEmits(['update:visible', 'locate'])

// ------- 状态 -------
const keyword = ref('')
const dateSelected = ref(null)   // 'YYYY-MM-DD' | null
const msgType = ref('')           // 空=全部  text/image/video/file/voice/emoji/forward
const direction = ref('')         // 空=全部  customer/staff
const senderName = ref('')        // 发送人名称模糊匹配
const loading = ref(false)
const items = ref([])             // [{ id, convId, convName, content, senderName, direction, type, createdAt }]
const errorMsg = ref('')
const page = ref(1)
const pageSize = 50
const hasMore = ref(false)
const selectedId = ref('')        // 当前高亮消息 id

// 日历元数据：供 CustomDatePicker 渲染
const dateMetaYears = ref([])
const dateMetaMonths = ref({})
const dateMetaDateSet = ref(new Set())

// ------- 常量 -------
const TYPE_OPTIONS = [
  { label: '全部类型', value: '' },
  { label: '文本', value: 'text' },
  { label: '图片', value: 'image' },
  { label: '视频', value: 'video' },
  { label: '文件', value: 'file' },
  { label: '语音', value: 'voice' },
  { label: '表情', value: 'emoji' },
  { label: '合并转发', value: 'forward' },
]
const DIR_OPTIONS = [
  { label: '全部方向', value: '' },
  { label: '客户发送', value: 'customer' },
  { label: '客服发送', value: 'staff' },
]

/** 后端 msg_type 数字 → 前端 type 字符串（_msg_json 里的 msg_type） */
const MSG_TYPE_MAP = {
  1: 'text', 2: 'image', 3: 'file', 4: 'video',
  5: 'link', 6: 'voice', 7: 'emoji', 9: 'forward',
}
/** 前端 type 字符串 → 后端 msg_type 数字（构建搜索参数时反查） */
const TYPE_TO_MSG_TYPE = Object.fromEntries(
  Object.entries(MSG_TYPE_MAP).map(([k, v]) => [v, Number(k)])
)

// ------- 生命周期 -------
watch(() => props.visible, (v) => {
  if (v) {
    keyword.value = props.initialQuery || ''
    dateSelected.value = null
    msgType.value = ''
    direction.value = ''
    senderName.value = ''
    page.value = 1
    items.value = []
    hasMore.value = false
    errorMsg.value = ''
    selectedId.value = ''
    loadDateMeta()
    doSearch()
  }
})

watch(() => props.initialQuery, (v) => {
  if (props.visible && v) keyword.value = v
})

// ------- 工具 -------

/** 时间格式化：后端 create_time "YYYY-MM-DD HH:MM:SS" → HH:mm */
function fmtHHmm(timeStr) {
  if (!timeStr) return ''
  const match = String(timeStr).match(/(\d{2}):(\d{2})/)
  return match ? `${match[1]}:${match[2]}` : ''
}

/** 字段映射：后端 snake_case → 前端 camelCase
 *  复刻 MessageRow 聊天窗口 picOf / nameOf / avatarOf 同款决策链，
 *  避免两处对"谁用什么头像/名称"各自演化漂移。 */
function mapItem(raw) {
  const conv = raw.conversation || {}
  return {
    id: raw.id,
    convId: conv.id,
    convName: conv.name,
    convAvatar: conv.avatar,          // 单聊 fallback：Conversation 表存的对方头像
    convChatType: conv.chat_type,     // 1=单聊 2=群聊
    content: raw.content,
    senderName: raw.sender_name || '未知',
    senderAvatar: raw.sender_avatar || null,
    senderAnon: !!raw.sender_anon,
    operatorName: raw.operator_name || '',  // staff 发的消息：操作人姓名
    type: MSG_TYPE_MAP[raw.msg_type] || 'text',
    // direction 后端 1=客户入 2=客服出
    direction: raw.direction === 2 ? 'staff' : 'customer',
    createdAt: raw.create_time,
  }
}

/** 头像选择：复刻 MessageRow.picOf 逻辑
 *  - staff 发的：null（用颜色块首字）
 *  - customer 群聊：sender_avatar（后端 sender_view 从 GroupMember 下发）
 *  - customer 单聊：conv.avatar（Conversation 表存的对方头像） */
function resolveAvatar(it) {
  if (it.direction === 'staff') return null
  if (it.convChatType === 2) return it.senderAvatar || null
  return it.convAvatar || null
}

/** 头像块的首字母兜底：MessageRow.avatarOf 同款 */
function avatarInitial(it) {
  if (it.direction === 'staff') return (it.operatorName || '客').slice(0, 1)
  if (it.convChatType === 2) return (it.senderName || '客').slice(0, 1)
  return (it.convName || it.senderName || '?').slice(0, 1)
}

/** 名称选择：复刻 MessageRow.nameOf 入方向分支
 *  核心区别：staff 发的消息 sender_name 存的是客户身份（消息归属客户），
 *  要用 operator_name 展示 staff 自己的名字。 */
function resolveName(it) {
  if (it.direction === 'staff') {
    if (it.operatorName === '自动报价') return '系统代发'
    if (it.operatorName) return it.operatorName
    return '手机端'
  }
  if (it.convChatType === 2) return it.senderName || '成员'
  return it.convName || it.senderName || '未知'
}

/** 头像图片 404 兜底：hide img，靠下方 v-else 显示首字块 */
function onAvatarError(e) {
  e.target.style.display = 'none'
}

function highlight(text, kw) {
  if (!kw || !text) return text || ''
  const escaped = kw.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const re = new RegExp(`(${escaped})`, 'gi')
  return text.replace(re, '<mark>$1</mark>')
}
function fallbackHtml(type) {
  return `<em>（${type || 'text'}消息）</em>`
}
function close() { emit('update:visible', false) }
function resetFilters() {
  keyword.value = props.initialQuery || ''
  dateSelected.value = null
  msgType.value = ''
  direction.value = ''
  senderName.value = ''
  page.value = 1
  items.value = []
  doSearch()
}

async function loadDateMeta() {
  try {
    const data = await fetchMessageDateMeta(props.convId)
    dateMetaYears.value = data.years || []
    dateMetaMonths.value = data.monthsByYear || {}
    dateMetaDateSet.value = new Set(data.dates || [])
  } catch (e) {
    dateMetaYears.value = []
    dateMetaMonths.value = {}
    dateMetaDateSet.value = new Set()
  }
}

// ------- 搜索 -------
async function doSearch() {
  if (loading.value) return
  loading.value = true
  errorMsg.value = ''
  try {
    const params = buildParams()
    const data = await searchMessages(params)
    // 应用字段映射：后端 snake_case → 前端 camelCase
    items.value = (data.items || []).map(mapItem)
    hasMore.value = !!data.hasMore
  } catch (e) {
    errorMsg.value = e?.response?.data?.error || e.message || '搜索失败'
    items.value = []
    hasMore.value = false
  } finally {
    loading.value = false
  }
}

function buildParams() {
  // 后端参数名：q, conv_id, msg_type, direction(1入2出), sender, date_from, date_to, page_size
  const p = { page_size: pageSize }
  if (props.convId) p.conv_id = props.convId
  if (keyword.value.trim()) p.q = keyword.value.trim()
  if (dateSelected.value) {
    p.date_from = dateSelected.value
    p.date_to = dateSelected.value
  }
  // 前端 msgType 空值='全部类型'，后端 msg_type 为空=不过滤
  if (msgType.value) p.msg_type = TYPE_TO_MSG_TYPE[msgType.value]
  // 前端 direction 空值='全部方向'，后端 direction 1=客户 2=客服
  if (direction.value) p.direction = direction.value === 'customer' ? 1 : 2
  if (senderName.value.trim()) p.sender = senderName.value.trim()
  return p
}

function onKeySearch(e) {
  if (e.key === 'Enter') { page.value = 1; doSearch() }
}

function loadMore() {
  if (loading.value || !hasMore.value) return
  page.value++
  doSearch()
}

// ------- 结果项交互 -------
async function onItemClick(item) {
  selectedId.value = item.id
  emit('locate', item)
}
</script>

<template>
  <Teleport to="body">
    <transition name="hd-fade">
      <div v-if="visible" class="hd-mask" :style="{ zIndex: maskZ }" @click.self="close"></div>
    </transition>
    <transition name="hd-pop">
      <div v-if="visible" class="hd-dialog" :style="{ zIndex: dialogZ }" role="dialog" aria-modal="true">
        <!-- 标题栏 -->
        <div class="hd-head">
          <div class="hd-title">
            <span class="hd-title-ic">🕑</span>
            <span class="hd-title-text">历史消息</span>
            <span v-if="convId" class="hd-title-scope">· 当前会话</span>
            <span v-else class="hd-title-scope">· 全部会话</span>
          </div>
          <button class="hd-close" @click="close" title="关闭">✕</button>
        </div>

        <!-- 筛选区 -->
        <div class="hd-filters">
          <!-- 关键词 -->
          <div class="hd-row">
            <input
              v-model="keyword"
              class="hd-input"
              placeholder="输入关键词，回车搜索"
              @keyup="onKeySearch"
            />
            <button class="hd-btn hd-btn-primary" :disabled="loading" @click="page=1;doSearch()">搜索</button>
            <button class="hd-btn hd-btn-ghost" @click="resetFilters">重置</button>
          </div>
          <div class="hd-row">
            <div class="hd-field">
              <CustomDatePicker
                v-model="dateSelected"
                :years="dateMetaYears"
                :months-by-year="dateMetaMonths"
                :date-set="dateMetaDateSet"
                @change="page=1;doSearch()"
              />
            </div>
            <div class="hd-field">
              <select v-model="msgType" class="hd-select">
                <option v-for="o in TYPE_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</option>
              </select>
            </div>
            <div class="hd-field">
              <select v-model="direction" class="hd-select">
                <option v-for="o in DIR_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</option>
              </select>
            </div>
            <div class="hd-field hd-field-grow">
              <input
                v-model="senderName"
                class="hd-input hd-input-sm"
                placeholder="发送人"
                @keyup="onKeySearch"
              />
            </div>
          </div>
        </div>

        <!-- 结果区 -->
        <div class="hd-results">
          <div class="hd-result-head">
            <span class="hd-result-count">
              <template v-if="loading">搜索中…</template>
              <template v-else-if="items.length">找到 {{ items.length }} 条 {{ hasMore ? '+ 更多' : '' }}</template>
              <template v-else>共 {{ items.length }} 条</template>
            </span>
          </div>
          <el-scrollbar class="hd-scroll">
            <!-- 骨架 -->
            <div v-if="loading && !items.length" class="hd-skeleton">
              <div v-for="i in 5" :key="i" class="hd-skel-row">
                <div class="hd-skel-avatar"></div>
                <div class="hd-skel-body">
                  <div class="hd-skel-line hd-skel-line-sm"></div>
                  <div class="hd-skel-line"></div>
                  <div class="hd-skel-line hd-skel-line-short"></div>
                </div>
              </div>
            </div>

            <!-- 错误 -->
            <div v-else-if="errorMsg" class="hd-error">⚠ {{ errorMsg }}</div>

            <!-- 空态 -->
            <div v-else-if="!items.length" class="hd-empty-wrap">
              <el-empty description="没有找到匹配的历史消息" />
            </div>

            <!-- 结果列表 -->
            <div v-else class="hd-list">
              <div
                v-for="it in items"
                :key="it.id"
                class="hd-item"
                :class="{ 'hd-item-selected': selectedId === it.id }"
                @click="onItemClick(it)"
              >
                <!-- 头像：复刻 MessageRow.picOf 逻辑选头像源 -->
                <div class="hd-item-avatar" :class="it.direction === 'staff' ? 'hd-item-avatar-me' : ''">
                  <img
                    v-if="resolveAvatar(it)"
                    :src="resolveAvatar(it)"
                    :alt="resolveName(it)"
                    class="hd-item-avatar-img"
                    referrerpolicy="no-referrer"
                    @error="onAvatarError"
                  />
                  <template v-else>{{ avatarInitial(it).toUpperCase() }}</template>
                </div>
                <div class="hd-item-body">
                  <div class="hd-item-meta">
                    <!-- 发送者名称：复刻 MessageRow.nameOf 逻辑 -->
                    <span class="hd-item-name">{{ resolveName(it) }}</span>
                    <!-- 跨会话搜索时显示所属会话（单聊已用 convName 做名称则跳过） -->
                    <span
                      v-if="!convId && it.convChatType === 2 && it.convName"
                      class="hd-item-conv"
                    >· {{ it.convName }}</span>
                    <!-- 消息类型标签 -->
                    <span class="hd-item-type hd-item-type-{{ it.type }}">{{ it.type || 'text' }}</span>
                    <!-- 消息时间 HH:mm 格式 -->
                    <span class="hd-item-time">{{ fmtHHmm(it.createdAt) }}</span>
                  </div>
                  <div class="hd-item-content" v-html="highlight(it.content, keyword) || fallbackHtml(it.type)"></div>
                </div>
              </div>
              <div v-if="hasMore" class="hd-load-more">
                <button class="hd-btn hd-btn-ghost hd-btn-sm" :disabled="loading" @click="loadMore">加载更多</button>
              </div>
            </div>
          </el-scrollbar>
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<style scoped>
/* ====== 1. 弹窗容器 ====== */
.hd-mask {
  position: fixed; inset: 0;
  background: rgba(10, 20, 45, 0.45);
  backdrop-filter: blur(2px);
}
.hd-dialog {
  position: fixed;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  width: 720px;
  height: 580px;
  max-width: calc(100vw - 48px);
  max-height: calc(100vh - 48px);
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 16px 50px rgba(15, 30, 68, 0.25);
  border: 1px solid #e8edf5;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ====== 2. 标题栏 ====== */
.hd-head {
  flex-shrink: 0;
  padding: 14px 18px;
  border-bottom: 1px solid #eef1f7;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: linear-gradient(180deg, #fafbfd 0%, #fff 100%);
}
.hd-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 15px;
  font-weight: 600;
  color: #17233a;
}
.hd-title-ic { font-size: 18px; }
.hd-title-scope {
  color: #8a96ab;
  font-weight: 400;
  font-size: 12px;
}
.hd-close {
  width: 28px; height: 28px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: #8a96ab;
  font-size: 14px;
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.15s;
}
.hd-close:hover { background: #f2f5fb; color: #1d5de4; }

/* ====== 3. 筛选区 ====== */
.hd-filters {
  flex-shrink: 0;
  padding: 14px 18px;
  background: #fafbfd;
  border-bottom: 1px solid #eef1f7;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.hd-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.hd-field { display: flex; align-items: center; }
.hd-field-grow { flex: 1; min-width: 140px; }

/* 输入框 */
.hd-input {
  height: 30px;
  border: 1px solid #dbe3ef;
  border-radius: 6px;
  padding: 0 10px;
  font-size: 12px;
  color: #17233a;
  background: #fff;
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
  min-width: 160px;
  box-sizing: border-box;
}
.hd-input:focus {
  border-color: #1d5de4;
  box-shadow: 0 0 0 2px rgba(29, 93, 228, 0.15);
}
.hd-input-sm { height: 28px; font-size: 11px; min-width: 120px; }

/* 选择框 */
.hd-select {
  height: 30px;
  border: 1px solid #dbe3ef;
  border-radius: 6px;
  padding: 0 24px 0 10px;
  font-size: 12px;
  color: #17233a;
  background: #fff url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath d='M1 1l4 4 4-4' fill='none' stroke='%238a96ab' stroke-width='1.5'/%3E%3C/svg%3E") no-repeat right 8px center;
  outline: none;
  appearance: none;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.hd-select:focus {
  border-color: #1d5de4;
  box-shadow: 0 0 0 2px rgba(29, 93, 228, 0.15);
}

/* 按钮 */
.hd-btn {
  height: 30px;
  border-radius: 6px;
  font-size: 12px;
  padding: 0 14px;
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}
.hd-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.hd-btn-sm { height: 26px; padding: 0 10px; font-size: 11px; }
.hd-btn-primary {
  background: #1d5de4;
  border-color: #1d5de4;
  color: #fff;
}
.hd-btn-primary:hover:not(:disabled) { background: #0f3da8; border-color: #0f3da8; }
.hd-btn-ghost {
  background: #fff;
  border-color: #dbe3ef;
  color: #17233a;
}
.hd-btn-ghost:hover:not(:disabled) { border-color: #1d5de4; color: #1d5de4; }

/* ====== 4. 结果区 ====== */
.hd-results {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.hd-result-head {
  flex-shrink: 0;
  padding: 10px 18px;
  border-bottom: 1px solid #eef1f7;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11px;
  color: #8a96ab;
}
.hd-scroll { flex: 1; min-height: 0; }
.hd-scroll :deep(.el-scrollbar__wrap) { overflow-x: hidden; }

/* 骨架屏 */
.hd-skeleton { padding: 10px 18px; }
.hd-skel-row {
  display: flex;
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid #f3f5fa;
}
.hd-skel-avatar {
  width: 34px; height: 34px; border-radius: 50%;
  background: linear-gradient(90deg, #eef1f7 25%, #f5f7fb 50%, #eef1f7 75%);
  background-size: 200% 100%;
  animation: hd-skel-shine 1.2s infinite;
  flex-shrink: 0;
}
.hd-skel-body { flex: 1; display: flex; flex-direction: column; gap: 6px; }
.hd-skel-line {
  height: 12px; border-radius: 4px;
  background: linear-gradient(90deg, #eef1f7 25%, #f5f7fb 50%, #eef1f7 75%);
  background-size: 200% 100%;
  animation: hd-skel-shine 1.2s infinite;
}
.hd-skel-line-sm { width: 35%; height: 11px; }
.hd-skel-line-short { width: 60%; }
@keyframes hd-skel-shine {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* 空态 / 错误 */
.hd-empty-wrap { padding: 40px; height: 100%; box-sizing: border-box; display: flex; align-items: center; justify-content: center; }
.hd-error { padding: 30px; text-align: center; color: #d94452; font-size: 13px; }

/* 结果列表 */
.hd-list { padding: 6px 0; }
.hd-item {
  display: flex;
  gap: 10px;
  padding: 12px 18px;
  cursor: pointer;
  border-bottom: 1px solid #f3f5fa;
  transition: background 0.12s;
}
.hd-item:hover { background: #f6f8fd; }
.hd-item-selected { background: #eef4ff !important; }

/* 头像 */
.hd-item-avatar {
  width: 34px; height: 34px;
  border-radius: 50%;
  background: linear-gradient(135deg, #4a84ee 0%, #1d5de4 100%);
  color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; font-weight: 600;
  flex-shrink: 0;
  overflow: hidden;
  position: relative;
}
.hd-item-avatar-me { background: linear-gradient(135deg, #34c759 0%, #1f9f4f 100%); }
.hd-item-avatar-img {
  width: 100%; height: 100%;
  object-fit: cover;
  border-radius: 50%;
  display: block;
}

/* body */
.hd-item-body { flex: 1; min-width: 0; }
.hd-item-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
  font-size: 11px;
  color: #8a96ab;
}
.hd-item-name { color: #17233a; font-weight: 600; font-size: 12px; }
.hd-item-conv { color: #6b7a93; }
.hd-item-type {
  padding: 1px 6px;
  border-radius: 3px;
  background: #f0f3f9;
  color: #6b7a93;
  font-size: 10px;
  text-transform: uppercase;
}
.hd-item-type-text { background: #e9f0ff; color: #1d5de4; }
.hd-item-type-image { background: #fef3e2; color: #c97a1f; }
.hd-item-type-video { background: #fde3e3; color: #c43c3c; }
.hd-item-type-file { background: #eef1f7; color: #6b7a93; }
.hd-item-type-voice { background: #e6f7ef; color: #2a9d6c; }
.hd-item-type-emoji { background: #fef3e2; color: #c97a1f; }
.hd-item-type-forward { background: #f3eefc; color: #7b4dc9; }
.hd-item-time { margin-left: auto; font-size: 11px; }
.hd-item-content {
  font-size: 12px;
  color: #17233a;
  line-height: 1.5;
  word-break: break-word;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.hd-item-content :deep(mark) {
  background: #fff3a1;
  color: #17233a;
  padding: 0 1px;
  border-radius: 2px;
}

/* 加载更多 */
.hd-load-more {
  display: flex;
  justify-content: center;
  padding: 10px 0 14px;
}

/* ====== 5. 过渡动画 ====== */
.hd-fade-enter-active, .hd-fade-leave-active { transition: opacity 0.2s ease; }
.hd-fade-enter-from, .hd-fade-leave-to { opacity: 0; }

.hd-pop-enter-active { transition: all 0.22s ease; }
.hd-pop-leave-active { transition: all 0.16s ease; }
.hd-pop-enter-from, .hd-pop-leave-to {
  opacity: 0;
  transform: translate(-50%, -52%) scale(0.96);
}
</style>
