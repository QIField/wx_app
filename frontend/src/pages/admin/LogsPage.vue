<script setup>
/** 操作日志：仅开发者可见。关键词搜索 + 全量列表（新→旧，上限 500 条）。 */
import { onMounted, ref } from 'vue'
import { fetchAuditLogs } from '../../api'

const emit = defineEmits(['toast'])

const list = ref([])
const keyword = ref('')
const loading = ref(true)

const ROLE_TEXT = { developer: '开发者', admin: '管理员', agent: '客服', system: '系统' }

async function load() {
  loading.value = true
  try {
    list.value = (await fetchAuditLogs(keyword.value.trim() || undefined)).list
  } catch (ex) {
    emit('toast', { msg: ex.message || '加载失败', type: 'danger' })
  }
  loading.value = false
}
onMounted(load)
</script>

<template>
  <div>
    <div class="page-head rise">
      <div>
        <h1>操作日志</h1>
        <div class="desc">谁、在什么时候、对什么、做了什么、结果如何 · 只保留 180 天</div>
      </div>
      <div class="page-actions">
        <div class="search">
          <span class="ic"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg></span>
          <input v-model="keyword" type="text" placeholder="搜索 操作人 / 动作 / 对象" @keydown.enter="load">
        </div>
        <button class="btn btn-ghost" @click="load">查询</button>
      </div>
    </div>

    <div class="card rise rise-1">
      <div class="tbl-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th>时间</th>
              <th>操作人</th>
              <th>模块</th>
              <th>动作</th>
              <th>对象</th>
              <th>结果</th>
              <th>详情 / IP</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading">
              <td v-for="i in 7" :key="i"><div class="skeleton" style="width:110px;height:12px"></div></td>
            </tr>
            <tr v-else-if="!list.length">
              <td colspan="7"><div class="empty"><span>暂无操作记录</span></div></td>
            </tr>
            <tr v-for="l in list" v-else :key="l.id">
              <td class="num" style="white-space:nowrap;">{{ l.created_at }}</td>
              <td>
                <div class="cell-main">{{ l.operator_name }}</div>
                <div class="cell-sub">{{ ROLE_TEXT[l.role] || l.role }}</div>
              </td>
              <td><span class="tag tag-gray">{{ l.module }}</span></td>
              <td class="cell-main">{{ l.action }}</td>
              <td class="num">{{ l.target }}</td>
              <td>
                <span class="tag" :class="l.result === 'fail' ? 'tag-danger' : 'tag-ok'">
                  {{ l.result === 'fail' ? '失败' : '成功' }}
                </span>
              </td>
              <td>
                <div class="cell-sub">{{ l.detail }}</div>
                <div class="cell-sub num">{{ l.ip }}</div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
