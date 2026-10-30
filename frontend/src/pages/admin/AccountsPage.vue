<script setup>
/** 账号管理：列表/搜索/新增/编辑（含微信设备绑定）/启停用/重置密码。 */
import { computed, onMounted, ref } from 'vue'
import {
  createAccount,
  fetchAccounts,
  resetAccountPassword,
  toggleAccountStatus,
  updateAccount,
} from '../../api'

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

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return list.value
  return list.value.filter(
    (u) => u.username.toLowerCase().includes(kw) || u.name.toLowerCase().includes(kw)
  )
})

async function load() {
  loading.value = true
  try {
    list.value = await fetchAccounts()
  } catch (ex) {
    toast('toast', { msg: ex.message || '加载失败', type: 'danger' })
  }
  loading.value = false
}
onMounted(load)

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

/* ===== 新增弹窗 ===== */
const addOpen = ref(false)
const addForm = ref({ username: '', name: '', role: 'agent', open_id: '' })
const addErr = ref('')
const addSaving = ref(false)
const roleOptions = computed(() =>
  props.me.role === 'developer'
    ? [['developer', '开发者'], ['admin', '管理员'], ['agent', '客服']]
    : [['admin', '管理员'], ['agent', '客服']]
)

function openAdd() {
  addForm.value = { username: '', name: '', role: 'agent', open_id: '' }
  addErr.value = ''
  addOpen.value = true
}

async function saveAdd() {
  const f = addForm.value
  if (!f.username.trim() || !f.name.trim()) { addErr.value = '请填写登录账号与姓名'; return }
  addSaving.value = true
  try {
    await createAccount({
      username: f.username.trim(),
      name: f.name.trim(),
      role: f.role,
      open_id: f.open_id.trim(),
    })
    toast('toast', { msg: `已新增账号 ${f.username.trim()}，初始密码 123456` })
    addOpen.value = false
    await load()
  } catch (ex) {
    addErr.value = ex.message || '保存失败，请重试'
  }
  addSaving.value = false
}

/* ===== 编辑弹窗 ===== */
const editOpen = ref(false)
const editForm = ref({ id: null, username: '', name: '', open_id: '' })
const editErr = ref('')
const editSaving = ref(false)

function openEdit(u) {
  editForm.value = { id: u.id, username: u.username, name: u.name, open_id: u.open_id || '' }
  editErr.value = ''
  editOpen.value = true
}

async function saveEdit() {
  const f = editForm.value
  if (!f.name.trim()) { editErr.value = '请填写姓名'; return }
  editSaving.value = true
  try {
    await updateAccount(f.id, { name: f.name.trim(), open_id: f.open_id.trim() })
    toast('toast', { msg: '已保存账号修改' })
    editOpen.value = false
    await load()
  } catch (ex) {
    editErr.value = ex.message || '保存失败，请重试'
  }
  editSaving.value = false
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
        <button class="btn btn-primary" @click="openAdd">
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
              <th>微信绑定</th>
              <th>状态</th>
              <th>最近登录</th>
              <th style="text-align:right;">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading">
              <td v-for="i in 7" :key="i"><div class="skeleton" style="width:96px;height:12px"></div></td>
            </tr>
            <tr v-else-if="!filtered.length">
              <td colspan="7"><div class="empty"><span>没有符合条件的账号</span></div></td>
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
                <span v-if="u.open_id" class="tag tag-ok" :title="u.open_id">已绑定</span>
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
                          :title="devLocked(u) ? '管理员无权操作开发者账号' : '编辑姓名与微信设备绑定'" @click="openEdit(u)">
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

    <!-- 新增账号弹窗 -->
    <div class="modal-mask" :class="{ show: addOpen }" @click.self="addOpen = false">
      <div class="modal">
        <div class="modal-head">
          <h3>新增账号</h3>
          <button type="button" class="icon-btn" aria-label="关闭" @click="addOpen = false">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
          </button>
        </div>
        <div class="modal-body">
          <div class="field">
            <label>登录账号</label>
            <input v-model="addForm.username" class="input" type="text" placeholder="如：cs10">
          </div>
          <div class="field">
            <label>姓名</label>
            <input v-model="addForm.name" class="input" type="text" placeholder="成员真实姓名">
          </div>
          <div class="field">
            <label>角色</label>
            <select v-model="addForm.role" class="select">
              <option v-for="[v, t] in roleOptions" :key="v" :value="v">{{ t }}</option>
            </select>
          </div>
          <div class="field">
            <label>微信设备 open_id（可选）</label>
            <input v-model="addForm.open_id" class="input" type="text" :disabled="!canBind"
                   :placeholder="canBind ? '中间方分配的设备标识，可创建后再绑定' : '仅开发者可配置微信设备绑定'">
          </div>
          <span class="tag tag-gray">初始密码统一为 123456，请通知成员尽快修改</span>
          <div class="form-err" :class="{ show: addErr }">
            <span>{{ addErr }}</span>
          </div>
        </div>
        <div class="modal-foot">
          <button type="button" class="btn btn-ghost" @click="addOpen = false">取消</button>
          <button type="button" class="btn btn-primary" :class="{ loading: addSaving }" :disabled="addSaving" @click="saveAdd">保存</button>
        </div>
      </div>
    </div>

    <!-- 编辑账号弹窗 -->
    <div class="modal-mask" :class="{ show: editOpen }" @click.self="editOpen = false">
      <div class="modal">
        <div class="modal-head">
          <h3>编辑账号</h3>
          <button type="button" class="icon-btn" aria-label="关闭" @click="editOpen = false">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
          </button>
        </div>
        <div class="modal-body">
          <div class="field">
            <label>登录账号</label>
            <input class="input" type="text" :value="editForm.username" disabled>
          </div>
          <div class="field">
            <label>姓名</label>
            <input v-model="editForm.name" class="input" type="text" placeholder="成员真实姓名">
          </div>
          <div class="field">
            <label>微信设备 open_id</label>
            <input v-model="editForm.open_id" class="input" type="text" :disabled="!canBind"
                   :placeholder="canBind ? '中间方分配的设备标识，留空解除绑定' : '仅开发者可配置'">
          </div>
          <span class="tag tag-gray">
            {{ canBind ? '绑定后该账号在工作台只看到此设备的会话与好友，留空则列表为空' : '微信设备绑定仅开发者可配置，管理员只能修改姓名' }}
          </span>
          <div class="form-err" :class="{ show: editErr }">
            <span>{{ editErr }}</span>
          </div>
        </div>
        <div class="modal-foot">
          <button type="button" class="btn btn-ghost" @click="editOpen = false">取消</button>
          <button type="button" class="btn btn-primary" :class="{ loading: editSaving }" :disabled="editSaving" @click="saveEdit">保存</button>
        </div>
      </div>
    </div>
  </div>
</template>
