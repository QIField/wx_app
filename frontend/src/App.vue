<script setup>
/** 应用入口：恢复会话 → 按角色分流（developer/admin → 管理后台，agent → 工作台）。 */
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { fetchMe, getToken, setToken } from './api'
import LoginPage from './pages/LoginPage.vue'
import WorkbenchPage from './pages/WorkbenchPage.vue'
import AdminLayout from './pages/AdminLayout.vue'
import DashboardPage from './pages/admin/DashboardPage.vue'
import AccountsPage from './pages/admin/AccountsPage.vue'
import LogsPage from './pages/admin/LogsPage.vue'
import ForceChangePassword from './components/ForceChangePassword.vue'

const booted = ref(false)
const me = ref(null)          // 当前登录人（/api/auth/me）
const view = ref('login')     // login | workbench | admin
const page = ref('dashboard') // 管理后台内页：dashboard | accounts | logs
const changingPwd = ref(false) // 初始密码账号的强制改密弹窗

const toasts = ref([])
let toastSeq = 0
function toast(msg, type = 'ok') {
  const id = ++toastSeq
  toasts.value.push({ id, msg, type })
  setTimeout(() => { toasts.value = toasts.value.filter((t) => t.id !== id) }, 2600)
}

// 任何业务接口被后端拦截（PASSWORD_CHANGE_REQUIRED）都会广播到这里弹窗
function onNeedChangePwd() { changingPwd.value = true }
onMounted(() => window.addEventListener('need-change-password', onNeedChangePwd))
onBeforeUnmount(() => window.removeEventListener('need-change-password', onNeedChangePwd))

onMounted(async () => {
  if (!getToken()) {
    view.value = 'login'
    booted.value = true
    return
  }
  try {
    me.value = await fetchMe()
    changingPwd.value = !!me.value.must_change_password
    view.value = me.value.role === 'agent' ? 'workbench' : 'admin'
  } catch {
    setToken('')
    me.value = null
    view.value = 'login'
  }
  booted.value = true
})

function onLoggedIn(user) {
  me.value = user
  changingPwd.value = !!user.must_change_password
  view.value = user.role === 'agent' ? 'workbench' : 'admin'
}

function onPwdChanged(user) {
  me.value = user
  changingPwd.value = false
  toast('密码修改成功')
}

function onLoggedOut() {
  setToken('')
  me.value = null
  changingPwd.value = false
  view.value = 'login'
}
</script>

<template>
  <LoginPage v-if="booted && view === 'login'" @logged-in="onLoggedIn" />

  <WorkbenchPage v-else-if="booted && view === 'workbench'" :me="me" @logout="onLoggedOut" @back="view = 'admin'" />

  <AdminLayout v-else-if="booted && view === 'admin'" v-model:page="page" :me="me" @logout="onLoggedOut" @open-workbench="view = 'workbench'">
    <DashboardPage v-if="page === 'dashboard'" :me="me" />
    <AccountsPage v-else-if="page === 'accounts'" :me="me" @toast="toast" />
    <LogsPage v-else-if="page === 'logs'" @toast="toast" />
  </AdminLayout>

  <div v-else class="boot-loading">加载中…</div>

  <!-- 初始密码强制改密：覆盖一切页面，不可关闭 -->
  <ForceChangePassword v-if="changingPwd" @done="onPwdChanged" />

  <!-- 轻提示 -->
  <div class="toast-box">
    <div v-for="t in toasts" :key="t.id" class="toast" :class="t.type">{{ t.msg }}</div>
  </div>
</template>

<style scoped>
.boot-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100vh;
  color: var(--c-text-sub);
  font-size: 13px;
}
</style>
