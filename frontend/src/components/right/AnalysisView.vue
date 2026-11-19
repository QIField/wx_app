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

/** 每列双柱（报价 / OE；VIN 仅进 KPI 不出柱），共用报价系列的最大值归一。 */
const cols = computed(() => {
  const d = data.value
  if (!d) return []
  return d.days.map((label, i) => {
    const quote = (d.series.quote && d.series.quote[i]) || 0
    const oe = (d.series.oe && d.series.oe[i]) || 0
    return {
      label,
      showLabel: period.value === 'month' ? i % 2 === 0 : i % 3 === 0,
      quote: barPercent(quote, seriesMax.value),
      oe: barPercent(oe, seriesMax.value),
      quoteVal: quote,
      oeVal: oe,
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

    <div v-if="error" class="qq-empty err">{{ error }}</div>

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
        <div v-else class="qq-empty">该时段暂无询价记录</div>
      </div>
    </template>
    <div v-else class="qq-empty">统计加载中…</div>
  </div>
</template>

<style scoped>
/* 日/月报切换：分段 pill 组 */
.ana-toggle {
  display: inline-flex; gap: 3px;
  padding: 3px;
  background: var(--c-bg);
  border-radius: 999px;
  margin-bottom: 10px;
}
.tg {
  padding: 5px 16px; font-size: 12px; color: var(--c-text-sub);
  border-radius: 999px; cursor: pointer; user-select: none;
  transition: all 0.15s;
}
.tg:hover { color: var(--c-primary); }
.tg.on {
  background: linear-gradient(145deg, #f2594e, var(--c-primary));
  color: #fff; font-weight: 600;
  box-shadow: 0 2px 6px rgba(232, 32, 22, 0.28);
}

/* KPI：车车安乘配统计卡语言——白卡浮起 + 品牌红大数字 */
.kpis { display: flex; gap: 8px; margin-bottom: 10px; }
.kpi {
  flex: 1; min-width: 0; text-align: center;
  background: var(--c-panel); border: 1px solid var(--c-border);
  border-radius: var(--r-lg); padding: 10px 4px;
  box-shadow: 0 2px 8px rgba(31, 45, 61, 0.05);
}
.kpi .kl { font-size: 10px; color: var(--c-text-sub); }
.kpi .kv { font: 700 20px/1.2 var(--f-num); color: var(--c-primary); margin: 3px 0 4px; }
.kpi .kt { font-size: 10px; color: var(--c-text-sub); }
.kpi .kt.up { color: var(--c-ok); }
.kpi .kt.down { color: var(--c-danger); }

/* 趋势/TOP 卡片 */
.panel {
  background: var(--c-panel); border: 1px solid var(--c-border);
  border-radius: var(--r-lg);
  padding: 11px; margin-bottom: 10px;
  box-shadow: 0 2px 8px rgba(31, 45, 61, 0.05);
}
.ph {
  font-weight: 700; font-size: 12px; margin-bottom: 8px;
  display: flex; align-items: center; gap: 6px;
}
.ph::before {
  content: ''; width: 3px; height: 12px; flex: none;
  border-radius: 2px; background: var(--c-primary);
}
.ph .sub { font: 10px var(--f-num); color: var(--c-text-sub); font-weight: 400; }

.legend { display: flex; gap: 10px; margin-bottom: 6px; }
.lg { font-size: 10px; color: var(--c-text-sub); display: inline-flex; align-items: center; gap: 4px; }
.lg .dot { width: 8px; height: 8px; border-radius: 3px; }
.lg .dot.q { background: var(--c-primary); }
.lg .dot.o { background: #5588f1; }

/* 双柱：报价=品牌红渐变，OE=车车安乘配图标蓝 */
.barchart { display: flex; align-items: flex-end; gap: 2px; height: 120px; padding-top: 4px; border-bottom: 1px solid var(--c-border); }
.col { flex: 1; min-width: 0; height: 100%; display: flex; flex-direction: column; }
.bars { flex: 1; display: flex; align-items: flex-end; justify-content: center; gap: 1px; }
.bar { width: 38%; max-width: 12px; border-radius: 3px 3px 0 0; transition: height 0.25s ease; }
.bar.q { background: linear-gradient(180deg, #f2594e, var(--c-primary)); }
.bar.o { background: linear-gradient(180deg, #7ba4f5, #5588f1); }
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
  border-radius: 6px; background: var(--c-bg); color: var(--c-text-sub);
  font: 700 11px/18px var(--f-num); text-align: center;
}
.rank-list .no.top { background: var(--c-primary); color: #fff; }
.rank-list .nm { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rank-list .oe { font: 11px var(--f-num); color: var(--c-text-sub); }
.rank-list .ct { font: 700 12px var(--f-num); color: var(--c-danger); }
</style>
