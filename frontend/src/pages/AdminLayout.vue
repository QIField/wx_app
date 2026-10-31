<script setup>
/** 管理后台框架：顶栏（品牌+用户）+ 侧栏导航（按角色显隐）+ 内容区。 */
import { computed } from 'vue'
import BrandLogo from '../components/BrandLogo.vue'

const props = defineProps({
  me: { type: Object, required: true },
})
const emit = defineEmits(['logout', 'open-workbench'])

const page = defineModel('page', { type: String, default: 'dashboard' })

const ROLE_TEXT = { developer: '开发者', admin: '管理员', agent: '客服' }

const navs = computed(() => {
  const items = [
    { key: 'dashboard', label: '总览', roles: ['developer', 'admin'], icon: 'grid' },
    { key: 'accounts', label: '账号管理', roles: ['developer', 'admin'], icon: 'users' },
    { key: 'logs', label: '操作日志', roles: ['developer'], icon: 'history' },
  ]
  return items.filter((n) => n.roles.includes(props.me.role))
})

const ICONS = {
  grid: 'M3 3h7v9H3zM14 3h7v5h-7zM14 12h7v9h-7zM3 16h7v5H3z',
  users: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M9 7a4 4 0 1 0 0 0.01 M22 21v-2a4 4 0 0 0-3-3.87 M16 3.13a4 4 0 0 1 0 7.75',
  history: 'M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8 M3 3v5h5 M12 7v5l4 2',
}
</script>

<template>
  <div class="frame admin-frame">
    <header class="topbar">
      <div class="brand">
        <BrandLogo />
        <div class="brand-text">
          <span class="name">SI客服系统</span>
          <span class="sub">SI ADMIN CONSOLE</span>
        </div>
      </div>
      <div class="right">
        <span class="env-chip num">DEV</span>
        <div class="user-chip">
          <div class="user-avatar num">{{ me.name.slice(0, 1) }}</div>
          <div class="user-meta">
            <span class="user-name">{{ me.name }}</span>
            <span class="user-role">{{ ROLE_TEXT[me.role] || me.role }}</span>
          </div>
          <button class="icon-btn" title="退出登录" aria-label="退出登录" @click="emit('logout')">
            <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/></svg>
          </button>
        </div>
      </div>
    </header>

    <div class="layout">
      <aside class="app-side">
        <nav class="app-nav">
          <div class="nav-label">管理后台</div>
          <a v-for="n in navs" :key="n.key" class="nav-item" :class="{ on: page === n.key }" href="javascript:void(0)" @click="page = n.key">
            <span class="ic"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path :d="ICONS[n.icon]" /></svg></span>
            <span class="nav-text">{{ n.label }}</span>
          </a>
          <div class="nav-label">快捷入口</div>
          <a class="nav-item" href="javascript:void(0)" title="进入消息工作台" @click="emit('open-workbench')">
            <span class="ic"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/><path d="M13 8H7"/><path d="M17 12H7"/></svg></span>
            <span class="nav-text">消息工作台</span>
          </a>
        </nav>
        <div class="nav-foot num">SI-WXCS v2.4.0</div>
      </aside>
      <main class="app-content">
        <slot />
      </main>
    </div>
  </div>
</template>
