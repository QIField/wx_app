<script setup>
/**
 * HistoryDialog —— 历史消息搜索弹窗
 * 筛选维度：关键词 + 日期范围 + 消息类型 + 方向 + 发送人
 * 交互：点结果 → locate 事件 → ChatPanel 打开会话 + 滚动定位 + 脉冲高亮
 */
import { computed, nextTick, ref, watch } from 'vue'
import { searchMessages } from '../api'
import { msgTextOf } from '../utils/message'

const props = defineProps({
  visible: { type: Boolean, default: false },
  convId: { type: [String, Number], default: '' },  // 限定某会话；空=跨会话
  initialQuery: { type: String, default: '' },  // 外部搜索框传入的初始关键词
})

const emit = defineEmits(['update:visible', 'locate'])

// ------- 状态 -------
const keyword = ref('')
const dateRange = ref(null)       // [YYYY-MM-DD, YYYY-MM-DD] 或 null
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

// ------- 生命周期 -------
watch(() => props.visible, (v) => {
  if (v) {
    keyword.value = props.initialQuery || ''
    dateRange.value = null
    msgType.value = ''
    direction.value = ''
    senderName.value = ''
    page.value = 1
    items.value = []
    hasMore.value = false
    errorMsg.value = ''
    selectedId.value = ''
    doSearch()
  }
})

watch(() => props.initialQuery, (v) => {
  if (props.visible && v) keyword.value = v
})

// ------- 工具 -------
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
  dateRange.value = null
  msgType.value = ''
  direction.value = ''
  senderName.value = ''
  page.value = 1
  items.value = []
  doSearch()
}

// ------- 搜索 -------
async function doSearch() {
  if (loading.value) return
  loading.value = true
  errorMsg.value = ''
  try {
    const params = buildParams()
    const data = await searchMessages(params)
    items.value = data.items || []
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
  const p = { page: page.value, pageSize }
  if (props.convId) p.convId = props.convId
  if (keyword.value.trim()) p.keyword = keyword.value.trim()
  if (dateRange.value?.length === 2) {
    p.date_from = dateRange.value[0]
    p.date_to = dateRange.value[1]
  }
  if (msgType.value) p.type = msgType.value
  if (direction.value) p.direction = direction.value
  if (senderName.value.trim()) p.senderName = senderName.value.trim()
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
      <div v-if="visible" class="hd-mask" @click.self="close"></div>
    </transition>
    <transition name="hd-pop">
      <div v-if="visible" class="hd-dialog" role="dialog" aria-modal="true">
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
              <ElDatePicker
                v-model="dateRange"
                type="daterange"
                range-separator="至"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                value-format="YYYY-MM-DD"
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
                <div class="hd-item-avatar" :class="it.direction === 'staff' ? 'hd-item-avatar-me' : ''">
                  {{ (it.senderName || '?').charAt(0).toUpperCase() }}
                </div>
                <div class="hd-item-body">
                  <div class="hd-item-meta">
                    <span class="hd-item-name">{{ it.senderName || '未知' }}</span>
                    <span v-if="!convId" class="hd-item-conv">· {{ it.convName || '未知会话' }}</span>
                    <span class="hd-item-type hd-item-type-{{ it.type }}">{{ it.type || 'text' }}</span>
                    <span class="hd-item-time">{{ it.createdAt }}</span>
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
  z-index: 9999;
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
  z-index: 10000;
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
}
.hd-item-avatar-me { background: linear-gradient(135deg, #34c759 0%, #1f9f4f 100%); }

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
