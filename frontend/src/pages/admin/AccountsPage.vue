<script setup>
/** 账号管理：列表/搜索/新增/编辑（设备关联从设备库勾选）/启停用/重置密码。 */
import { computed, onMounted, ref } from 'vue'
import DevicePicker from '../../components/DevicePicker.vue'
import {
  createAccount,
  fetchAccounts,
  fetchAdminDevices,
  fetchOrgs,
  resetAccountPassword,
  toggleAccountStatus,
  updateAccount,
} from '../../api'
import { matchName } from '../../utils/format'

const props = defineProps({
  me: { type: Object, required: true },
})
const toast = defineEmits(['toast'])

const list = ref([])
const keyword = ref('')
const loading = ref(true)

const ROLE_TEXT = { developer: '开发者', admin: '管理员', agent: '客服' }
const ROLE_CLASS = { developer: 'role-developer', admin: 'role-admin', agent: 'role-agent' }

const isSelf = (u) => u.id === props.me.id
const devLocked = (u) => props.me.role === 'admin' && u.role === 'developer'
const canBind = props.me.role === 'developer'

const filtered = computed(() =>
  list.value.filter((u) => matchName([u.username, u.name, u.initials], u.pinyin_toks, keyword.value)))

async function load() {
  loading.value = true
  try {
    list.value = await fetchAccounts()
  } catch (ex) {
    toast('toast', { msg: ex.message || '加载失败', type: 'danger' })
  }
  loading.value = false
}

/* ===== 组织与设备字典：组织必选归属；设备关联从设备库勾选（多对多、可跨组织） ===== */
const orgs = ref([])
const devices = ref([])  // 设备字典（含 bound_users，供选择器显示占用）
async function loadDicts() {
  try {
    const [orgList, deviceList] = await Promise.all([fetchOrgs(), fetchAdminDevices()])
    orgs.value = orgList
    devices.value = deviceList
  } catch { /* 字典拉不到时表单下拉为空，保存时后端兜底校验 */ }
}
onMounted(() => { load(); loadDicts() })

/* ===== 启停用 ===== */
async function onToggle(u) {
  if (isSelf(u) || devLocked(u)) return
  const next = u.status === 1 ? 0 : 1
  try {
    await toggleAccountStatus(u.id, next)
    u.status = next
    toast('toast', { msg: `${next === 1 ? '已启用' : '已停用'} ${u.username}` })
  } catch (ex) {
    toast('toast', { msg: ex.message || '操作失败', type: 'danger' })
  }
}

/* ===== 重置密码 ===== */
async function onReset(u) {
  if (!window.confirm(`确认将 ${u.username}（${u.name}）的密码重置为初始密码 123456？`)) return
  try {
    await resetAccountPassword(u.id)
    toast('toast', { msg: `已重置 ${u.username} 的密码为 123456` })
  } catch (ex) {
    toast('toast', { msg: ex.message || '操作失败', type: 'danger' })
  }
}

/* ===== 新增 / 编辑弹窗（同一弹窗：editingId 为空即新增；设备关联从设备库勾选，device_ids 整体替换） ===== */
const modalOpen = ref(false)
const editingId = ref(null)
const editingUser = ref(null)  // 编辑行快照：admin 不可改关联，只读展示现有绑定用
const form = ref({ username: '', name: '', role: 'agent', org_id: null, device_ids: [] })
const formErr = ref('')
const saving = ref(false)
const roleOptions = computed(() =>
  props.me.role === 'developer'
    ? [['developer', '开发者'], ['admin', '管理员'], ['agent', '客服']]
    : [['admin', '管理员'], ['agent', '客服']]
)
const needOrg = (role) => role !== 'developer'  // 开发者跨组织，其余必选

function openModal(u) {
  editingId.value = u ? u.id : null
  editingUser.value = u || null
  form.value = u
    ? { username: u.username, name: u.name, role: u.role, org_id: u.org_id ?? null,
        device_ids: [...(u.device_ids || (u.devices || []).map((d) => d.id))] }
    : { username: '', name: '', role: 'agent', org_id: null, device_ids: [] }
  formErr.value = ''
  modalOpen.value = true
}

async function save() {
  const f = form.value
  if (!f.name.trim() || (!editingId.value && !f.username.trim())) {
    formErr.value = editingId.value ? '请填写姓名' : '请填写登录账号与姓名'
    return
  }
  if (needOrg(f.role) && !f.org_id) { formErr.value = '请选择所属组织'; return }
  saving.value = true
  try {
    if (editingId.value) {
      const payload = { name: f.name.trim(), org_id: f.org_id }
      if (canBind) payload.device_ids = [...f.device_ids] // 空数组=解绑全部；admin 不带字段=不动关联
      await updateAccount(editingId.value, payload)
      toast('toast', { msg: '已保存账号修改' })
    } else {
      const payload = {
        username: f.username.trim(),
        name: f.name.trim(),
        role: f.role,
        org_id: f.org_id,
      }
      if (canBind) payload.device_ids = [...f.device_ids]
      await createAccount(payload)
      toast('toast', { msg: `已新增账号 ${f.username.trim()}，初始密码 123456` })
    }
    modalOpen.value = false
    await load()
  } catch (ex) {
    formErr.value = ex.message || '保存失败，请重试'
  }
  saving.value = false
}
</script>

<template>
  <div>
    <div class="page-head rise">
      <div>
        <h1>账号管理</h1>
        <div class="desc">账号的新增、编辑、启停用与微信设备绑定
          <template v-if="me.role === 'admin'">
            <span class="tag tag-warn" style="margin-left:8px;">管理员不可修改开发者账号</span>
            <span class="tag tag-warn" style="margin-left:8px;">微信设备绑定仅开发者可配置</span>
          </template>
        </div>
      </div>
      <div class="page-actions">
        <button class="btn btn-primary" @click="openModal(null)">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 21a8 8 0 0 1 13.292-6"/><circle cx="10" cy="8" r="5"/><path d="M19 16v6"/><path d="M22 19h-6"/></svg>
          新增账号
        </button>
      </div>
    </div>

    <div class="card rise rise-1" style="display:flex;align-items:center;gap:8px;padding:10px 14px;margin-bottom:10px;">
      <div class="search">
        <span class="ic"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg></span>
        <input v-model="keyword" type="text" placeholder="搜索账号 / 姓名">
      </div>
    </div>

    <div class="card rise rise-2">
      <div class="tbl-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th>登录账号</th>
              <th>成员</th>
              <th>角色</th>
              <th>所属组织</th>
              <th>微信绑定</th>
              <th>状态</th>
              <th>最近登录</th>
              <th style="text-align:right;">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading">
              <td v-for="i in 8" :key="i"><div class="skeleton" style="width:96px;height:12px"></div></td>
            </tr>
            <tr v-else-if="!filtered.length">
              <td colspan="8"><div class="empty"><span>没有符合条件的账号</span></div></td>
            </tr>
            <tr v-for="u in filtered" v-else :key="u.id">
              <td>
                <div class="cell-main num">{{ u.username }}</div>
                <div class="cell-sub num">创建于 {{ u.created_at }}</div>
              </td>
              <td>
                <div style="display:flex;align-items:center;gap:8px;">
                  <span class="avatar sm">{{ u.name.slice(0, 1) }}</span>
                  <span class="cell-main">{{ u.name }}</span>
                </div>
              </td>
              <td><span class="tag" :class="ROLE_CLASS[u.role]">{{ ROLE_TEXT[u.role] }}</span></td>
              <td>
                <span v-if="u.org_name" class="tag tag-blue">{{ u.org_name }}</span>
                <span v-else class="tag tag-gray" :title="u.role === 'developer' ? '开发者账号跨组织' : '存量账号未分配，编辑时可补选'">
                  {{ u.role === 'developer' ? '跨组织' : '未分配' }}
                </span>
              </td>
              <td>
                <div v-if="u.devices?.length" class="bind-chips"
                     :title="u.devices.map((d) => `${d.org_name || '未分配'} · ${d.name || d.openid}`).join('、')">
                  <span v-for="d in u.devices.slice(0, 2)" :key="d.id" class="bind-chip">{{ d.name || d.openid }}</span>
                  <span v-if="u.devices.length > 2" class="bind-chip more">+{{ u.devices.length - 2 }}</span>
                  <span class="cell-sub">共 {{ u.devices.length }} 台</span>
                </div>
                <span v-else class="tag tag-gray" title="未绑定设备，登录工作台看不到任何会话">未绑定</span>
              </td>
              <td>
                <div style="display:flex;align-items:center;gap:8px;">
                  <button type="button" class="switch" :class="{ on: u.status === 1 }"
                          :disabled="isSelf(u) || devLocked(u)"
                          :title="isSelf(u) ? '不能停用当前登录账号' : devLocked(u) ? '管理员无权操作开发者账号' : (u.status === 1 ? '点击停用该账号' : '点击启用该账号')"
                          @click="onToggle(u)"></button>
                  <span class="tag" :class="u.status === 1 ? 'tag-ok' : 'tag-gray'">{{ u.status === 1 ? '启用' : '停用' }}</span>
                </div>
              </td>
              <td class="num">{{ u.last_login_at || '从未登录' }}</td>
              <td>
                <div class="ops">
                  <button type="button" class="icon-btn" :disabled="devLocked(u)"
                          :title="devLocked(u) ? '管理员无权操作开发者账号' : '编辑姓名与微信设备绑定'" @click="openModal(u)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.828 2.828 0 1 1 4 4L7 21l-4 1 1-4L17 3z"/></svg>
                  </button>
                  <button type="button" class="icon-btn" :disabled="devLocked(u)"
                          :title="devLocked(u) ? '管理员无权操作开发者账号' : '重置为初始密码 123456'" @click="onReset(u)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2.586 17.414A2 2 0 0 0 2 18.828V21a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h.172a2 2 0 0 0 1.414-.586l.814-.814a6.5 6.5 0 1 0-4-4z"/><circle cx="16.5" cy="7.5" r=".5" fill="currentColor"/></svg>
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 新增 / 编辑账号弹窗（editingId 为空即新增） -->
    <div class="modal-mask" :class="{ show: modalOpen }" @click.self="modalOpen = false">
      <div class="modal">
        <div class="modal-head">
          <h3>{{ editingId ? '编辑账号' : '新增账号' }}</h3>
          <button type="button" class="icon-btn" aria-label="关闭" @click="modalOpen = false">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
          </button>
        </div>
        <div class="modal-body">
          <div class="field">
            <label>登录账号</label>
            <input v-model="form.username" class="input" type="text" :disabled="!!editingId" placeholder="如：cs10">
          </div>
          <div class="field">
            <label>姓名</label>
            <input v-model="form.name" class="input" type="text" placeholder="成员真实姓名">
          </div>
          <div v-if="!editingId" class="field">
            <label>角色</label>
            <select v-model="form.role" class="select">
              <option v-for="[v, t] in roleOptions" :key="v" :value="v">{{ t }}</option>
            </select>
          </div>
          <div class="field">
            <label>所属组织{{ needOrg(form.role) ? '' : '（可选）' }}</label>
            <select v-model="form.org_id" class="select">
              <option :value="null" :disabled="!editingId">{{ needOrg(form.role) ? '请选择组织' : '不绑组织（跨组织）' }}</option>
              <option v-for="o in orgs" :key="o.id" :value="o.id">{{ o.name }}</option>
            </select>
          </div>
          <div class="field">
            <label>关联设备{{ editingId ? '（可多台，全部移除=解绑）' : '（可选，可多台）' }}</label>
            <DevicePicker v-if="canBind" v-model="form.device_ids" :devices="devices" :orgs="orgs" />
            <template v-else>
              <div v-if="editingUser?.devices?.length" class="bind-chips">
                <span v-for="d in editingUser.devices" :key="d.id" class="bind-chip"
                      :title="`${d.org_name || '未分配'} · ${d.name || d.openid}`">{{ d.name || d.openid }}</span>
              </div>
              <span class="tag tag-gray">微信设备绑定仅开发者可配置{{ editingId ? '，管理员只能修改姓名' : '' }}</span>
            </template>
          </div>
          <span v-if="!editingId" class="tag tag-gray">初始密码统一为 123456，请通知成员尽快修改</span>
          <span v-else-if="canBind" class="tag tag-gray">绑定后该账号在工作台只看到这些设备的会话与好友</span>
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
