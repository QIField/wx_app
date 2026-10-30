<script setup>
/** 登录页：账号密码登录，按角色分流（developer/admin → 管理后台，agent → 工作台）。
    左侧品牌星图动画拆分在 BrandConstellation.vue（纯展示组件）。 */
import { ref } from 'vue'
import { apiLogin, setToken } from '../api'
import BrandConstellation from '../components/BrandConstellation.vue'
import BrandLogo from '../components/BrandLogo.vue'

const emit = defineEmits(['logged-in'])

const username = ref('')
const password = ref('')
const showPwd = ref(false)
const errMsg = ref('')
const shake = ref(false)
const loading = ref(false)

function setErr(msg) {
  errMsg.value = msg
  shake.value = false
  requestAnimationFrame(() => { shake.value = true })
}

async function submit() {
  const u = username.value.trim()
  const p = password.value
  if (!u || !p) { setErr('请输入账号和密码'); return }

  errMsg.value = ''
  loading.value = true
  try {
    const data = await apiLogin(u, p)
    setToken(data.token)
    emit('logged-in', data.user)
  } catch (ex) {
    setErr(ex.message || '登录失败，请重试')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-body">
    <div class="login-wrap">
      <!-- 左侧品牌区：脑图式关键词 -->
      <section class="login-brand">
        <div class="brand-row rise">
          <BrandLogo :size="46" />
          <div>
            <div class="big-name">SI客服系统</div>
            <div class="big-sub">SI · CUSTOMER SERVICE SYSTEM</div>
          </div>
        </div>

        <BrandConstellation class="rise rise-1" />

        <p class="tagline rise rise-2">一站式客服工作台 · 消息同步 · 会话协作 · 客户资料</p>

        <div class="login-meta rise rise-3">
          <span class="m-chip num">ENV · DEV</span>
        </div>
      </section>

      <!-- 右侧登录卡 -->
      <section class="login-card rise rise-2" :class="{ shake }">
        <div class="card-tag">
          <h2>登录</h2>
          <span class="latin">Sign in</span>
        </div>
        <p class="hint">使用管理员分配的账号登录，按角色进入对应工作台</p>

        <form class="login-form" novalidate @submit.prevent="submit">
          <div class="field">
            <label for="login-username">账号</label>
            <div class="input-group">
              <span class="ic"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg></span>
              <input id="login-username" v-model="username" class="input" type="text" placeholder="如：admin01" autocomplete="username">
            </div>
          </div>
          <div class="field">
            <label for="login-password">密码</label>
            <div class="input-group">
              <span class="ic"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2.586 17.414A2 2 0 0 0 2 18.828V21a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h.172a2 2 0 0 0 1.414-.586l.814-.814a6.5 6.5 0 1 0-4-4z"/><circle cx="16.5" cy="7.5" r=".5" fill="currentColor"/></svg></span>
              <input id="login-password" v-model="password" class="input" :type="showPwd ? 'text' : 'password'" placeholder="请输入密码" autocomplete="current-password">
              <button type="button" class="icon-btn eye-btn" aria-label="显示或隐藏密码" @click="showPwd = !showPwd">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>
              </button>
            </div>
          </div>

          <div class="form-err" :class="{ show: errMsg }">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 20h16a2 2 0 0 0 1.73-2Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>
            <span>{{ errMsg }}</span>
          </div>

          <button class="btn btn-primary btn-block" type="submit" :class="{ loading }" :disabled="loading">登 录</button>
        </form>

        <p class="login-foot num">首次使用请找开发者开通账号 · 初始密码 123456</p>
      </section>
    </div>
  </div>
</template>
