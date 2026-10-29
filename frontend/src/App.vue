<script setup>
/** 三栏工作台：顶栏 + 会话列表 / 聊天窗 / 资料栏。 */
import { onMounted } from 'vue'
import { useChatStore } from './stores/chat'
import ConvList from './components/ConvList.vue'
import ChatPanel from './components/ChatPanel.vue'
import InfoPanel from './components/InfoPanel.vue'

const chat = useChatStore()

onMounted(async () => {
  await chat.loadConversations()
  chat.connect()
})
</script>

<template>
  <div class="frame">
    <header class="topbar">
      <div class="brand">
        <span class="logo">微</span>
        <div class="brand-text">
          <span class="name">微信客服工作台</span>
          <span class="env">开发环境 · 演示数据</span>
        </div>
      </div>
      <div class="status">
        <span class="dot"></span>设备在线
      </div>
    </header>

    <div class="layout">
      <aside class="col-side"><ConvList /></aside>
      <main class="col-main"><ChatPanel /></main>
      <aside class="col-info"><InfoPanel /></aside>
    </div>
  </div>
</template>

<style scoped>
.frame {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--c-bg);
}

.topbar {
  height: 56px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background: var(--c-panel);
  border-bottom: 1px solid var(--c-border);
}
.brand { display: flex; align-items: center; gap: 10px; }
.logo {
  width: 32px; height: 32px;
  border-radius: var(--r-sm);
  background: var(--c-primary);
  color: #fff; font-size: 16px; font-weight: 600;
  display: flex; align-items: center; justify-content: center;
}
.brand-text { display: flex; flex-direction: column; line-height: 1.2; }
.name { font-weight: 600; }
.env { font-size: 11px; color: var(--c-text-sub); }

.status {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; color: var(--c-text-sub);
}
.dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: #22c55e;
}

.layout {
  flex: 1;
  display: flex;
  gap: 10px;
  padding: 10px;
  min-height: 0;
}
.col-side {
  width: 300px;
  background: var(--c-panel);
  border-radius: var(--r-lg);
  overflow: hidden;
  flex-shrink: 0;
}
.col-main {
  flex: 1;
  background: var(--c-panel);
  border-radius: var(--r-lg);
  overflow: hidden;
  min-width: 0;
}
.col-info {
  width: 320px;
  background: var(--c-panel);
  border-radius: var(--r-lg);
  overflow: hidden;
  flex-shrink: 0;
}
</style>
