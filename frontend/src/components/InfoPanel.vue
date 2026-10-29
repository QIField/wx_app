<script setup>
/** 右栏：报价处理台（本期为静态演示数据，后端接口后续接入，数据结构与 quote_order/quote_item 对齐）。 */
import { computed, ref } from 'vue'

const TABS = [
  { key: 'pending', label: '待处理' },
  { key: 'quoted', label: '已报价' },
  { key: 'done', label: '已购' },
]

/* 演示数据：对标报价单卡片（群名/联系方式/车辆信息/进度），非真实接口 */
const QUOTES = [
  { id: 1, status: 'pending', group: '鑫铃自动报价群', contact: '佛山鑫铃 139****9515(测试)', time: '15:30:36', urgent: true,
    car: '一汽大众 A4L(中国-2009-15) 2011 2.0L C0ZA-涡轮增压 汽油 CVT 无级变速箱 (LVSJCB2B6S2555553)', done: 1, total: 3 },
  { id: 2, status: 'pending', group: '泉州鑫铃-奔驰超豪', contact: '泉州鑫铃 138****6652', time: '15:26:41', urgent: false,
    car: '奔驰 Super Hao Raul(2009-2015)超豪 2012 1.8L CEAA-涡轮增压 汽油 6速自动变速箱 (LSVCR3BT2B6750555)', done: 0, total: 1 },
  { id: 3, status: 'pending', group: '鑫铃自动报价群', contact: '佛山鑫铃 139****9515(测试)', time: '15:02:26', urgent: false,
    car: '进口奥迪 A6L Avant(2019-2025) 3.0L DLZA 7速双离合变速箱 (WAURGFCF20LN00955)', done: 1, total: 3 },
  { id: 4, status: 'quoted', group: '鑫铃自动报价群', contact: '佛山鑫铃 139****9515(测试)', time: '14:47:58', urgent: false,
    car: '进口大众 途锐(2011-2014) 2014款 3.0L CRCA-机械增压 汽油 8速自动变速箱 (WVGAY97PZED039956)', done: 1, total: 2 },
  { id: 5, status: 'quoted', group: '广州鑫铃-奔驰超豪', contact: '广州鑫铃 136****0027', time: '11:32:19', urgent: false,
    car: '本田 2014 (JHMC63FORTU2045) 2.4L K24W5-自然吸气 汽油 CVT 无级变速箱', done: 2, total: 2 },
  { id: 6, status: 'done', group: '厦门鑫铃', contact: '厦门鑫铃 135****8890', time: '10:14:59', urgent: false,
    car: '东风悦达起亚 Q2(2010-2015)Q2 2015 3.0L CJTC 8速自动变速箱 (WAAEAD3GF0D001479)', done: 1, total: 1 },
]

const active = ref('pending')
const list = computed(() => QUOTES.filter(q => q.status === active.value))
const count = key => QUOTES.filter(q => q.status === key).length
</script>

<template>
  <div class="desk">
    <div class="tabs">
      <span class="tab on">报价</span>
      <span class="tab dim">聊天管理</span>
      <span class="tab dim">客户画像</span>
    </div>

    <div class="filter-row">
      <div class="status-tabs">
        <span
          v-for="t in TABS" :key="t.key"
          class="st" :class="{ on: active === t.key }"
          @click="active = t.key"
        >{{ t.label }} <em class="num">{{ count(t.key) }}</em></span>
      </div>
      <span class="lang">语别:全部</span>
    </div>

    <el-scrollbar class="scroll">
      <div class="cards">
        <div
          v-for="(q, i) in list"
          :key="q.id"
          class="card"
          :class="{ urgent: q.urgent }"
          :style="{ animationDelay: i * 45 + 'ms' }"
        >
          <div class="row-top">
            <span class="group">{{ q.group }}</span>
            <span class="contact">{{ q.contact }}</span>
          </div>
          <div class="car">{{ q.car }}</div>
          <div class="row-bottom">
            <span class="time num">{{ q.time }}</span>
            <span class="progress">
              <em class="num" :class="{ zero: q.done === 0 }">{{ q.done }}/{{ q.total }}</em>
              <span class="links"><a>查全部</a><i>|</i><a>车型报价</a></span>
            </span>
          </div>
        </div>
      </div>
      <div class="footnote">演示数据 · 后端接口后续接入</div>
    </el-scrollbar>
  </div>
</template>

<style scoped>
.desk { display: flex; flex-direction: column; height: 100%; }

.tabs {
  display: flex; gap: 2px; padding: 8px 10px 0;
  border-bottom: 1px solid var(--c-border);
}
.tab {
  padding: 6px 10px; font-size: 13px; cursor: pointer;
  border-radius: var(--r-sm) var(--r-sm) 0 0;
}
.tab.on {
  font-weight: 600; color: var(--c-primary);
  background: var(--c-primary-soft);
  box-shadow: inset 0 2px 0 var(--c-primary);
}
.tab.dim { color: var(--c-text-sub); }
.tab.dim:hover { color: var(--c-text); }

.filter-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 7px 10px;
  border-bottom: 1px solid var(--c-border);
  background: #fafbfd;
}
.status-tabs { display: flex; gap: 4px; }
.st {
  font-size: 12px; color: var(--c-text-sub);
  padding: 3px 9px; border-radius: 3px; cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.15s;
}
.st:hover { color: var(--c-text); }
.st.on {
  color: var(--c-primary); font-weight: 600;
  background: var(--c-primary-soft);
  border-color: #b9d0ff;
}
.st em { font-style: normal; font-size: 11px; opacity: 0.75; margin-left: 1px; }
.lang { font-size: 11px; color: var(--c-text-sub); }

.scroll { flex: 1; }
.cards { padding: 4px 10px; }

.card {
  padding: 8px 10px;
  border-bottom: 1px dashed var(--c-border-strong);
  position: relative;
  animation: card-in 0.3s both;
  transition: background 0.15s;
}
@keyframes card-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: none; }
}
.card::before {
  content: '';
  position: absolute; left: -2px; top: 10px; bottom: 10px; width: 3px;
  background: var(--c-primary);
  border-radius: 2px;
  opacity: 0;
  transition: opacity 0.15s;
}
.card:hover { background: #f8fafd; }
.card:hover::before { opacity: 1; }
.card.urgent::after {
  content: '急';
  position: absolute; right: 8px; top: 7px;
  font-size: 10px; color: #fff; background: var(--c-danger);
  border-radius: 3px; padding: 0 4px; line-height: 15px;
}

.row-top { display: flex; justify-content: space-between; gap: 8px; align-items: baseline; }
.group { font-weight: 600; font-size: 13px; }
.contact {
  font-size: 11px; color: var(--c-text-sub);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

.car {
  margin: 5px 0;
  padding: 5px 7px;
  font-size: 12px; line-height: 1.5;
  color: var(--c-primary-deep);
  background: var(--c-primary-soft);
  border-radius: var(--r-sm);
  border-left: 3px solid var(--c-primary);
}

.row-bottom { display: flex; justify-content: space-between; align-items: center; }
.time { font-size: 11px; color: var(--c-text-sub); }
.progress { display: flex; align-items: center; gap: 8px; }
.progress em { font-style: normal; font-weight: 700; font-size: 13px; color: var(--c-primary); }
.progress em.zero { color: var(--c-warn); }
.links { display: flex; align-items: center; gap: 5px; font-size: 11px; }
.links a { color: var(--c-primary); cursor: pointer; }
.links a:hover { text-decoration: underline; }
.links i { color: var(--c-border-strong); font-style: normal; }

.footnote {
  text-align: center; font-size: 10px; color: var(--c-border-strong);
  padding: 8px 0 10px;
}
</style>
