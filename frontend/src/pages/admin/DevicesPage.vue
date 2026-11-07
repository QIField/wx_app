<script setup>
/** 设备管理：设备字典（openid 全局唯一、录入后不可改）/ 统计 / 筛选 / 新增 / 编辑 / 删除。
 * developer/admin 可查看；新增/编辑/删除仅 developer（与账号绑定同口径）。 */
import { computed, onMounted, ref } from 'vue'
import {
  createAdminDevice,
  deleteAdminDevice,
  fetchAdminDevices,
  fetchOrgs,
  restoreAdminDevice,
  updateAdminDevice,
} from '../../api'
import { matchKeyword } from '../../utils/format'

const props = defineProps({
  me: { type: Object, required: true },
})
const emit = defineEmits(['toast'])

const canManage = props.me.role === 'developer'

const list = ref([])
const orgs = ref([])
const loading = ref(true)

const ONLINE_TEXT = { 1: '在线', 0: '离线', '-1': '未知' }
const ONLINE_CLS = { 1: 'on', 0: 'off', '-1': 'unknown' }

const orgFilter = ref('')
const onlineFilter = ref('')
const keyword = ref('')
const trashMode = ref(false) // 回收站：只看软删除设备，可恢复

/** 在用设备（统计口径始终排除已删除，避免回收站数据污染看板）。 */
const activeList = computed(() => list.value.filter((d) => !d.deleted_at))

const filtered = computed(() =>
  list.value.filter((d) => {
    if (trashMode.value ? !d.deleted_at : !!d.deleted_at) return false
    if (orgFilter.value && d.org_id !== Number(orgFilter.value)) return false
    if (onlineFilter.value && String(d.online) !== onlineFilter.value) return false
    return matchKeyword(
      [d.openid, d.name, d.org_name, ...(d.bound_users || []).flatMap((u) => [u.name, u.username])],
      keyword.value,
    )
  }))

const stats = computed(() => {
  const rows = activeList.value
  return {
    total: rows.length,
    on: rows.filter((d) => d.online === 1).length,
    off: rows.filter((d) => d.online === 0).length,
    free: rows.filter((d) => !(d.bound_users || []).length).length,
  }
})

async function load() {
  loading.value = true
  try {
    const [devices, orgList] = await Promise.all([
      fetchAdminDevices(trashMode.value ? { include_deleted: 1 } : undefined),
      fetchOrgs(),
    ])
    list.value = devices
    orgs.value = orgList
  } catch (ex) {
    emit('toast', { msg: ex.message || '加载失败', type: 'danger' })
  }
  loading.value = false
}
onMounted(load)

/** 切换在用 / 回收站：后端默认只返回未删除，回收站需 include_deleted=1。 */
async function toggleTrash() {
  trashMode.value = !trashMode.value
  await load()
}

/* ===== 关联账号 chips ===== */
const boundUsers = (d) => d.bound_users || []
const isCrossOrg = (d) => boundUsers(d).some((u) => u.org_id !== d.org_id)

/* ===== 新增 / 编辑（同一弹窗：editingId 为空即新增） ===== */
const modalOpen = ref(false)
const editingId = ref(null)
const form = ref({ openid: '', name: '', org_id: null })
const formErr = ref('')
const saving = ref(false)

function openModal(d) {
  editingId.value = d ? d.id : null
  form.value = d
    ? { openid: d.openid, name: d.name, org_id: d.org_id }
    : { openid: '', name: '', org_id: null }
  formErr.value = ''
  modalOpen.value = true
}

async function save() {
  const f = form.value
  if (!editingId.value && !f.openid.trim()) { formErr.value = '请填写设备 ID'; return }
  if (!f.name.trim()) { formErr.value = '请填写设备名称'; return }
  if (!f.org_id) { formErr.value = '请选择所属组织'; return }
  saving.value = true
  try {
    if (editingId.value) {
      await updateAdminDevice(editingId.value, { name: f.name.trim(), org_id: f.org_id })
      emit('toast', { msg: `已保存设备「${f.name.trim()}」` })
    } else {
      await createAdminDevice({ openid: f.openid.trim(), name: f.name.trim(), org_id: f.org_id })
      emit('toast', { msg: `已新增设备「${f.name.trim()}」，可到账号管理中关联` })
    }
    modalOpen.value = false
    await load()
  } catch (ex) {
    formErr.value = ex.message || '保存失败，请重试'
  }
  saving.value = false
}

async function remove(d) {
  if (boundUsers(d).length) {
    emit('toast', { msg: `「${d.name || d.openid}」仍被 ${boundUsers(d).length} 个账号关联，请先解除关联`, type: 'danger' })
    return
  }
  if (!window.confirm(`确认删除设备「${d.name || d.openid}」（${d.openid}）？\n删除后进入回收站，可随时恢复。`)) return
  try {
    await deleteAdminDevice(d.id)
    emit('toast', { msg: `已删除设备「${d.name || d.openid}」，可在回收站恢复` })
    await load()
  } catch (ex) {
    emit('toast', { msg: ex.message || '删除失败', type: 'danger' })
  }
}

/** 从回收站恢复：只把 deleted_at 置回 NULL，原 id 与关联保持不变。 */
async function restore(d) {
  try {
    await restoreAdminDevice(d.id)
    emit('toast', { msg: `已恢复设备「${d.name || d.openid}」` })
    await load()
  } catch (ex) {
    emit('toast', { msg: ex.message || '恢复失败', type: 'danger' })
  }
}
</script>

<template>
  <div>
    <div class="page-head rise">
      <div>
        <h1>设备管理</h1>
        <div class="desc">微信设备先入库，再到账号管理中关联给账号；删除为软删除，可在回收站恢复
          <span v-if="!canManage" class="tag tag-warn" style="margin-left:8px;">设备增删改仅开发者可操作</span>
        </div>
      </div>
      <div v-if="canManage" class="page-actions">
        <button class="btn btn-primary" @click="openModal(null)">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="20" x="5" y="2" rx="2" ry="2"/><path d="M12 18h.01"/></svg>
          新增设备
        </button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stat-grid rise rise-1">
      <div class="card stat-card">
        <div class="stat-top"><span>设备总数</span></div>
        <div class="stat-val">{{ stats.total }}</div>
        <div class="stat-foot">openid 全局唯一</div>
      </div>
      <div class="card stat-card">
        <div class="stat-top"><span>在线</span></div>
        <div class="stat-val">{{ stats.on }}</div>
        <div class="stat-foot">按在线检测回写</div>
      </div>
      <div class="card stat-card">
        <div class="stat-top"><span>离线</span></div>
        <div class="stat-val">{{ stats.off }}</div>
        <div class="stat-foot">不再推送消息</div>
      </div>
      <div class="card stat-card">
        <div class="stat-top"><span>未关联</span></div>
        <div class="stat-val">{{ stats.free }}</div>
        <div class="stat-foot">尚未关联任何账号</div>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="card rise rise-2" style="display:flex;align-items:center;gap:8px;padding:10px 14px;margin-bottom:10px;">
      <select v-model="orgFilter" class="select" style="width:140px;">
        <option value="">全部组织</option>
        <option v-for="o in orgs" :key="o.id" :value="o.id">{{ o.name }}</option>
      </select>
      <select v-model="onlineFilter" class="select" style="width:120px;">
        <option value="">全部状态</option>
        <option value="1">在线</option>
        <option value="0">离线</option>
        <option value="-1">未知</option>
      </select>
      <div class="search">
        <span class="ic"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg></span>
        <input v-model="keyword" type="text" placeholder="搜索设备 ID / 名称 / 关联账号">
      </div>
      <span style="flex:1"></span>
      <button type="button" class="btn" :class="trashMode ? 'btn-primary' : 'btn-ghost'" @click="toggleTrash">
        <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
        {{ trashMode ? '返回在用设备' : '回收站' }}
      </button>
    </div>

    <!-- 设备列表 -->
    <div class="card rise rise-3">
      <div class="tbl-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th>设备 ID</th>
              <th>设备名称</th>
              <th>所属组织</th>
              <th>在线状态</th>
              <th>关联账号</th>
              <th>创建时间</th>
              <th style="text-align:right;">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading">
              <td v-for="i in 7" :key="i"><div class="skeleton" style="width:96px;height:12px"></div></td>
            </tr>
            <tr v-else-if="!filtered.length">
              <td colspan="7"><div class="empty"><span>没有符合条件的设备</span></div></td>
            </tr>
            <tr v-for="d in filtered" v-else :key="d.id">
              <td>
                <div class="cell-main num">{{ d.openid }}</div>
                <div class="cell-sub num">ID #{{ d.id }}</div>
              </td>
              <td><div class="cell-main">{{ d.name || '—' }}</div></td>
              <td>
                <span v-if="d.org_name" class="tag tag-blue">{{ d.org_name }}</span>
                <span v-else class="tag tag-gray" title="迁移遗留未分配，编辑时可补选">未分配</span>
              </td>
              <td>
                <template v-if="d.deleted_at">
                  <span class="tag tag-gray">已删除</span>
                  <div class="cell-sub num" style="margin-top:4px;">{{ d.deleted_at }}</div>
                </template>
                <div v-else style="display:flex;align-items:center;gap:6px;">
                  <span class="online-dot" :class="ONLINE_CLS[d.online]"></span>
                  <span>{{ ONLINE_TEXT[d.online] }}</span>
                </div>
              </td>
              <td>
                <div v-if="boundUsers(d).length" class="bind-chips">
                  <span v-for="u in boundUsers(d).slice(0, 2)" :key="u.id" class="bind-chip"
                        :title="`${u.org_name || '未分配'} · ${u.name}（${u.username}）`">{{ u.name }}</span>
                  <span v-if="boundUsers(d).length > 2" class="bind-chip more">+{{ boundUsers(d).length - 2 }}</span>
                  <span class="cell-sub">共 {{ boundUsers(d).length }} 个账号关联</span>
                </div>
                <span v-else class="tag tag-gray" title="尚未被任何账号关联">未关联</span>
                <span v-if="isCrossOrg(d)" class="tag tag-warn" style="margin-left:4px;"
                      title="存在与设备归属不同组织的关联账号">跨组织</span>
              </td>
              <td class="num">{{ d.created_at }}</td>
              <td>
                <div class="ops" style="justify-content:flex-end;">
                  <template v-if="canManage && d.deleted_at">
                    <button type="button" class="icon-btn" title="恢复设备（deleted_at 置回 NULL）" @click="restore(d)">
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>
                    </button>
                  </template>
                  <template v-else-if="canManage">
                    <button type="button" class="icon-btn" title="编辑设备名称与所属组织" @click="openModal(d)">
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.828 2.828 0 1 1 4 4L7 21l-4 1 1-4L17 3z"/></svg>
                    </button>
                    <button type="button" class="icon-btn" title="删除设备（软删除，可在回收站恢复；被关联时不可删除）" @click="remove(d)">
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg>
                    </button>
                  </template>
                  <span v-else class="cell-sub">仅查看</span>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 新增 / 编辑设备弹窗 -->
    <div class="modal-mask" :class="{ show: modalOpen }" @click.self="modalOpen = false">
      <div class="modal">
        <div class="modal-head">
          <h3>{{ editingId ? '编辑设备' : '新增设备' }}</h3>
          <button type="button" class="icon-btn" aria-label="关闭" @click="modalOpen = false">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
          </button>
        </div>
        <div class="modal-body">
          <div class="field">
            <label>设备 ID（openid）</label>
            <input v-model="form.openid" class="input num" type="text" :disabled="!!editingId"
                   :placeholder="editingId ? '录入后不可修改' : '中间方设备标识，如 wxid_xxx'"
                   maxlength="64">
            <div v-if="editingId" class="cell-sub" style="margin-top:4px;">设备 ID 录入后不可修改</div>
          </div>
          <div class="field">
            <label>设备名称</label>
            <input v-model="form.name" class="input" type="text" placeholder="如：佛山一部-01" maxlength="64">
          </div>
          <div class="field">
            <label>所属组织</label>
            <select v-model="form.org_id" class="select">
              <option :value="null" disabled>请选择组织</option>
              <option v-for="o in orgs" :key="o.id" :value="o.id">{{ o.name }}</option>
            </select>
          </div>
          <span class="tag tag-gray">新增后可到账号管理中把设备关联给账号，一个设备可关联多个账号</span>
          <div class="form-err" :class="{ show: formErr }">
            <span>{{ formErr }}</span>
          </div>
        </div>
        <div class="modal-foot">
          <button type="button" class="btn btn-ghost" @click="modalOpen = false">取消</button>
          <button type="button" class="btn btn-primary" :class="{ loading: saving }" :disabled="saving" @click="save">保存</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 在线状态圆点：绿在线 / 灰离线 / 黄未知 */
.online-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.online-dot.on { background: var(--c-ok); box-shadow: 0 0 0 3px rgba(24, 160, 88, 0.15); }
.online-dot.off { background: var(--c-border-strong); }
.online-dot.unknown { background: var(--c-warn); box-shadow: 0 0 0 3px rgba(240, 130, 30, 0.15); }
</style>
