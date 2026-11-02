<script setup>
/** 总览页：四个指标卡 + 最新操作（日志仅开发者可见）。 */
import { onMounted, ref } from 'vue'
import { fetchAdminStats, fetchAuditLogs } from '../../api'

const props = defineProps({
  me: { type: Object, required: true },
})

const stats = ref(null)
const logs = ref([])
const isDev = props.me.role === 'developer'

onMounted(async () => {
  try {
    stats.value = await fetchAdminStats()
  } catch { /* 接口失败显示占位 */ }
  if (isDev) {
    try {
      logs.value = (await fetchAuditLogs()).list.slice(0, 6)
    } catch { /* 忽略 */ }
  }
})

function successText(v) {
  return v === null || v === undefined ? '—' : `${v}%`
}
</script>

<template>
  <div>
    <div class="page-head rise">
      <div>
        <h1>总览</h1>
        <div class="desc">系统运行概况与关键指标</div>
      </div>
    </div>

    <div class="stat-grid rise rise-1">
      <div class="card stat-card">
        <div class="stat-top"><span>今日消息量</span>
          <span class="ic"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/></svg></span>
        </div>
        <div class="stat-val num">{{ stats ? stats.msg_today : '—' }}<small>条</small></div>
        <div class="stat-foot"><span>收发合计，含群聊</span></div>
      </div>
      <div class="card stat-card">
        <div class="stat-top"><span>客服账号</span>
          <span class="ic"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg></span>
        </div>
        <div class="stat-val num">{{ stats ? stats.agents_on : '—' }}<small>/ {{ stats ? stats.agents_total : '—' }} 启用</small></div>
        <div class="stat-foot"><span>启用账号才会同步设备消息</span></div>
      </div>
      <div class="card stat-card">
        <div class="stat-top"><span>今日新增客户</span>
          <span class="ic"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 21a8 8 0 0 1 13.292-6"/><circle cx="10" cy="8" r="5"/><path d="M19 16v6"/><path d="M22 19h-6"/></svg></span>
        </div>
        <div class="stat-val num">{{ stats ? stats.new_customers : '—' }}<small>人</small></div>
        <div class="stat-foot"><span>新建立的会话数</span></div>
      </div>
      <div class="card stat-card">
        <div class="stat-top"><span>发送成功率</span>
          <span class="ic"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m22 7-8.991 5.727a2 2 0 0 1-2.009 0L2 7"/><rect x="2" y="4" width="20" height="16" rx="2"/></svg></span>
        </div>
        <div class="stat-val num">{{ stats ? successText(stats.success_rate) : '—' }}</div>
        <div class="stat-foot"><span>已确认结果的发送任务</span></div>
      </div>
    </div>

    <div v-if="isDev" class="card rise rise-2">
      <div class="card-head">
        <div class="card-title">
          <span class="ic"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/></svg></span>
          最新操作
        </div>
      </div>
      <div class="card-body">
        <div v-if="!logs.length" class="empty"><span>暂无操作记录</span></div>
        <div v-for="l in logs" :key="l.id" class="mini-log">
          <span class="m-time num">{{ l.created_at }}</span>
          <div class="m-body">
            <b>{{ l.operator_name }}</b><span v-if="l.org_name" class="tag tag-blue" style="margin:0 4px;">{{ l.org_name }}</span> {{ l.action }} · {{ l.target }}
            <span :class="l.result === 'fail' ? 'tag-danger' : 'tag-gray'" class="tag" style="margin-left:6px;">{{ l.result === 'fail' ? '失败' : '成功' }}</span>
            <div v-if="l.detail" style="color:var(--c-text-sub);">{{ l.detail }}</div>
          </div>
        </div>
      </div>
    </div>
    <div v-else class="card rise rise-2">
      <div class="card-body">
        <div class="empty"><span>操作日志仅开发者可见</span></div>
      </div>
    </div>
  </div>
</template>
