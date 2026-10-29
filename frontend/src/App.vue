<script setup>
/** 三栏工作台：深色顶栏 + 会话列表 / 聊天窗 / 报价处理台（可收起、可拖宽）。 */
import { onMounted, ref } from 'vue'
import { useChatStore } from './stores/chat'
import ConvList from './components/ConvList.vue'
import ChatPanel from './components/ChatPanel.vue'
import InfoPanel from './components/InfoPanel.vue'

const chat = useChatStore()

const infoOpen = ref(true)
const infoW = ref(316)

/* 左边缘拖拽调宽：向左拖=变宽（260~480px） */
let rz = null
function onResizeDown(e) {
  rz = { x: e.clientX, w: infoW.value }
  window.addEventListener('mousemove', onResizeMove)
  window.addEventListener('mouseup', onResizeUp)
}
function onResizeMove(e) {
  infoW.value = Math.min(480, Math.max(260, rz.w - (e.clientX - rz.x)))
}
function onResizeUp() {
  window.removeEventListener('mousemove', onResizeMove)
  window.removeEventListener('mouseup', onResizeUp)
  rz = null
}

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
      <div v-if="infoOpen" class="info-resizer" title="拖拽调整宽度" @mousedown.prevent="onResizeDown"></div>
      <aside v-if="infoOpen" class="col-info" :style="{ width: infoW + 'px' }"><InfoPanel /></aside>
      <button
        class="info-toggle"
        :title="infoOpen ? '收起扩展栏' : '展开扩展栏'"
        @click="infoOpen = !infoOpen"
      >
        <svg viewBox="0 0 24 24" width="12" height="12">
          <path v-if="infoOpen" d="M9 6l6 6-6 6" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
          <path v-else d="M15 6l-6 6 6 6" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </button>
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
  background: var(--c-panel);
  border-radius: var(--r-md);
  box-shadow: var(--shadow-card);
  overflow: hidden;
  flex-shrink: 0;
  transition: width 0.12s ease-out;
}

.info-resizer {
  width: 5px;
  flex-shrink: 0;
  cursor: col-resize;
  border-radius: 3px;
  transition: background 0.15s;
}
.info-resizer:hover { background: var(--c-primary); }

.info-toggle {
  width: 16px;
  flex-shrink: 0;
  border: 1px solid var(--c-border);
  border-radius: var(--r-sm);
  background: var(--c-panel);
  color: var(--c-text-sub);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}
.info-toggle:hover {
  color: var(--c-primary);
  border-color: var(--c-primary);
  background: var(--c-primary-soft);
}
</style>
