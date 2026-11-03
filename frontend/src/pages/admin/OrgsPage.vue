<script setup>
/** 组织管理：组织字典表格（含已删除）/ 新增 / 软删除 / 恢复。 */
import { onMounted, ref } from 'vue'
import { createOrg, fetchAllOrgs, updateOrgStatus } from '../../api'

const emit = defineEmits(['toast'])

const list = ref([])
const loading = ref(true)

async function load() {
  loading.value = true
  try {
    list.value = await fetchAllOrgs()
  } catch (ex) {
    emit('toast', { msg: ex.message || '加载失败', type: 'danger' })
  }
  loading.value = false
}
onMounted(load)

/* ===== 新增：回车或点按钮，重名由后端兜底拒绝 ===== */
const name = ref('')
const adding = ref(false)

async function onAdd() {
  const value = name.value.trim()
  if (!value) return
  adding.value = true
  try {
    await createOrg(value)
    emit('toast', { msg: `已新增组织 ${value}` })
    name.value = ''
    await load()
  } catch (ex) {
    emit('toast', { msg: ex.message || '操作失败', type: 'danger' })
  }
  adding.value = false
}

/* ===== 软删除 / 恢复：只改状态，行保留，历史归属不受影响 ===== */
async function onToggle(o) {
  const next = o.status === 1 ? 0 : 1
  if (next === 0 && !window.confirm(
    `确认删除组织「${o.name}」？\n删除后不再出现在各处下拉里，已绑定账号的历史归属仍保留该组织名，可随时恢复。`
  )) return
  try {
    await updateOrgStatus(o.id, next)
    o.status = next
    emit('toast', { msg: next === 1 ? `已恢复组织 ${o.name}` : `已删除组织 ${o.name}` })
  } catch (ex) {
    emit('toast', { msg: ex.message || '操作失败', type: 'danger' })
  }
}
</script>

<template>
  <div>
    <div class="page-head rise">
      <div>
        <h1>组织管理</h1>
      </div>
    </div>

    <div class="card rise rise-1" style="display:flex;align-items:center;gap:8px;padding:10px 14px;margin-bottom:10px;">
      <input v-model="name" class="input" style="width:220px;" type="text"
             placeholder="新组织名称，如：惠州" maxlength="64" @keyup.enter="onAdd">
      <button type="button" class="btn btn-primary" :disabled="adding || !name.trim()" @click="onAdd">+ 新增组织</button>
    </div>

    <div class="card rise rise-2">
      <div class="tbl-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th>组织名称</th>
              <th>状态</th>
              <th>创建时间</th>
              <th style="text-align:right;">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading">
              <td v-for="i in 4" :key="i"><div class="skeleton" style="width:96px;height:12px"></div></td>
            </tr>
            <tr v-else-if="!list.length">
              <td colspan="4"><div class="empty"><span>还没有组织，先在上方新增一个</span></div></td>
            </tr>
            <tr v-for="o in list" v-else :key="o.id">
              <td>
                <span class="tag" :class="o.status === 1 ? 'tag-blue' : 'tag-gray'"
                      :title="o.status === 1 ? '启用中，各处下拉可选' : '软删除：行保留，历史归属仍显示该组织名'">
                  {{ o.name }}
                </span>
              </td>
              <td><span class="tag" :class="o.status === 1 ? 'tag-ok' : 'tag-gray'">{{ o.status === 1 ? '启用' : '已删除' }}</span></td>
              <td class="num">{{ o.created_at || '—' }}</td>
              <td>
                <div class="ops" style="justify-content:flex-end;">
                  <button v-if="o.status === 1" type="button" class="icon-btn" title="删除（软删除，可恢复）" @click="onToggle(o)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg>
                  </button>
                  <button v-else type="button" class="icon-btn" title="恢复启用" @click="onToggle(o)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
