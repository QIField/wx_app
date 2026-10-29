<script setup>
/** 三栏工作台：深色顶栏 + 会话列表 / 聊天窗 / 报价处理台。 */
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
          <span class="sub num">WX-DESK v0.1</span>
        </div>
      </div>
      <div class="right">
        <span class="env-chip">演示数据</span>
        <span class="status"><span class="dot"></span>设备在线</span>
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
  height: 46px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 14px;
  background: linear-gradient(90deg, var(--c-navy), var(--c-navy-2));
  color: #fff;
}
.brand { display: flex; align-items: center; gap: 9px; }
.logo {
  width: 26px; height: 26px;
  border-radius: var(--r-sm);
  background: var(--c-primary);
  color: #fff; font-size: 13px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
  box-shadow: inset 0 -6px 12px rgba(0, 0, 0, 0.18);
}
.brand-text { display: flex; flex-direction: column; line-height: 1.15; }
.name { font-size: 13px; font-weight: 600; letter-spacing: 1px; }
.sub { font-size: 10px; color: rgba(255, 255, 255, 0.55); }
.right { display: flex; align-items: center; gap: 12px; }
.env-chip {
  font-size: 11px; color: #ffd8a8;
  border: 1px solid rgba(240, 130, 30, 0.55);
  background: rgba(240, 130, 30, 0.14);
  border-radius: 3px; padding: 1px 7px;
}
.status { display: flex; align-items: center; gap: 5px; font-size: 12px; color: rgba(255, 255, 255, 0.8); }
.dot { width: 7px; height: 7px; border-radius: 50%; background: #35d07f; box-shadow: 0 0 6px #35d07f; }

.layout {
  flex: 1;
  display: flex;
  gap: 8px;
  padding: 8px;
  min-height: 0;
}
.col-side {
  width: 264px;
  background: var(--c-panel);
  border-radius: var(--r-md);
  box-shadow: var(--shadow-card);
  overflow: hidden;
  flex-shrink: 0;
}
.col-main {
  flex: 1;
  background: var(--c-panel);
  border-radius: var(--r-md);
  box-shadow: var(--shadow-card);
  overflow: hidden;
  min-width: 0;
}
.col-info {
  width: 316px;
  background: var(--c-panel);
  border-radius: var(--r-md);
  box-shadow: var(--shadow-card);
  overflow: hidden;
  flex-shrink: 0;
}
</style>
