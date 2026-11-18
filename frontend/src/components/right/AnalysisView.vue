<script setup>
/** 视图三：报价分析 —— 日报/月报切换，KPI + 趋势柱图 + TOP 询价配件。
 *
 * 数据：GET /quote/stats?period=day|month（真实聚合，绑定设备口径）。
 *   day=最近 15 天日桶、KPI=今日 vs 昨日；month=最近 10 周周桶、KPI=本月 vs 上月。
 * 柱图：报价次数与 OE 报价次数双柱并排（utils/quoteStats 纯函数换算柱高）。
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchQuoteStats } from '../../api'
import { barPercent, maxOf, trendBadge, trendPercent } from '../../utils/quoteStats'

const PERIODS = [
  { key: 'day', label: '日报' },
  { key: 'month', label: '月报' },
]

const period = ref('day')
const loading = ref(true)
const loaded = ref(false)
const error = ref('')
const data = ref(null)

const seriesMax = computed(() => maxOf((data.value && data.value.series && data.value.series.quote) || []))

const kpis = computed(() => {
  const d = data.value
  if (!d) return []
  return [
    { key: 'quote', label: '报价次数', cur: d.kpi.quote, pct: trendPercent(d.kpi.quote, d.prev.quote) },
    { key: 'oe', label: 'OE 报价次数', cur: d.kpi.oe, pct: trendPercent(d.kpi.oe, d.prev.oe) },
    { key: 'vin', label: 'VIN 解析次数', cur: d.kpi.vin, pct: trendPercent(d.kpi.vin, d.prev.vin) },
  ]
})

/** 每列双柱（报价 / OE），共用报价系列的最大值归一。 */
const cols = computed(() => {
  const d = data.value
  if (!d) return []
  return d.days.map((label, i) => {
    const quote = (d.series.quote && d.series.quote[i]) || 0
    const oe = (d.series.oe && d.series.oe[i]) || 0
    const vin = (d.series.vin && d.series.vin[i]) || 0
    return {
      label,
      showLabel: period.value === 'month' ? i % 2 === 0 : i % 3 === 0,
      quote: barPercent(quote, seriesMax.value),
      oe: barPercent(oe, seriesMax.value),
      vin: barPercent(vin, seriesMax.value),
      quoteVal: quote,
      oeVal: oe,
      vinVal: vin,
    }
  })
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await fetchQuoteStats(period.value)
    loaded.value = true
  } catch (e) {
    error.value = e.message || '统计加载失败'
  } finally {
    loading.value = false
  }
}

function switchPeriod(key) {
  period.value = key
  load()
}

onMounted(() => {
  load().catch(() => ElMessage.error('统计加载失败'))
})
</script>

<template>
  <div v-loading="loading" class="ana">
    <div class="ana-toggle">
      <span
        v-for="p in PERIODS" :key="p.key"
        class="tg" :class="{ on: period === p.key }"
        @click="switchPeriod(p.key)"
      >{{ p.label }}</span>
    </div>

    <div v-if="error" class="empty err">{{ error }}</div>

    <template v-else-if="loaded && data">
      <div class="kpis">
        <div v-for="k in kpis" :key="k.key" class="kpi">
          <div class="kl">{{ k.label }}</div>
          <div class="kv num">{{ k.cur }}</div>
          <div class="kt" :class="trendBadge(k.pct).cls">{{ trendBadge(k.pct).text }}</div>
        </div>
      </div>

      <div class="panel">
        <div class="ph">趋势 <span class="num sub">{{ data.period === 'day' ? '近 15 天' : '近 10 周' }}</span></div>
        <div class="legend">
          <span class="lg"><i class="dot q"></i>报价</span>
          <span class="lg"><i class="dot o"></i>OE 报价</span>
        </div>
        <div class="barchart">
          <div v-for="(c, i) in cols" :key="i" class="col" :title="`${c.label}：报价 ${c.quoteVal} / OE ${c.oeVal}`">
            <div class="bars">
              <div class="bar q" :style="{ height: c.quote + '%' }"></div>
              <div class="bar o" :style="{ height: c.oe + '%' }"></div>
            </div>
            <div class="lb" :class="{ hide: !c.showLabel }">{{ c.label }}</div>
          </div>
        </div>
      </div>

      <div class="panel">
        <div class="ph">TOP 询价配件</div>
        <ol v-if="data.top.length" class="rank-list">
          <li v-for="(t, i) in data.top" :key="i">
            <span class="no" :class="{ top: i < 3 }">{{ i + 1 }}</span>
            <span class="nm">{{ t.name }}</span>
            <span class="oe num">{{ t.oe }}</span>
            <span class="ct num">{{ t.ct }}</span>
          </li>
        </ol>
        <div v-else class="empty">该时段暂无询价记录</div>
      </div>
    </template>
    <div v-else class="empty">统计加载中…</div>
  </div>
</template>

<style scoped>
.ana-toggle {
  display: inline-flex; border: 1px solid var(--c-border-strong);
  border-radius: var(--r-md); overflow: hidden; margin-bottom: 10px;
}
.tg { padding: 5px 14px; font-size: 12px; color: var(--c-text-sub); cursor: pointer; background: var(--c-panel); }
.tg.on { background: var(--c-primary-soft); color: var(--c-primary); font-weight: 600; }

.kpis { display: flex; gap: 8px; margin-bottom: 10px; }
.kpi {
  flex: 1; text-align: center;
  background: var(--c-primary-soft); border: 1px solid #c7d8ff;
  border-radius: var(--r-md); padding: 9px 4px;
}
.kpi .kl { font-size: 10px; color: var(--c-primary-deep); }
.kpi .kv { font: 700 20px/1.2 var(--f-num); color: var(--c-primary); margin: 2px 0 3px; }
.kpi .kt { font-size: 10px; color: var(--c-text-sub); }
.kpi .kt.up { color: var(--c-ok); }
.kpi .kt.down { color: var(--c-danger); }

.panel {
  border: 1px solid var(--c-border); border-radius: var(--r-md);
  padding: 10px; margin-bottom: 10px;
}
.ph { font-weight: 700; font-size: 12px; margin-bottom: 8px; display: flex; align-items: center; gap: 6px; }
.ph .sub { font: 10px var(--f-num); color: var(--c-text-sub); font-weight: 400; }

.legend { display: flex; gap: 10px; margin-bottom: 6px; }
.lg { font-size: 10px; color: var(--c-text-sub); display: inline-flex; align-items: center; gap: 4px; }
.lg .dot { width: 8px; height: 8px; border-radius: 2px; }
.lg .dot.q { background: var(--c-primary); }
.lg .dot.o { background: #8b5cf6; }

.barchart { display: flex; align-items: flex-end; gap: 2px; height: 120px; padding-top: 4px; border-bottom: 1px solid var(--c-border); }
.col { flex: 1; min-width: 0; height: 100%; display: flex; flex-direction: column; }
.bars { flex: 1; display: flex; align-items: flex-end; justify-content: center; gap: 1px; }
.bar { width: 38%; max-width: 12px; border-radius: 2px 2px 0 0; transition: height 0.25s ease; }
.bar.q { background: var(--c-primary); }
.bar.o { background: #8b5cf6; }
.lb {
  flex: none; height: 16px;
  font: 9px/16px var(--f-num); color: var(--c-text-sub);
  text-align: center; white-space: nowrap; overflow: hidden;
}
.lb.hide { visibility: hidden; }

.rank-list { list-style: none; margin: 0; padding: 0; }
.rank-list li {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 2px; border-bottom: 1px dashed var(--c-border);
  font-size: 12px;
}
.rank-list li:last-child { border-bottom: none; }
.rank-list .no {
  flex: none; width: 18px; height: 18px;
  border-radius: var(--r-sm); background: var(--c-bg); color: var(--c-text-sub);
  font: 700 11px/18px var(--f-num); text-align: center;
}
.rank-list .no.top { background: var(--c-primary); color: #fff; }
.rank-list .nm { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rank-list .oe { font: 11px var(--f-num); color: var(--c-text-sub); }
.rank-list .ct { font: 700 12px var(--f-num); color: var(--c-danger); }

.empty { padding: 20px 10px; text-align: center; color: var(--c-text-sub); font-size: 11px; }
.empty.err { color: var(--c-danger); }
</style>
