<script setup>
/** 视图四：设置 —— 报价模式 / AI 执行开关 / 等级价格系数 / 配件黑名单（global 行）。
 *
 * 读 GET /quote/config 回填，保存 PUT /quote/config（仅 admin/developer 可写，
 * 客服保存 403 → toast 后端文案）。黑名单标签可移除、可新增（前端同款预校验）。
 * 话术模板 / 通知配置为原型预留板块：渲染但置灰，标注「待后端支持」。
 */
import { onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { saveQuoteConfig } from '../../api'
import { useQuoteConfig } from '../../composables/useQuoteConfig'
import { useChatStore } from '../../stores/chat'

const chat = useChatStore()
const MAX_BLACKLIST = 20
const MAX_PART_LEN = 20

const loading = ref(true)
const saving = ref(false)
const { aiOn, mode: quoteMode, load: loadConfigFields } = useQuoteConfig()
const rates = ref({ vip_a: '', vip_b: '', normal: '' })
const parts = ref([])
const partInput = ref('')

const RATE_LABELS = [
  { key: 'vip_a', label: 'VIP-A（月结大客户）' },
  { key: 'vip_b', label: 'VIP-B（月结）' },
  { key: 'normal', label: '普通客户' },
]

/* 预留板块（待后端支持，仅展示） */
const TPLS = [
  { key: 'tplA', name: '标准版', text: '【{车型}】\n{配件}（OE {oe}）\n{品牌价格}\n4S对照价 ¥{s4}\n现货速发，量大优惠' },
  { key: 'tplB', name: '热情推销版', text: '老板您好！{车型} {配件} 现货\n{品牌价格}\n比 4S 店便宜一大截\n质保齐全，下单即发' },
  { key: 'tplC', name: '极简版', text: '{配件}：{品牌价格}\nOE {oe}' },
]
const tpl = ref('tplA')
const NOTIFS = [
  { key: 'highInq', title: '高价值询价提醒', desc: '单笔询价金额超过阈值时提醒', th: '5000', on: true },
  { key: 'highPart', title: '高价配件询价提醒', desc: '4S 价超过阈值的配件被询价时提醒', th: '3000', on: true },
  { key: 'unFollow', title: '长时间未跟进询价提醒', desc: '询价超过设定小时数未回复时提醒', th: '24', on: false },
]

onMounted(async () => {
  try {
    await loadConfigFields((cfg) => {
      rates.value = {
        vip_a: cfg.price_map?.vip_a ?? '0.75',
        vip_b: cfg.price_map?.vip_b ?? '0.82',
        normal: cfg.price_map?.normal ?? '0.90',
      }
      parts.value = (cfg.parts_blacklist || []).map((t) => String(t))
    }, chat.activeOpenid)
  } catch (e) {
    ElMessage.error(e.message || '配置加载失败')
  } finally {
    loading.value = false
  }
})

/* ---------- 设备切换联动：重新拉配置（ai_enabled / quote_mode 是设备级） ---------- */
watch(() => chat.activeOpenid, async () => {
  loading.value = true
  try {
    await loadConfigFields((cfg) => {
      rates.value = {
        vip_a: cfg.price_map?.vip_a ?? '0.75',
        vip_b: cfg.price_map?.vip_b ?? '0.82',
        normal: cfg.price_map?.normal ?? '0.90',
      }
      parts.value = (cfg.parts_blacklist || []).map((t) => String(t))
    }, chat.activeOpenid)
  } catch (e) {
    ElMessage.error(e.message || '配置加载失败')
  } finally {
    loading.value = false
  }
})

function addPart() {
  const t = partInput.value.trim()
  if (!t) return
  if (t.length > MAX_PART_LEN) {
    ElMessage.warning(`单个配件不能超过 ${MAX_PART_LEN} 字`)
    return
  }
  if (parts.value.includes(t)) {
    ElMessage.warning('该配件已在黑名单中')
    return
  }
  if (parts.value.length >= MAX_BLACKLIST) {
    ElMessage.warning(`黑名单最多 ${MAX_BLACKLIST} 个配件`)
    return
  }
  parts.value.push(t)
  partInput.value = ''
}

function removePart(i) {
  parts.value.splice(i, 1)
}

async function onSave() {
  for (const { key, label } of RATE_LABELS) {
    const v = Number(rates.value[key])
    if (!(v > 0 && v <= 1)) {
      ElMessage.warning(`${label}系数必须在 (0, 1] 区间`)
      return
    }
  }
  saving.value = true
  try {
    await saveQuoteConfig({
      ai_enabled: aiOn.value,
      quote_mode: quoteMode.value,
      price_map: {
        vip_a: Number(rates.value.vip_a).toFixed(2),
        vip_b: Number(rates.value.vip_b).toFixed(2),
        normal: Number(rates.value.normal).toFixed(2),
      },
      parts_blacklist: parts.value,
    }, chat.activeOpenid)
    ElMessage.success('报价配置已保存')
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div v-loading="loading" class="view">
    <div class="set-sec">
      <div class="sh">基础识别配置</div>
      <div class="sb">
        <div class="set-row">
          <div class="rl">
            <div class="rt">AI 智能识别</div>
          </div>
          <label class="qq-switch sw">
            <input v-model="aiOn" type="checkbox">
            <span class="track"></span>
          </label>
        </div>
        <div class="set-row">
          <div class="rl">
            <div class="rt">自动报价模式</div>
          </div>
          <div class="radio-group">
            <span class="radio-pill" :class="{ on: quoteMode === 'preview' }" @click="quoteMode = 'preview'">仅侧边预览</span>
            <span class="radio-pill" :class="{ on: quoteMode === 'auto' }" @click="quoteMode = 'auto'">自动发送</span>
          </div>
        </div>
        <div class="set-row col">
          <div class="rl">
            <div class="rt">配件黑名单</div>
          </div>
          <div class="blk-tags">
            <span v-for="(p, i) in parts" :key="p" class="blk-tag" @click="removePart(i)">{{ p }} <i>×</i></span>
            <span v-if="!parts.length" class="rs">暂无黑名单配件</span>
          </div>
          <div class="blk-add">
            <input v-model="partInput" class="input" placeholder="输入配件名后回车加入" @keyup.enter="addPart">
            <button class="qq-btn-sm add-btn" @click="addPart">添加</button>
          </div>
        </div>
      </div>
    </div>

    <div class="set-sec">
      <div class="sh">价格系数</div>
      <div class="sb">
        <table class="map-table">
          <thead>
            <tr><th>客户等级</th><th>系数</th></tr>
          </thead>
          <tbody>
            <tr v-for="r in RATE_LABELS" :key="r.key">
              <td>{{ r.label }}</td>
              <td><input v-model="rates[r.key]" class="input rate" type="number" min="0" max="1" step="0.01"></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="set-sec disabled" title="待后端支持">
      <div class="sh">报价话术模板 <span class="qq-badge b-gray">待后端支持</span></div>
      <div class="sb">
        <div class="tpl-grid">
          <div v-for="t in TPLS" :key="t.key" class="tpl-card" :class="{ on: tpl === t.key }" @click="tpl = t.key">
            <div class="tn">{{ t.name }}</div>
            <div class="tp">{{ t.text }}</div>
          </div>
        </div>
        <div class="tpl-preview">{{ TPLS.find((t) => t.key === tpl).text }}</div>
        <div class="rs" style="margin-top: 4px;">默认一版，模板选择与动态新增待后端存储支持</div>
      </div>
    </div>

    <div class="set-sec disabled" title="待后端支持">
      <div class="sh">通知配置 <span class="qq-badge b-gray">待后端支持</span></div>
      <div class="sb">
        <div v-for="n in NOTIFS" :key="n.key" class="set-row notif">
          <div class="rl">
            <div class="rt">{{ n.title }}</div>
            <div class="rs">{{ n.desc }}</div>
          </div>
          <input class="input th-input num" :value="n.th" disabled>
          <label class="qq-switch sw">
            <input type="checkbox" :checked="n.on" disabled>
            <span class="track"></span>
          </label>
        </div>
      </div>
    </div>

    <button class="save-btn" :disabled="saving" @click="onSave">保存设置</button>
  </div>
</template>

<style scoped>
.view { display: flex; flex-direction: column; }

/* 分区：白卡浮起，标题带红色竖条（车车安乘配卡片标题语言） */
.set-sec {
  background: var(--c-panel);
  border: 1px solid var(--c-border);
  border-radius: var(--r-lg);
  margin-bottom: 10px; overflow: hidden;
  box-shadow: 0 2px 8px rgba(31, 45, 61, 0.05);
}
.set-sec .sh {
  padding: 9px 11px;
  border-bottom: 1px solid var(--c-border);
  font-weight: 700;
  font-size: 12px;
  display: flex; align-items: center; gap: 6px;
}
.set-sec .sh::before {
  content: ''; width: 3px; height: 12px; flex: none;
  border-radius: 2px; background: var(--c-primary);
}
.set-sec .sb { padding: 11px; }
.set-sec.disabled { opacity: 0.72; }

.set-row { display: flex; align-items: center; gap: 8px; padding: 6px 0; }
.set-row + .set-row { border-top: 1px dashed var(--c-border); }
.set-row.col { flex-direction: column; align-items: stretch; }
.set-row.notif { padding: 7px 0; }
.set-row .rl { flex: 1; min-width: 0; }
.set-row .rt { font-size: 12px; }
.set-row .rs { font-size: 10px; color: var(--c-text-sub); margin-top: 1px; }

/* 模式选择：pill 组 */
.radio-group { display: flex; gap: 6px; }
.radio-pill {
  font-size: 11px; padding: 4px 11px;
  border-radius: 999px;
  border: 1px solid var(--c-border-strong);
  color: var(--c-text-sub); cursor: pointer; user-select: none;
  transition: all 0.15s;
}
.radio-pill.on { border-color: var(--c-primary); color: var(--c-primary); background: var(--c-primary-soft); font-weight: 600; }

.blk-tags { display: flex; gap: 5px; flex-wrap: wrap; margin-top: 6px; }
.blk-tag {
  display: inline-flex; align-items: center; gap: 5px;
  font-size: 11px; padding: 3px 9px;
  background: var(--c-danger-soft);
  border: 1px solid rgba(229, 72, 77, 0.3);
  border-radius: 999px; color: var(--c-danger); cursor: pointer;
}
.blk-tag i { font-style: normal; opacity: 0.6; font-family: var(--f-num); }
.blk-tag:hover i { opacity: 1; }
.blk-add { display: flex; gap: 6px; margin-top: 7px; }
.blk-add .input { flex: 1; padding: 5px 8px; font-size: 11px; }

.input {
  padding: 7px 10px; font-size: 12px;
  border: 1px solid var(--c-border-strong); border-radius: var(--r-md);
  background: var(--c-panel); color: var(--c-text); outline: none; font-family: inherit;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.input:focus { border-color: var(--c-primary); box-shadow: 0 0 0 3px rgba(232, 32, 22, 0.1); }
.input.rate { width: 80px; padding: 4px 8px; font-size: 11px; font-family: var(--f-num); }
.th-input { width: 74px; padding: 4px 6px; font-size: 11px; font-family: var(--f-num); }

/* 表单行「添加」按钮：比公共 .qq-btn-sm 更高（配合表单输入框） */
.add-btn { padding: 5px 10px; }

.map-table { width: 100%; border-collapse: collapse; font-size: 11px; }
.map-table th { text-align: left; color: var(--c-text-sub); font-weight: 600; padding: 4px 6px; background: var(--c-bg); border-radius: 4px; }
.map-table td { padding: 5px 6px; border-bottom: 1px dashed var(--c-border); }

.tpl-grid { display: flex; gap: 6px; flex-wrap: wrap; }
.tpl-card {
  flex: 1 1 44%;
  border: 1px solid var(--c-border-strong); border-radius: var(--r-md);
  padding: 8px; cursor: pointer; background: var(--c-panel); transition: all 0.15s;
}
.tpl-card:hover { border-color: var(--c-primary); }
.tpl-card.on { border-color: var(--c-primary); background: var(--c-primary-soft); }
.tpl-card .tn { font-weight: 700; font-size: 12px; margin-bottom: 3px; }
.tpl-card .tp {
  font-size: 10px; color: var(--c-text-sub);
  overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
}
.tpl-preview {
  margin-top: 8px;
  background: var(--c-bg); border-radius: var(--r-sm);
  padding: 8px 10px; font-size: 11px; white-space: pre-wrap;
  border: 1px dashed var(--c-border-strong);
}

.save-btn {
  font-size: 13px; font-weight: 600; padding: 9px 0;
  border: 1px solid var(--c-primary-deep); border-radius: var(--r-md);
  background: var(--c-primary); color: #fff; cursor: pointer;
  box-shadow: 0 2px 8px rgba(232, 32, 22, 0.28);
  transition: background 0.15s, transform 0.15s, box-shadow 0.15s;
}
.save-btn:hover:not(:disabled) { background: var(--c-primary-deep); transform: translateY(-1px); }
.save-btn:active:not(:disabled) { transform: translateY(0); }
.save-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
