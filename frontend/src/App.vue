<script setup>
/** 三栏工作台：深色顶栏 + 会话列表/通讯录（切换）/ 聊天窗 / 报价处理台（可收起、可拖宽）。 */
import { onMounted, ref } from 'vue'
import { useChatStore } from './stores/chat'
import ConvList from './components/ConvList.vue'
import ContactsPanel from './components/ContactsPanel.vue'
import ChatPanel from './components/ChatPanel.vue'
import ContactDetail from './components/ContactDetail.vue'
import InfoPanel from './components/InfoPanel.vue'

const chat = useChatStore()

const activeView = ref('chat') // chat | contacts

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
      <aside class="col-side">
        <div class="view-tabs">
          <button :class="{ on: activeView === 'chat' }" @click="activeView = 'chat'">会话</button>
          <button :class="{ on: activeView === 'contacts' }" @click="activeView = 'contacts'">通讯录</button>
        </div>
        <div class="view-body">
          <ConvList v-if="activeView === 'chat'" />
          <ContactsPanel v-else />
        </div>
      </aside>
      <main class="col-main">
        <ChatPanel v-if="activeView === 'chat'" />
        <ContactDetail v-else @enter-chat="activeView = 'chat'" />
      </main>
      <aside v-if="infoOpen" class="col-info" :style="{ width: infoW + 'px' }">
        <div class="info-resizer" title="拖拽调整宽度" @mousedown.prevent="onResizeDown"><i></i></div>
        <InfoPanel />
        <button class="info-toggle" title="收起扩展栏" @click="infoOpen = false">
          <svg viewBox="0 0 24 24" width="12" height="12">
            <path d="M9 6l6 6-6 6" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
      </aside>
      <button v-else class="info-toggle outside" title="展开扩展栏" @click="infoOpen = true">
        <svg viewBox="0 0 24 24" width="12" height="12">
          <path d="M15 6l-6 6 6 6" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
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
  display: flex;
  flex-direction: column;
}

/* 左栏顶部：会话 | 通讯录 切换 */
.view-tabs {
  display: flex;
  flex-shrink: 0;
  border-bottom: 1px solid var(--c-border);
}
.view-tabs button {
  flex: 1;
  padding: 9px 0;
  font-size: 13px;
  color: var(--c-text-sub);
  background: none;
  border: none;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: color 0.15s, border-color 0.15s;
}
.view-tabs button:hover { color: var(--c-text); }
.view-tabs button.on {
  color: var(--c-primary);
  font-weight: 600;
  border-bottom-color: var(--c-primary);
}
.view-body { flex: 1; min-height: 0; }

.col-main {
  flex: 1;
  background: var(--c-panel);
  border-radius: var(--r-md);
  box-shadow: var(--shadow-card);
  overflow: hidden;
  min-width: 0;
}
.col-info {
  position: relative;
  background: var(--c-panel);
  border-radius: var(--r-md);
  box-shadow: var(--shadow-card);
  overflow: visible;
  flex-shrink: 0;
  transition: width 0.12s ease-out;
}

/* 把手与按钮都嵌在右栏内部，不占外面空间 */
.info-resizer {
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 10px;
  z-index: 5;
  cursor: col-resize;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--r-md) 0 0 var(--r-md);
  transition: background 0.15s;
}
.info-resizer i {
  width: 3px; height: 28px;
  border-radius: 2px;
  background: var(--c-border-strong);
  transition: background 0.15s, height 0.15s;
}
.info-resizer:hover { background: #f0f4fb; }
.info-resizer:hover i { background: var(--c-primary); height: 44px; }

.info-toggle {
  position: absolute;
  right: 0; top: 50%;
  transform: translateY(-50%);
  width: 14px; height: 52px;
  z-index: 5;
  border: 1px solid var(--c-border);
  border-right: none;
  border-radius: var(--r-sm) 0 0 var(--r-sm);
  background: var(--c-panel);
  color: var(--c-text-sub);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  transition: all 0.15s;
}
.info-toggle:hover {
  color: var(--c-primary);
  border-color: var(--c-primary);
  background: var(--c-primary-soft);
}
.info-toggle.outside {
  position: static;
  transform: none;
  align-self: stretch;
  height: auto;
  width: 16px;
  border: 1px solid var(--c-border);
  border-radius: var(--r-sm);
  box-shadow: var(--shadow-card);
}
</style>
