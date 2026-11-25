<script setup>
/** QuoteCard.vue —— 重构版 v2。
 *
 * 收起态：状态 pill + VIN 行 + OE 行 + 时间 + 箭头（单行 52px grid）。
 * 展开态：左 4px 竖指示条（蓝=正常 / 红=错误）+ 2 种模板。
 *
 * 模板 normal：车辆识别信息 + 配件报价清单（所有非 error 条目统一）
 * 模板 error ：浅红报错卡 + 原始 VIN 信息（price_json.error 存在）
 *
 * API 契约（不变）：
 *   props:   inquiry
 *   emits:   refresh / open-detail
 *   imports: ignoreQuoteInquiry
 */
import { computed, inject, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ignoreQuoteInquiry } from '../api'

const props = defineProps({ inquiry: { type: Object, required: true } })
const emit = defineEmits(['refresh', 'open-detail'])

/** 聊天面板 ref —— 用于定位聊天气泡 */
const chatPanelRef = inject('chatPanelRef', null)

const expanded = ref(false)

/* ============= 分类 ============= */
const p = computed(() => props.inquiry || {})
const pj = computed(() => p.value.price_json || {})
const car = computed(() => pj.value.car || null)
const pricing = computed(() => pj.value.pricing || { items: [] })

/** 两种模板：error（服务异常）/ normal（其余全走同一套）。 */
const tpl = computed(() => pj.value.error ? 'error' : 'normal')

const isError = computed(() => tpl.value === 'error')

/* ============= 状态 pill ============= */
const STATUS_MAP = {
  0: { label: '待处理', cls: 'amber' },
  1: { label: '待处理', cls: 'amber' },
  3: { label: '已报价', cls: 'green' },
  2: { label: '错误',   cls: 'red' },
  4: { label: '错误',   cls: 'red' },
}
const statusChip = computed(() => {
  const s = p.value.status
  if (p.value.status_label) return { label: p.value.status_label, cls: STATUS_MAP[s]?.cls || 'amber' }
  return STATUS_MAP[s] || { label: '待处理', cls: 'amber' }
})

/* ============= 收起行数据 ============= */
const inquiryVIN = computed(() => (p.value.vin || '').trim())
const carVIN = computed(() => (car.value?.vin || '').trim() || inquiryVIN.value)
const carModelStr = computed(() => {
  if (!car.value) return ''
  return car.value.saleModelName
    || [car.value.brandName, car.value.model].filter(Boolean).join(' ')
})
/** 判断字符串是否是微信号（纯英文数字，无中文） */
const WXID_RE = /^[a-zA-Z0-9_-]+$/
function isWechatId(s) { return s && WXID_RE.test(s) && /[a-zA-Z]/.test(s) }

/** 主行：私聊显示客户名 / 群聊显示群名 + 客户名（过滤微信号） */
const primaryLabel = computed(() => {
  const convName = p.value.conversation_name || ''
  const sender = p.value.sender_name || ''
  // 过滤：纯英文数字串当作微信号，不展示
  const cleanConv = isWechatId(convName) ? '' : convName
  const cleanSender = isWechatId(sender) ? '' : sender
  const isGroup = p.value.chat_type === 2 || (p.value.chat_type === 1 && cleanConv && cleanConv !== cleanSender)
  if (isGroup && cleanConv && cleanSender) return `${cleanConv} · ${cleanSender}`
  return cleanSender || cleanConv || sender || convName || '未识别'
})
/** 次行：配件名称（多 OE 则用 / 分割，否则 part_name 或 inquiry_content 截断） */
const oeList = computed(() => {
  const items = pricing.value.items || []
  const list = items.map(it => it.oe).filter(Boolean)
  if (list.length) return list
  if (p.value.oem_no) return [p.value.oem_no]
  return []
})
const partNames = computed(() => {
  // 从 items 里取 product.name 或 part_name 或 oe，用 / 拼
  const items = pricing.value.items || []
  const bits = items.map(it => it.product?.name || it.oe).filter(Boolean)
  if (bits.length) return bits.join(' / ')
  if (p.value.part_name) return p.value.part_name
  if (p.value.oem_no) return p.value.oem_no
  if (p.value.inquiry_content) return p.value.inquiry_content.slice(0, 40)
  return '—'
})
const isMultiPart = computed(() => oeList.value.length > 1)
const timeLabel = computed(() => {
  const t = p.value.inquiry_time || p.value.sent_at || p.value.created_at
  if (!t) return ''
  const d = new Date(t)
  const now = new Date()
  const sameDay = d.toDateString() === now.toDateString()
  if (sameDay) {
    const hh = String(d.getHours()).padStart(2, '0')
    const mm = String(d.getMinutes()).padStart(2, '0')
    return `${hh}:${mm}`
  }
  return `${d.getMonth() + 1}/${d.getDate()}`
})

/* ============= 展开详情数据 ============= */
const carFull = computed(() => {
  if (!car.value) return ''
  const bits = [
    carModelStr.value,
    car.value.yearPattern,
    car.value.displacement,
    car.value.fuel,
  ].filter(Boolean)
  return bits.join(' · ')
})
const sourceLabel = computed(() => {
  const bits = []
  const convName = p.value.conversation_name
  const sender = p.value.sender_name
  if (convName && !isWechatId(convName)) bits.push(convName)
  if (sender && !isWechatId(sender)) bits.push('· 成员 ' + sender)
  if (!bits.length) return ''
  return bits.join('  ')
})
const quoteText = computed(() => pricing.value.text || '')

/* ============= 操作 ============= */
function toggle(e) {
  if (e.target.closest('.q-btn') || e.target.closest('.q-row-time')) return
  expanded.value = !expanded.value
}
function copyText(text, okLabel) {
  if (!text) { ElMessage.warning('没有可复制内容'); return }
  navigator.clipboard.writeText(text)
    .then(() => ElMessage.success(okLabel))
    .catch(() => ElMessage.error('复制失败'))
}

/** 定位聊天气泡 —— 切会话 + 滚动到 inquiry 关联的消息 */
async function onJumpToBubble() {
  const { conversation_id: convId, message_id: msgId } = p.value
  if (!convId) { ElMessage.warning('该询价未关联会话'); return }
  if (!chatPanelRef.value?.locateMessage) {
    ElMessage.error('聊天面板未就绪，请稍候再试'); return
  }
  if (!msgId) {
    ElMessage.warning('该询价暂无关联消息，将打开会话定位到最新');
  }
  try {
    await chatPanelRef.value.locateMessage({ convId, id: msgId || 0 })
    if (msgId) ElMessage.success('已定位到询价消息')
  } catch (e) {
    ElMessage.error('定位失败：' + (e.message || '未知原因'))
  }
}
async function doIgnore() {
  try {
    await ignoreQuoteInquiry(p.value.id)
    ElMessage.success('已忽略')
    emit('refresh')
  } catch (e) {
    ElMessage.error(e.message || '操作失败')
  }
}
function retryVIN() {
  ElMessage.info('重试 VIN — 后续接入后端接口')
}
function openDetail() {
  emit('open-detail', p.value.id)
}
</script>

<template>
  <li class="quote-item" :class="{ expanded, error: isError }" @click="toggle">

    <!-- ========== 收起行 ========== -->
    <div class="q-row">
      <div class="q-status" :class="statusChip.cls">{{ statusChip.label }}</div>
      <div class="q-body">
        <div class="q-body-vin">
          <span class="q-vin" :class="{ empty: primaryLabel === '未识别' }">{{ primaryLabel }}</span>
          <span v-if="isMultiPart" class="q-ic">{{ oeList.length }} 项</span>
        </div>
        <div class="q-body-oe">
          <span class="q-oe" :class="{ empty: partNames === '—' }">{{ partNames }}</span>
        </div>
      </div>
      <div class="q-row-time">{{ timeLabel }}</div>
      <div class="q-arrow" :class="{ open: expanded }">
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M2.5 3.5L5 6L7.5 3.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>
      </div>
    </div>

    <!-- ========== 展开详情 ========== -->
    <Transition name="expand">
      <div v-if="expanded" class="q-expand">

        <!-- 来源条（三种模板共有） -->
        <div v-if="sourceLabel" class="q-source">来自 {{ sourceLabel }}</div>

        <!-- ===== 模板 normal（所有非 error 条目统一） ===== -->
        <template v-if="tpl === 'normal'">
          <!-- 车辆识别信息 -->
          <div class="q-card">
            <div class="q-card-title">车辆识别信息</div>
            <div class="q-kv"><span class="q-k">VIN</span><span class="q-v mono">{{ carVIN || '—' }}</span></div>
            <div class="q-kv"><span class="q-k">车型</span><span class="q-v">{{ carFull || carModelStr || '—' }}</span></div>
          </div>

          <!-- OE 清单（品牌/完整报价留给详情页） -->
          <div class="q-card">
            <div class="q-card-title">
              OE 清单
              <template v-if="oeList.length">（{{ oeList.length }} 项）</template>
            </div>
            <template v-if="oeList.length">
              <div class="q-oes">
                <div v-for="(o, i) in oeList" :key="o + i" class="q-oe-item">
                  <span class="q-oe-num">{{ i + 1 }}</span>
                  <span class="q-oe-code mono">{{ o }}</span>
                </div>
              </div>
            </template>
            <div v-else class="q-empty">暂无 OE 匹配，点击按钮手动查询</div>
          </div>

          <!-- 按钮组 -->
          <div class="q-actions">
            <button class="q-btn primary q-btn-lg" @click.stop="openDetail">打开详情页报价</button>
            <button class="q-btn ghost q-btn-lg" @click.stop="onJumpToBubble">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:-1px;margin-right:4px">
                <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>
              </svg>
              定位聊天气泡
            </button>
            <button class="q-btn ghost q-btn-lg" @click.stop="copyText(quoteText || p.inquiry_content || p.part_name, '内容已复制')">复制内容</button>
          </div>
        </template>

        <!-- ===== 模板 C：错误 ===== -->
        <template v-else-if="tpl === 'error'">
          <div class="q-card error">
            <div class="q-error-msg">
              <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><circle cx="6.5" cy="6.5" r="5.5" stroke="currentColor" stroke-width="1.2"/><path d="M6.5 4v2.5M6.5 9h.01" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>
              <span>{{ pj.error }}</span>
            </div>
          </div>
          <div class="q-card">
            <div class="q-card-title">原始 VIN 信息</div>
            <div class="q-kv"><span class="q-k">原始 VIN</span>
              <span class="q-v mono red">{{ carVIN || '—' }}</span>
            </div>
            <div class="q-kv"><span class="q-k">报错步骤</span>
              <span class="q-v">{{ pj.error_step || '—' }}</span>
            </div>
          </div>
          <div class="q-actions">
            <button class="q-btn ghost q-btn-lg" @click.stop="retryVIN">重试 VIN</button>
            <button class="q-btn ghost q-btn-lg" @click.stop="onJumpToBubble">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:-1px;margin-right:4px">
                <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>
              </svg>
              定位聊天气泡
            </button>
            <button class="q-btn ghost q-btn-lg" @click.stop="doIgnore">忽略</button>
          </div>
        </template>

      </div>
    </Transition>
  </li>
</template>

<style scoped>
/* ==================== 基础 ==================== */
.quote-item {
  list-style: none;
  position: relative;
  background: #FFFFFF;
  border-bottom: 1px solid #E5E7EB;
}
/* 左竖指示条（absolute z-index 0，内容 z-index 1，不影响布局） */
.quote-item::before {
  content: '';
  position: absolute; left: 0; top: 0; bottom: 0;
  width: 4px;
  background: transparent;
  z-index: 0;
  transition: background 0.2s;
}
.quote-item.expanded::before {
  background: #3370FF;
}
.quote-item.expanded.error::before {
  background: #D1242F;
}

/* ==================== 收起行 ==================== */
.q-row {
  position: relative; z-index: 1;
  display: grid;
  grid-template-columns: 56px 1fr auto 28px;
  gap: 10px;
  min-height: 52px;
  padding: 10px 16px;
  align-items: center;
  cursor: pointer;
  transition: background 0.12s;
}
.q-row:hover { background: #FAFBFC; }
.quote-item.expanded > .q-row:hover { background: transparent; }

/* 状态 pill */
.q-status {
  font-size: 10.5px; font-weight: 600; line-height: 1;
  padding: 3px 8px; border-radius: 10px; text-align: center;
  white-space: nowrap; justify-self: start;
}
.q-status.green { background: #E6F4EA; color: #179C52; }
.q-status.amber { background: #FDF6E0; color: #B08800; }
.q-status.red { background: #FDECEE; color: #D1242F; }

/* 主信息双行 —— 固定两行高度，防止任何子元素折行撑高 */
.q-body {
  display: grid;
  grid-template-rows: 16px 14px;   /* 两行固定高，够 12px + 11px 文字 */
  row-gap: 2px;
  min-width: 0;
  overflow: hidden;                /* 兜底：任何溢出直接裁掉 */
}
.q-body-vin { display: flex; align-items: center; gap: 6px; min-width: 0; overflow: hidden; }
.q-vin {
  font-size: 12px; color: #24292F; font-weight: 500; line-height: 16px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  display: block;                  /* block 保证 white-space 必生效 */
}
.q-vin.empty { color: #B4BBC4; font-style: italic; font-family: inherit; }
.q-ic {
  font-size: 9.5px; font-weight: 600; flex-shrink: 0; line-height: 1;
  color: #3370FF; background: #EAF0FB;
  padding: 1px 6px; border-radius: 8px;
}
/* 收起态 OE 单行 */
.q-body-oe {
  font-size: 11px; color: #8C959F;
  font-family: 'SF Mono', Consolas, Menlo, monospace;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  line-height: 14px;
}
.q-oe { display: inline; }
.q-oe + .q-oe::before { content: ' · '; color: #C9CDD2; }
.q-oe.empty { color: #C9CDD2; font-style: italic; font-family: inherit; }

/* 时间 */
.q-row-time {
  font-size: 11px; color: #B4BBC4;
  font-family: 'SF Mono', Consolas, Menlo, monospace;
  white-space: nowrap; justify-self: end;
}

/* 箭头 */
.q-arrow {
  display: flex; align-items: center; justify-content: center;
  width: 20px; height: 20px; color: #B4BBC4;
  transition: transform 0.2s;
}
.q-arrow.open { transform: rotate(180deg); color: var(--c-text-sub); }

/* ==================== 展开详情 ==================== */
.q-expand {
  position: relative; z-index: 1;
  padding: 0 16px 16px 16px;
  border-bottom: 1px solid #E5E7EB;
  display: flex; flex-direction: column; gap: 10px;
}

/* 来源条 */
.q-source {
  font-size: 11px; color: var(--c-text-muted);
  padding: 6px 0 2px 0;
}

/* 白色圆角卡片 */
.q-card {
  background: #FFFFFF;
  border: 1px solid #EAECEF;
  border-radius: 8px;
  padding: 10px 12px;
}
.q-card.error {
  background: #FDECEE;
  border-color: #F5C2C2;
}

.q-card-title {
  font-size: 11px; font-weight: 600; color: var(--c-text-muted);
  margin-bottom: 8px; letter-spacing: 0.3px;
}

/* key-value 行 */
.q-kv {
  display: grid; grid-template-columns: 72px 1fr;
  gap: 8px; align-items: center;
  font-size: 11.5px; line-height: 1.6;
}
.q-kv + .q-kv { margin-top: 2px; }
.q-k { color: var(--c-text-muted); }
.q-v { color: var(--c-text); word-break: break-all; }
.q-v.mono { font-family: 'SF Mono', Consolas, Menlo, monospace; }
.q-v.red { color: #D1242F; }

/* 空提示 */
.q-empty {
  font-size: 11.5px; color: #B4BBC4;
  text-align: center; padding: 12px 0;
}

/* 错误消息 */
.q-error-msg {
  display: flex; align-items: flex-start; gap: 6px;
  font-size: 11.5px; color: #D1242F; line-height: 1.5;
}
.q-error-msg svg { flex-shrink: 0; margin-top: 1px; }

/* OE 清单（纯编号列表，品牌报价留给详情页） */
.q-oes { display: flex; flex-direction: column; gap: 2px; }
.q-oe-item {
  display: flex; align-items: center; gap: 8px;
  padding: 5px 10px; border-radius: 4px;
  font-size: 12px;
}
.q-oe-item:hover { background: #F7F8FA; }
.q-oe-num {
  width: 18px; height: 18px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 10px; font-weight: 600; color: #8C959F;
  background: #F0F2F5; border-radius: 4px;
}
.q-oe-code {
  color: var(--c-text);
  font-family: 'SF Mono', Consolas, Menlo, monospace;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

/* ==================== 按钮 ==================== */
.q-actions {
  display: flex; gap: 8px; padding-top: 2px;
}
.q-btn {
  font-family: inherit; cursor: pointer;
  border-radius: 6px; font-weight: 500;
  transition: all 0.12s; border: 1px solid transparent;
}
.q-btn-lg { padding: 7px 16px; font-size: 12px; }
.q-btn.primary {
  background: #3370FF; color: #FFFFFF;
}
.q-btn.primary:hover { background: #2461F0; }
.q-btn.ghost {
  background: #FFFFFF; color: var(--c-text-sub);
  border-color: #E2E5EA;
}
.q-btn.ghost:hover { background: #F5F7FA; color: var(--c-text); }

/* ==================== 过渡 ==================== */
.expand-enter-active, .expand-leave-active {
  transition: opacity 0.18s ease;
}
.expand-enter-from, .expand-leave-to {
  opacity: 0;
}
</style>
