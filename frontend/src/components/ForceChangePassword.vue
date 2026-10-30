<script setup>
/** 强制改密弹窗：初始密码账号登录后必须改密，不可关闭、不可绕过。 */
import { ref } from 'vue'
import { apiChangePassword } from '../api'

const emit = defineEmits(['done'])

const oldPwd = ref('')
const newPwd = ref('')
const confirmPwd = ref('')
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
  if (!oldPwd.value || !newPwd.value || !confirmPwd.value) {
    setErr('请填写完整'); return
  }
  if (newPwd.value.length < 6) {
    setErr('新密码至少 6 位'); return
  }
  if (newPwd.value !== confirmPwd.value) {
    setErr('两次输入的新密码不一致'); return
  }

  errMsg.value = ''
  loading.value = true
  try {
    const user = await apiChangePassword(oldPwd.value, newPwd.value)
    emit('done', user)
  } catch (ex) {
    setErr(ex.message || '修改失败，请重试')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="fcp-mask">
    <div class="fcp-card" :class="{ shake }">
      <div class="fcp-head">
        <span class="ic">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
        </span>
        <div>
          <h2>请先修改初始密码</h2>
          <p>为了账号安全，使用新密码前必须完成修改</p>
        </div>
      </div>

      <form class="fcp-form" novalidate @submit.prevent="submit">
        <div class="field">
          <label for="fcp-old">旧密码</label>
          <input id="fcp-old" v-model="oldPwd" class="input" type="password" placeholder="当前密码（初始密码 123456）" autocomplete="current-password">
        </div>
        <div class="field">
          <label for="fcp-new">新密码</label>
          <div class="input-group">
            <input id="fcp-new" v-model="newPwd" class="input" :type="showPwd ? 'text' : 'password'" placeholder="至少 6 位" autocomplete="new-password">
            <button type="button" class="icon-btn" aria-label="显示或隐藏密码" @click="showPwd = !showPwd">
              <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>
            </button>
          </div>
        </div>
        <div class="field">
          <label for="fcp-confirm">确认新密码</label>
          <input id="fcp-confirm" v-model="confirmPwd" class="input" :type="showPwd ? 'text' : 'password'" placeholder="再输入一次" autocomplete="new-password">
        </div>

        <div class="form-err" :class="{ show: errMsg }">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 20h16a2 2 0 0 0 1.73-2Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>
          <span>{{ errMsg }}</span>
        </div>

        <button class="btn btn-primary btn-block" type="submit" :class="{ loading }" :disabled="loading">确认修改</button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.fcp-mask {
  position: fixed;
  inset: 0;
  z-index: 300;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(20, 38, 77, 0.45);
  backdrop-filter: blur(2px);
}
.fcp-card {
  width: 360px;
  background: var(--c-panel);
  border-radius: var(--r-lg);
  box-shadow: var(--shadow-pop);
  padding: 22px 24px 20px;
}
.fcp-card.shake { animation: fcp-shake 0.36s; }
@keyframes fcp-shake {
  0%, 100% { transform: translateX(0); }
  25% { transform: translateX(-6px); }
  50% { transform: translateX(5px); }
  75% { transform: translateX(-3px); }
}
.fcp-head {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  margin-bottom: 16px;
}
.fcp-head .ic {
  width: 34px; height: 34px;
  flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  border-radius: var(--r-md);
  background: var(--c-warn-soft);
  color: var(--c-warn);
}
.fcp-head h2 { margin: 0; font-size: 15px; }
.fcp-head p { margin: 2px 0 0; font-size: 12px; color: var(--c-text-sub); }
.fcp-form { display: flex; flex-direction: column; gap: 12px; }
.input-group { position: relative; display: flex; }
.input-group .input { padding-right: 34px; height: 32px; }
.input-group .icon-btn {
  position: absolute; right: 3px; top: 3px;
  width: 26px; height: 26px;
}
.btn.loading { pointer-events: none; opacity: 0.8; }
.btn.loading::before {
  content: ''; width: 12px; height: 12px; flex-shrink: 0;
  border: 2px solid rgba(255, 255, 255, 0.45); border-top-color: #fff;
  border-radius: 50%; animation: fcp-spin 0.7s linear infinite;
}
@keyframes fcp-spin { to { transform: rotate(360deg); } }
</style>
