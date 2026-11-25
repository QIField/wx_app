<script setup>
/** 全屏报价详情页（新开标签页）
 *
 * 路由: /quote-detail/:id —— history 路由，独立于工作台 main window
 * 数据源: GET /api/quote/inquiries/:id
 * 布局: 深蓝汇总卡 + 车辆横幅 + 侧栏配件清单 + 主内容图片列表格 + 产品档案 + 报价话术 + 改价发送
 *
 * 视觉 token 自成体系（复用 --c-primary / --f-num 等全局变量，零外部依赖）。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { fetchQuoteInquiry, sendQuoteInquiry, ignoreQuoteInquiry, saveQuoteOverride } from '../api'

const route = useRoute()
const router = useRouter()

const loading = ref(true)
const error = ref('')
const inquiry = ref(null)
const priceInput = ref('')
const busy = ref(false)

/** 图片预览（与 ChatPanel 共用 el-image-viewer，支持缩放/旋转/左右切换） */
const preview = ref(null) // { urls: [], index: 0 }
function openPreview(url, list) {
  // 去重 + 保持顺序，点击定位在当前那张
  const urls = [...new Set(list.filter(Boolean))]
  const index = urls.indexOf(url)
  if (urls.length) preview.value = { urls, index: Math.max(0, index) }
}

const data = computed(() => inquiry.value || {})
const r = computed(() => {
  const pj = data.value.price_json
  // 后端可能返回 JSON string（SQLite 边界情况），兜底 parse
  if (typeof pj === 'string') { try { return JSON.parse(pj) } catch { return {} } }
  return pj || {}
})
// 兜底逻辑：后端有时会把 car 覆盖成 {}，此时用 inquiry 顶层字段拼凑
const car = computed(() => {
  const c = r.value.car
  if (c && Object.keys(c).length > 0) return c
  // 兜底：顶层 vin 可能有，但 brandName/model 没了
  return { vin: data.value.vin || '', brandName: '', model: '', yearPattern: '', fuel: '', displacement: '' }
})
const items = computed(() => (r.value.pricing || {}).items || [])
const product = computed(() => r.value.product)
const quoteText = computed(() => ((r.value.pricing || {}).text || '').trim())
const pricing = computed(() => r.value.pricing || {})

const finalPriceOverride = ref(null)
const finalPrice = computed(() => {
  if (finalPriceOverride.value != null) return finalPriceOverride.value
  return pricing.value.final_price
})
const itemCount = computed(() => items.value.length)

/** 所有可预览图片（去重，按 items + 产品档案顺序） */
const allImages = computed(() => {
  const set = new Set()
  for (const it of items.value) {
    const u = it.product?.image
    if (u) set.add(u)
  }
  const pu = product.value?.image
  if (pu) set.add(pu)
  return [...set]
})
const carLine = computed(() => {
  const c = car.value
  if (!c || !c.brandName) {
    // 连 brandName 都没有 → 显示 part_name 兜底
    return data.value.part_name || '（未识别车型）'
  }
  const head = [c.brandName, c.model].filter(Boolean).join(' ')
  const tail = [c.yearPattern ? `${c.yearPattern}款` : '', c.displacement, c.fuel].filter(Boolean).join(' ')
  return tail ? `${head} ${tail}` : head
})
const vinShort = computed(() => {
  const v = car.value.vin || data.value.vin
  if (!v) return ''
  return v.length > 8 ? '···' + v.slice(-8) : v
})

async function load(id) {
  loading.value = true; error.value = ''
  try {
    inquiry.value = await fetchQuoteInquiry(id)
    finalPriceOverride.value = null // 新询价重置本地 override
  } catch (e) { error.value = e.message || '加载失败' }
  finally { loading.value = false }
}

const inquiryId = computed(() => Number(route.params.id) || 0)
onMounted(() => { if (inquiryId.value) load(inquiryId.value) })
watch(inquiryId, (v) => { if (v) load(v) })

function goBack() {
  // 优先回工作台，如果没有历史就新开一个
  if (history.length > 1) router.back()
  else window.open('/', '_blank')
}

/* ---------- 动作 ---------- */
async function onSend() {
  const price = priceInput.value.trim()
  if (price && !(Number(price) > 0)) { ElMessage.warning('改价需 > 0'); return }
  busy.value = true
  try {
    await sendQuoteInquiry(data.value.id, price)
    ElMessage.success('报价已发送')
    await load(data.value.id)
  } catch (e) { ElMessage.error(e.message || '发送失败') }
  finally { busy.value = false }
}
async function onIgnore() {
  busy.value = true
  try {
    await ignoreQuoteInquiry(data.value.id)
    ElMessage.success('已忽略')
    await load(data.value.id)
  } catch (e) { ElMessage.error(e.message || '操作失败') }
  finally { busy.value = false }
}
async function copyText() {
  try { await navigator.clipboard.writeText(quoteText.value); ElMessage.success('话术已复制') }
  catch { ElMessage.error('复制失败') }
}

/* ---------- 行内改价 debounce 自动保存 ---------- */
const saveState = ref('') // '' | 'dirty' | 'saving' | 'saved' | 'error'
let debounceTimer = null

function updateItemPrice(it, val) {
  const n = Number(val)
  if (Number.isNaN(n) || n <= 0) return
  it.final_price = n
  saveState.value = 'dirty'
  // debounce 800ms 自动保存
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(saveAllOverrides, 800)
}

async function saveAllOverrides() {
  if (saveState.value === 'saving' || saveState.value === 'saved') return
  const dirty = items.value.filter((it) => {
    const original = pricing.value.items?.find?.((x) => x.oe === it.oe)
    return String(it.final_price) !== String(original?.final_price)
  })
  if (!dirty.length) { saveState.value = ''; return }
  saveState.value = 'saving'
  try {
    await saveQuoteOverride(data.value.id, dirty.map((it) => ({
      oe: it.oe, final_price: Number(it.final_price).toFixed(2),
    })))
    saveState.value = 'saved'
    // 汇总卡 final_price 本地联动刷新（用 override ref，不直接改 pricing computed）
    const newTotal = items.value.reduce((s, i) => s + Number(i.final_price || 0), 0).toFixed(2)
    finalPriceOverride.value = newTotal
    // 2s 后清 saved 提示
    setTimeout(() => { if (saveState.value === 'saved') saveState.value = '' }, 2000)
  } catch (e) {
    saveState.value = 'error'
    ElMessage.error('改价保存失败：' + (e.message || e))
  }
}
</script>

<template>
  <div class="qd">
    <!-- ===== 顶部栏 ===== -->
    <header class="topbar">
      <div class="tb-left">
        <button class="tb-back" @click="goBack">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M15 18l-6-6 6-6"/>
          </svg>
          返回工作台
        </button>
        <div class="tb-breadcrumb">
          <span>报价管理</span><span class="sep">/</span>
          <span>询价单 #{{ data.id }}</span><span class="sep">/</span>
          <span class="cur">报价详情</span>
        </div>
      </div>
      <div class="tb-right">
        <template v-if="data.status_label">
          <span class="status-tag" :class="'s' + data.status">{{ data.status_label }}</span>
        </template>
      </div>
    </header>

    <!-- ===== 加载态 / 错误 ===== -->
    <div v-if="loading" class="loading">
      <div class="spinner"></div> 加载报价详情中...
    </div>
    <div v-else-if="error" class="loading err">
      ❌ {{ error }}
    </div>

    <main v-else class="main">

      <!-- ===== 深蓝汇总卡（视觉焦点）===== -->
      <section class="summary">
        <div class="s-left">
          <div class="s-label">最终报价</div>
          <div class="s-price"><span class="cur">¥</span>{{ finalPrice || '—' }}</div>
          <div class="s-sub" v-if="pricing.level || pricing.rate">
            <span v-if="pricing.level">客户等级：{{ pricing.level === 'normal' ? '普通客户' : pricing.level }}</span>
            <span v-if="pricing.rate">· 报价系数 {{ (pricing.rate * 100).toFixed(0) }}%</span>
          </div>
        </div>
        <div class="s-stats">
          <div class="stat">
            <div class="stat-label">配件小计</div>
            <div class="stat-value num">¥{{ items.reduce((s, i) => s + Number(i.cost_price || 0), 0).toFixed(2) }}</div>
          </div>
          <div class="stat">
            <div class="stat-label">配件数量</div>
            <div class="stat-value num">{{ itemCount }} 款</div>
          </div>
          <div class="stat">
            <div class="stat-label">原始售价</div>
            <div class="stat-value num">¥{{ product?.store_price || '—' }}</div>
          </div>
          <div class="stat" v-if="pricing.save_percent != null">
            <div class="stat-label">省钱比例</div>
            <div class="stat-value num save">{{ pricing.save_percent }}%</div>
          </div>
        </div>
      </section>

      <!-- ===== 车辆横幅 ===== -->
      <section class="vbanner">
        <div class="vb-icon">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8">
            <path d="M14 16H9m10 0h3v-3.15a1 1 0 0 0-.84-.99L16 11l-2.7-3.6a1 1 0 0 0-.8-.4H5.24a2 2 0 0 0-1.8 1.1l-.8 1.63A6 6 0 0 0 2 12.42V16h2"/>
            <circle cx="6.5" cy="16.5" r="2.5"/><circle cx="16.5" cy="16.5" r="2.5"/>
          </svg>
        </div>
        <div class="vb-info">
          <div class="vb-title">{{ carLine }}</div>
          <div class="vb-fields">
            <span v-if="vinShort"><b>VIN</b> {{ vinShort }}</span>
            <span v-if="data.part_name"><b>配件</b> {{ data.part_name }}</span>
            <span v-if="data.sender_name"><b>询价人</b> {{ data.sender_name }}</span>
            <span v-if="data.inquiry_time"><b>时间</b> {{ data.inquiry_time }}</span>
          </div>
        </div>
      </section>

      <!-- ===== 双栏：侧栏配件清单 + 主内容 ===== -->
      <div class="grid">
        <!-- 侧栏：配件清单 -->
        <aside class="sidebar">
          <div class="sb-head">
            <div class="sb-title">询价配件清单</div>
            <div class="sb-count">共 {{ itemCount }} 项</div>
          </div>
          <div class="sb-list">
            <div v-for="(it, i) in items" :key="i" class="sb-item" :class="{ active: i === 0 }">
              <img v-if="it.product?.image" class="sb-img" :src="it.product.image" @click="openPreview(it.product.image, allImages)">
              <div v-else class="sb-img ph">图</div>
              <div class="sb-info">
                <div class="sb-name" :title="it.part || it.product?.product_name">{{ it.part || it.product?.product_name || '—' }}</div>
                <div class="sb-oe num">{{ it.oe }}</div>
                <div class="sb-bottom">
                  <span class="sb-brand">{{ it.product?.brand_name }}</span>
                  <span class="sb-price num">¥{{ it.final_price || it.cost_price }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 产品档案快照 -->
          <div v-if="product" class="prod-card">
            <div class="prod-card-title">原始产品档案</div>
            <div v-if="product.image" class="prod-img-wrap">
              <img :src="product.image" @click="openPreview(product.image, allImages)">
            </div>
            <div class="prod-name">{{ product.product_name }}</div>
            <div class="prod-sub" v-if="product.sell_point">{{ product.sell_point }}</div>
            <div v-if="product.child?.length" class="child-list">
              <div v-for="(c, i) in product.child.slice(0, 6)" :key="i" class="child-row">
                <span class="c-brand">{{ c.brand_name }}</span>
                <span class="c-cost num">¥{{ c.cost_price }}</span>
                <span class="c-stock" :class="{ low: c.stock <= 5 }">
                  {{ c.stock ? (c.stock > 10 ? '现货' : `仅剩${c.stock}`) : '缺货' }}
                </span>
              </div>
            </div>
          </div>
        </aside>

        <!-- 主内容：完整图片列表格 + 报价条款 + 话术 + 改价 -->
        <section class="main-col">
          <!-- 图片列表格 -->
          <div class="section">
            <div class="section-head">
              <div class="section-title">报价明细（{{ itemCount }} 款）</div>
              <div class="section-actions">
                <!-- 保存状态指示器：改价 debounce 自动保存 -->
                <span class="save-indicator" :class="'si-' + saveState" v-if="saveState">
                  <svg v-if="saveState === 'saving'" class="spin" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
                  </svg>
                  <span v-else-if="saveState === 'saved'">✓ 已保存</span>
                  <span v-else-if="saveState === 'dirty'">⏱ 待保存…</span>
                  <span v-else-if="saveState === 'error'">✗ 保存失败</span>
                </span>
                <button class="btn btn-sm btn-ghost" @click="copyText" v-if="quoteText">复制所有报价</button>
              </div>
            </div>
            <div class="table-wrap">
              <table class="q-table">
                <thead>
                  <tr>
                    <th style="width:52px">图片</th>
                    <th style="width:140px">OE码</th>
                    <th style="width:120px">品牌</th>
                    <th>规格</th>
                    <th style="text-align:right;width:100px">销售价</th>
                    <th style="text-align:right;width:100px">成本价</th>
                    <th style="text-align:center;width:80px">库存</th>
                    <th style="text-align:right;width:100px">最终报价</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(it, i) in items" :key="i">
                    <td>
                      <img v-if="it.product?.image" class="t-thumb" :src="it.product.image" @click="openPreview(it.product.image, allImages)">
                      <div v-else class="t-thumb ph">图</div>
                    </td>
                    <td class="num td-oe">{{ it.oe }}</td>
                    <td>
                      <span class="brand-tag" :class="{ red: it.product?.brand_name === '原厂' || it.product?.brand_name === '马勒' }">
                        {{ it.product?.brand_name || '-' }}
                      </span>
                    </td>
                    <td class="td-spec">{{ it.product?.sell_point || it.part }}</td>
                    <td class="num">¥{{ it.product?.store_price || it.sale_price || '—' }}</td>
                    <td class="num">¥{{ it.cost_price }}</td>
                    <td class="td-stock">
                      <span v-if="it.product?.child?.[0]" class="stock-chip" :class="
                        it.product.child.reduce((s, c) => s + Number(c.stock || 0), 0) > 10 ? 'in' :
                        it.product.child.reduce((s, c) => s + Number(c.stock || 0), 0) > 0 ? 'low' : 'out'
                      ">
                        {{ it.product.child.reduce((s, c) => s + Number(c.stock || 0), 0) > 0 ? '现货' : '缺货' }}
                      </span>
                    </td>
                    <td class="num td-final">
                      <input
                        class="t-input" type="number" min="0" step="0.01"
                        :value="it.final_price"
                        @input="updateItemPrice(it, $event.target.value)"
                      >
                    </td>
                  </tr>
                </tbody>
                <tfoot>
                  <tr>
                    <td colspan="6" class="tfoot-label">费用汇总</td>
                    <td colspan="2" class="tfoot-value num">
                      ¥{{ items.reduce((s, i) => s + Number(i.final_price || i.cost_price || 0), 0).toFixed(2) }}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>

          <!-- 报价话术 -->
          <div class="section" v-if="quoteText">
            <div class="section-head">
              <div class="section-title">AI 生成报价话术</div>
              <div class="section-actions">
                <button class="btn btn-sm btn-ghost" @click="copyText">复制话术</button>
              </div>
            </div>
            <pre class="quote-text">{{ quoteText }}</pre>
          </div>

          <!-- 改价 & 发送 -->
          <div class="section" v-if="[0,1].includes(data.status)">
            <div class="section-head">
              <div class="section-title">人工处理</div>
            </div>
            <div class="send-row">
              <div class="send-left">
                <div class="send-label">改价（可选，留空用自动报价）</div>
                <div class="send-input-wrap">
                  <span class="send-prefix">¥</span>
                  <input v-model="priceInput" class="send-input" type="number" min="0" step="0.01"
                         placeholder="输入新报价，回车发送">
                </div>
              </div>
              <div class="send-right">
                <button class="btn btn-lg btn-ignore" :disabled="busy" @click="onIgnore">忽略此询价</button>
                <button class="btn btn-lg btn-send" :disabled="busy" @click="onSend">
                  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M22 2 11 13"/><path d="M22 2l-7 20-4-9-9-4 20-7z"/>
                  </svg>
                  发送报价
                </button>
              </div>
            </div>
          </div>
          <div v-else-if="data.sent_at" class="sent-banner">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>
            </svg>
            已于 {{ data.sent_at }} 发送报价
          </div>
        </section>
      </div>
    </main>

    <!-- 图片全屏预览（与 ChatPanel 共用 el-image-viewer，支持缩放/旋转/键盘方向键切换） -->
    <el-image-viewer
      v-if="preview"
      :url-list="preview.urls"
      :initial-index="preview.index"
      hide-on-click-modal
      @close="preview = null"
    />
  </div>
</template>

<style scoped>
/* ===== 全局 token（复用工作台品牌变量）===== */
.qd {
  --c-primary: #E82016;
  --c-primary-deep: #C31A0E;
  --c-primary-soft: #FDEBEA;
  --c-navy: #0E1C3D;
  --c-navy-2: #234A92;
  --c-bg: #F4F6FA;
  --c-surface: #FFFFFF;
  --c-panel: #FAFBFD;
  --c-text: #1F2D3D;
  --c-text-sub: #8A97A6;
  --c-text-muted: #C3CDD8;
  --c-border: #EAF1F7;
  --c-border-strong: #D9E2EC;
  --c-danger: #DC2626;
  --f-num: ui-monospace, 'SF Mono', 'Menlo', 'PingFang SC', monospace;

  min-height: 100vh;
  background: var(--c-bg);
  font-family: 'PingFang SC', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  color: var(--c-text);
}

/* ===== 顶部栏 ===== */
.topbar {
  position: sticky; top: 0; z-index: 100;
  display: flex; justify-content: space-between; align-items: center;
  height: 48px; padding: 0 18px;
  background: linear-gradient(92deg, #0e1c3d 0%, var(--c-navy) 34%, var(--c-navy-2) 72%, #234a92 100%);
  color: #fff;
  box-shadow: 0 1px 6px rgba(14,28,61,0.18);
}
.tb-left { display: flex; align-items: center; gap: 14px; }
.tb-back {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 12px; color: rgba(255,255,255,0.9);
  padding: 4px 10px; border-radius: 6px;
  border: 1px solid rgba(255,255,255,0.25); background: rgba(255,255,255,0.08);
  cursor: pointer; transition: all 0.15s;
}
.tb-back:hover { background: rgba(255,255,255,0.18); border-color: rgba(255,255,255,0.5); }
.tb-breadcrumb { font-size: 12px; opacity: 0.85; display: flex; align-items: center; gap: 6px; }
.tb-breadcrumb .sep { opacity: 0.4; }
.tb-breadcrumb .cur { opacity: 1; font-weight: 500; }
.status-tag {
  font-size: 11px; padding: 3px 10px; border-radius: 999px; font-weight: 500;
  background: rgba(255,255,255,0.18);
}
.status-tag.s0, .status-tag.s1 { background: #FEF3C7; color: #92400E; }
.status-tag.s3 { background: #DCFCE7; color: #15803D; }
.status-tag.s4 { background: #F1F5F9; color: #64748B; }
.status-tag.s2 { background: #FEE2E2; color: #991B1B; }

/* ===== 加载态 ===== */
.loading {
  display: grid; place-items: center; gap: 12px;
  padding: 80px 20px; text-align: center;
  color: var(--c-text-sub); font-size: 14px;
}
.loading.err { color: var(--c-danger); }
.spinner {
  width: 24px; height: 24px; border-radius: 50%;
  border: 2.5px solid var(--c-border); border-top-color: var(--c-primary);
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ===== 主布局 ===== */
.main {
  max-width: 1400px; margin: 0 auto;
  padding: 24px 28px 60px;
  display: flex; flex-direction: column; gap: 18px;
}

/* ===== 深蓝汇总卡 ===== */
.summary {
  display: flex; justify-content: space-between; align-items: stretch;
  background: linear-gradient(135deg, #0E1C3D 0%, #1A3A72 100%);
  color: #fff; padding: 24px 30px; border-radius: 14px;
  box-shadow: 0 6px 24px rgba(14,28,61,0.22);
  position: relative; overflow: hidden;
}
.summary::after {
  content: ''; position: absolute; top: -30px; right: -30px;
  width: 180px; height: 180px; border-radius: 50%;
  background: rgba(255,255,255,0.07);
}
.summary::before {
  content: ''; position: absolute; bottom: -50px; left: -50px;
  width: 220px; height: 220px; border-radius: 50%;
  background: rgba(232,32,22,0.12);
}
.s-left { position: relative; z-index: 1; display: flex; flex-direction: column; justify-content: center; }
.s-label { font-size: 12px; opacity: 0.7; letter-spacing: 2px; margin-bottom: 6px; }
.s-price {
  font-family: var(--f-num); font-size: 48px; font-weight: 800;
  letter-spacing: -2px; line-height: 1;
}
.s-price .cur { font-size: 22px; font-weight: 600; margin-right: 2px; opacity: 0.9; }
.s-sub { font-size: 12px; opacity: 0.7; margin-top: 10px; display: flex; gap: 8px; }

.s-stats {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 18px;
  position: relative; z-index: 1;
}
.stat {
  background: rgba(255,255,255,0.08); backdrop-filter: blur(4px);
  border: 1px solid rgba(255,255,255,0.15);
  border-radius: 10px; padding: 12px 16px;
  text-align: left; min-width: 110px;
}
.stat-label { font-size: 11px; opacity: 0.65; letter-spacing: 0.5px; margin-bottom: 6px; }
.stat-value { font-family: var(--f-num); font-size: 20px; font-weight: 700; line-height: 1.2; }
.stat-value.num.save { color: #FCD34D; }

/* ===== 车辆横幅 ===== */
.vbanner {
  display: flex; gap: 16px; align-items: center;
  background: var(--c-surface); border: 1px solid var(--c-border);
  border-radius: 12px; padding: 16px 22px;
  box-shadow: 0 1px 4px rgba(14,28,61,0.04);
}
.vb-icon {
  width: 44px; height: 44px; flex-shrink: 0;
  display: grid; place-items: center;
  background: linear-gradient(135deg, var(--c-primary-soft), #FCE4E0);
  border-radius: 10px; color: var(--c-primary);
}
.vb-info { flex: 1; min-width: 0; }
.vb-title { font-size: 18px; font-weight: 600; color: var(--c-text); margin-bottom: 6px; }
.vb-fields { display: flex; flex-wrap: wrap; gap: 10px; font-size: 12px; color: var(--c-text-sub); }
.vb-fields b { color: var(--c-text-muted); font-weight: 500; margin-right: 2px; }

/* ===== 双栏布局 ===== */
.grid {
  display: grid; grid-template-columns: 340px 1fr; gap: 18px;
  align-items: start;
}

/* ===== 侧栏 ===== */
.sidebar {
  background: var(--c-surface); border: 1px solid var(--c-border);
  border-radius: 12px; padding: 0; overflow: hidden;
  box-shadow: 0 1px 4px rgba(14,28,61,0.04);
  position: sticky; top: 66px;
  max-height: calc(100vh - 82px); overflow-y: auto;
}
.sb-head { padding: 14px 16px; border-bottom: 1px solid var(--c-border); }
.sb-title { font-size: 13px; font-weight: 600; color: var(--c-text); }
.sb-count { font-size: 11px; color: var(--c-text-sub); margin-top: 2px; }
.sb-list { padding: 8px; display: flex; flex-direction: column; gap: 6px; }
.sb-item {
  display: flex; gap: 8px; padding: 8px; border-radius: 8px;
  border: 1px solid var(--c-border); cursor: pointer;
  transition: all 0.15s;
}
.sb-item:hover { border-color: var(--c-primary); background: var(--c-primary-soft); }
.sb-item.active { border-color: var(--c-primary); background: var(--c-primary-soft); box-shadow: 0 0 0 2px rgba(232,32,22,0.12); }
.sb-img {
  width: 48px; height: 48px; flex-shrink: 0;
  object-fit: cover; border-radius: 6px;
  border: 1px solid var(--c-border); cursor: zoom-in; background: var(--c-bg);
}
.sb-img.ph { display: grid; place-items: center; font-size: 10px; color: var(--c-text-muted); }
.sb-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 1px; }
.sb-name { font-size: 12px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sb-oe { font-size: 10px; color: var(--c-text-muted); }
.sb-bottom { display: flex; justify-content: space-between; align-items: center; margin-top: 2px; }
.sb-brand { font-size: 10px; color: var(--c-text-sub); }
.sb-price { font-size: 12px; font-weight: 700; color: var(--c-primary); }

/* 产品档案快照 */
.prod-card { padding: 14px 16px; border-top: 1px solid var(--c-border); background: var(--c-panel); }
.prod-card-title { font-size: 11px; font-weight: 600; color: var(--c-text-sub); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px; }
.prod-img-wrap { margin-bottom: 8px; }
.prod-img-wrap img {
  width: 100%; max-height: 120px; object-fit: contain;
  border-radius: 8px; border: 1px solid var(--c-border); background: #fff;
  cursor: zoom-in;
}
.prod-name { font-size: 13px; font-weight: 600; color: var(--c-text); }
.prod-sub { font-size: 11px; color: var(--c-text-sub); margin-bottom: 10px; }
.child-list { display: flex; flex-direction: column; gap: 3px; }
.child-row { display: flex; justify-content: space-between; font-size: 11px; padding: 2px 0; }
.c-brand { color: var(--c-text); }
.c-cost { color: var(--c-primary); font-weight: 600; }
.c-stock { color: #15803d; font-size: 10px; }
.c-stock.low { color: #b45309; }

/* ===== 主内容列 ===== */
.main-col { display: flex; flex-direction: column; gap: 18px; min-width: 0; }

.section {
  background: var(--c-surface); border: 1px solid var(--c-border);
  border-radius: 12px;
  box-shadow: 0 1px 4px rgba(14,28,61,0.04);
  overflow: hidden;
}
.section-head {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 20px; border-bottom: 1px solid var(--c-border);
}
.section-title { font-size: 13px; font-weight: 600; color: var(--c-text); }
.section-actions { display: flex; gap: 8px; }
.section-head + * { padding: 0; }
.section > :not(.section-head) { padding: 16px 20px 20px; }

/* 按钮 */
.btn {
  display: inline-flex; align-items: center; gap: 5px;
  font-size: 12px; padding: 6px 14px;
  border-radius: 7px; border: 1px solid var(--c-border-strong);
  background: var(--c-surface); color: var(--c-text);
  cursor: pointer; transition: all 0.15s; font-weight: 500;
}
.btn:hover { border-color: var(--c-primary); color: var(--c-primary); }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-sm { font-size: 11px; padding: 4px 10px; }
.btn-lg { font-size: 13px; padding: 9px 20px; }
.btn-primary { background: var(--c-primary); border-color: var(--c-primary-deep); color: #fff; font-weight: 600; box-shadow: 0 1px 4px rgba(232,32,22,0.25); }
.btn-primary:hover { background: var(--c-primary-deep); }
.btn-ghost { background: transparent; border-color: var(--c-border); color: var(--c-text-sub); }
.btn-ghost:hover { border-color: var(--c-primary); color: var(--c-primary); background: var(--c-primary-soft); }

/* 保存状态指示器 */
.save-indicator {
  display: inline-flex; align-items: center; gap: 3px;
  font-size: 11px; padding: 3px 9px; border-radius: 999px;
  background: var(--c-panel); color: var(--c-text-muted);
  border: 1px solid var(--c-border);
  font-weight: 500;
  transition: all 0.2s;
}
.save-indicator.si-dirty { color: var(--c-text-sub); border-color: var(--c-border-strong); }
.save-indicator.si-saving { color: #2563eb; border-color: #BFDBFE; background: #EFF6FF; }
.save-indicator.si-saved { color: #15803d; border-color: #BBF7D0; background: #F0FDF4; }
.save-indicator.si-error { color: #b91c1c; border-color: #FECACA; background: #FEF2F2; }
.save-indicator svg.spin { animation: spin 0.8s linear infinite; }

.btn-send { background: var(--c-primary); border-color: var(--c-primary-deep); color: #fff; font-weight: 600; box-shadow: 0 2px 6px rgba(232,32,22,0.3); }
.btn-send:hover:not(:disabled) { background: var(--c-primary-deep); transform: translateY(-1px); }
.btn-ignore { background: transparent; border-color: var(--c-border-strong); color: var(--c-text-sub); }
.btn-ignore:hover:not(:disabled) { border-color: var(--c-danger); color: var(--c-danger); }

/* 表格 */
.table-wrap { overflow-x: auto; }
.q-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.q-table th {
  font-size: 11px; color: var(--c-text-muted); font-weight: 500;
  padding: 10px 12px; text-align: left;
  border-bottom: 1px solid var(--c-border);
  background: var(--c-panel); text-transform: uppercase; letter-spacing: 0.4px;
}
.q-table td {
  padding: 10px 12px; border-bottom: 1px solid var(--c-border);
  vertical-align: middle;
}
.q-table tr:last-child td { border-bottom: none; }

.t-thumb {
  width: 38px; height: 38px; object-fit: cover;
  border-radius: 6px; border: 1px solid var(--c-border);
  cursor: zoom-in; background: var(--c-bg);
  transition: transform 0.15s;
}
.t-thumb:hover { transform: scale(1.08); }
.t-thumb.ph { display: grid; place-items: center; font-size: 10px; color: var(--c-text-muted); }

.num { font-family: var(--f-num); }
.td-oe { color: var(--c-text-muted); font-size: 12px; }
.td-spec { color: var(--c-text-sub); font-size: 12px; }

.brand-tag {
  display: inline-block; font-size: 11px; padding: 2px 8px; border-radius: 999px;
  background: var(--c-bg); color: var(--c-text); border: 1px solid var(--c-border);
}
.brand-tag.red { background: var(--c-primary-soft); color: var(--c-primary); border-color: transparent; }

.stock-chip {
  display: inline-block; font-size: 10px; padding: 2px 8px; border-radius: 999px; font-weight: 500;
}
.stock-chip.in { background: #DCFCE7; color: #15803D; }
.stock-chip.low { background: #FEF3C7; color: #92400E; }
.stock-chip.out { background: #FEE2E2; color: #991B1B; }

.t-input {
  width: 88px; text-align: right;
  font-family: var(--f-num); font-size: 13px; font-weight: 600;
  padding: 4px 6px; border: 1px solid var(--c-border-strong);
  border-radius: 5px; outline: none;
  background: var(--c-bg); transition: border-color 0.15s;
}
.t-input:focus { border-color: var(--c-primary); box-shadow: 0 0 0 2px rgba(232,32,22,0.12); }

.tfoot-label { text-align: right; font-weight: 500; color: var(--c-text-sub); padding-right: 16px; }
.tfoot-value { font-size: 14px; font-weight: 700; color: var(--c-primary); }

/* 条款 */
.terms { padding: 16px 20px; display: flex; flex-direction: column; gap: 12px; }
.term-item { display: flex; gap: 12px; font-size: 13px; line-height: 1.6; color: var(--c-text-sub); }
.term-num {
  width: 24px; height: 24px; flex-shrink: 0;
  display: grid; place-items: center;
  background: var(--c-primary-soft); color: var(--c-primary);
  font-weight: 700; font-size: 12px;
  border-radius: 50%; margin-top: 1px;
}

/* 话术 */
.quote-text {
  margin: 0; padding: 14px 18px;
  font-size: 13px; line-height: 1.7; font-family: inherit;
  color: var(--c-text); background: var(--c-panel);
  border: 1px solid var(--c-border); border-radius: 8px;
  white-space: pre-wrap; word-break: break-all;
  max-height: 280px; overflow-y: auto;
}

/* 改价发送 */
.send-row { padding: 18px 20px; display: flex; justify-content: space-between; align-items: center; gap: 20px; flex-wrap: wrap; }
.send-left { display: flex; flex-direction: column; gap: 6px; flex: 1; min-width: 240px; }
.send-label { font-size: 12px; color: var(--c-text-sub); }
.send-input-wrap {
  display: flex; align-items: center;
  border: 1.5px solid var(--c-border-strong); border-radius: 8px;
  overflow: hidden; transition: border-color 0.15s, box-shadow 0.15s;
  max-width: 300px;
}
.send-input-wrap:focus-within { border-color: var(--c-primary); box-shadow: 0 0 0 3px rgba(232,32,22,0.1); }
.send-prefix { padding: 0 10px; color: var(--c-text-muted); font-weight: 600; }
.send-input {
  flex: 1; min-width: 0;
  border: none; outline: none; font-size: 15px; font-weight: 600;
  padding: 9px 0; font-family: var(--f-num);
}
.send-right { display: flex; gap: 10px; }

.sent-banner {
  display: flex; align-items: center; justify-content: center; gap: 8px;
  padding: 16px; background: #F0FDF4; color: #15803D;
  border-radius: 0 0 12px 12px; font-size: 13px; font-weight: 500;
}

/* ===== 响应式 ===== */
@media (max-width: 1100px) {
  .grid { grid-template-columns: 1fr; }
  .sidebar { position: static; max-height: none; }
  .s-stats { grid-template-columns: repeat(2, 1fr); }
  .summary { flex-direction: column; gap: 18px; }
}
@media (max-width: 700px) {
  .s-price { font-size: 36px; }
  .s-stats { grid-template-columns: repeat(2, 1fr); }
  .vbanner { flex-direction: column; align-items: flex-start; }
  .main { padding: 16px 12px 40px; }
}
</style>
