<script setup>
/** 三栏工作台：深色顶栏 + 微信式图标侧栏（会话/通讯录）+ 列表 / 聊天窗 / 报价处理台。 */
import { nextTick, onMounted, onUnmounted, provide, ref, watch } from 'vue'
import { useChatStore } from '../stores/chat'
import { useContactsStore } from '../stores/contacts'
import { useBoundaryResize } from '../composables/useBoundaryResize'
import BrandLogo from '../components/BrandLogo.vue'
import ConvList from '../components/ConvList.vue'
import ContactsPanel from '../components/ContactsPanel.vue'
import ChatPanel from '../components/ChatPanel.vue'
import ContactDetail from '../components/ContactDetail.vue'
import DeviceCards from '../components/DeviceCards.vue'
import InfoColumn from '../components/InfoColumn.vue'
import UnreadBadge from '../components/UnreadBadge.vue'
import RingtoneSettings from '../components/RingtoneSettings.vue'
import HelpCenter from '../components/help/HelpCenter.vue'

const props = defineProps({
  me: { type: Object, required: true },
})
const emit = defineEmits(['logout', 'back'])

const chat = useChatStore()
const contacts = useContactsStore()

const ROLE_TEXT = { developer: '开发者', admin: '管理员', agent: '客服' }

const activeView = ref('chat') // chat | contacts | help
const convListRef = ref(null) // ConvList 实例：用于触发未读定位
const ringSettingsRef = ref(null) // 设置弹窗实例：左栏底部齿轮打开提示音选择
const chatPanelRef = ref(null) // ChatPanel 实例：暴露 locateMessage 方法给拓展栏的 QuoteCard
provide('chatPanelRef', chatPanelRef)

/* 左栏列表宽度：右缘 ±5px 悬停出拖拽光标，按住拖动实时调宽（220~420），松开持久化 */
const { width: listWidth, bind: bindListWidth } = useBoundaryResize({
  initial: 264,
  min: 220,
  max: 420,
  storageKey: 'wb.sideListWidth.v1',
})

/** rail 会话按钮：只有已经在消息列表页时才定位下一条未读；否则仅切换视图 */
function onChatRailClick() {
  if (activeView.value === 'chat') {
    convListRef.value?.locateUnread()
  } else {
    activeView.value = 'chat'
  }
}

onMounted(async () => {
  chat.operatorName = props.me.name // 本地气泡直接显示操作人
  await chat.loadDevices(true)      // 默认进第一个绑定的聊天账号
  await chat.loadConversations()
  chat.connect()
  chat.startDevicePolling()         // 顶栏卡片轮询重拉：展示后端在线状态回写结果
})
onUnmounted(() => chat.stopDevicePolling())

/* 切换聊天账号 → 通讯录跟着换设备重拉 */
watch(() => chat.activeOpenid, () => { contacts.load() })
</script>

<template>
  <div class="frame wb-frame">
    <header class="topbar">
      <div class="left">
        <div class="brand">
          <BrandLogo :size="26" />
          <div class="brand-text">
            <span class="name">SI客服系统</span>
            <span class="sub num">SI · MESSAGE WORKBENCH</span>
          </div>
        </div>
        <!-- 聊天账号卡片组：显示名 + 在线点 + 未读数，点击切换 -->
        <DeviceCards />
      </div>
      <div class="right">
        <button v-if="me.role !== 'agent'" class="icon-btn back-btn" title="返回管理后台" aria-label="返回管理后台" @click="emit('back')">
          <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 19-7-7 7-7"/><path d="M19 12H5"/></svg>
          <span>返回后台</span>
        </button>
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
      <!-- 左侧：rail 永远是 4 个按钮（会话/通讯录/帮助/设置），帮助+设置一起贴底 -->
      <div class="side-unit">
        <nav class="rail">
          <button class="rail-btn" :class="{ on: activeView === 'chat' }" title="会话（点击定位下一条未读并打开聊天窗）" @click="onChatRailClick">
            <svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z" />
            </svg>
            <UnreadBadge :count="chat.totalUnread" variant="rail" />
          </button>
          <button class="rail-btn" :class="{ on: activeView === 'contacts' }" title="通讯录" @click="activeView = 'contacts'">
            <svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" />
            </svg>
          </button>
          <div class="rail-bottom">
            <!-- 帮助中心入口 -->
            <button class="rail-btn" :class="{ on: activeView === 'help' }" title="帮助中心" aria-label="帮助中心" @click="activeView = 'help'">
              <svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/></svg>
            </button>
            <!-- 设置入口 -->
            <button class="rail-btn rail-settings" title="设置" aria-label="设置" @click="ringSettingsRef?.open()">
              <svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>
            </button>
          </div>
        </nav>
        <aside v-show="activeView !== 'help'" :ref="bindListWidth" class="col-side" :style="{ width: listWidth + 'px' }">
          <ConvList ref="convListRef" v-if="activeView === 'chat'" />
          <ContactsPanel v-else />
        </aside>
      </div>
      <main class="col-main">
        <ChatPanel v-if="activeView === 'chat'" ref="chatPanelRef" />
        <ContactDetail v-else-if="activeView === 'contacts'" @enter-chat="activeView = 'chat'" />
        <HelpCenter v-else />
      </main>
      <!-- 右侧扩展栏：帮助视图时隐藏 -->
      <InfoColumn v-if="activeView !== 'help'" />
    </div>

    <!-- 设置弹窗（提示音选择） -->
    <RingtoneSettings ref="ringSettingsRef" />
  </div>
</template>

<style scoped>
.frame {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--c-bg);
  /* 裁掉一切意外溢出：拓展栏收起后骑缝按钮会探出视口右缘 1px，
   * 不裁的话文档出现横向滚动条（Windows 浮动滚动条还会闪出黑色残影） */
  overflow: hidden;
}

/* 深海军蓝顶栏：斜向渐变打底 + 双层极光光晕反向漂移（纯 CSS，不挡交互） */
.topbar {
  position: relative;
  height: 46px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 14px;
  background: linear-gradient(92deg, #0e1c3d 0%, var(--c-navy) 34%, var(--c-navy-2) 72%, #234a92 100%);
  color: #fff;
  box-shadow: inset 0 -1px 0 rgba(255, 255, 255, 0.12); /* 底缘一道高光线 */
  overflow: hidden; /* 光晕层刻意超出发光（inset 为负），必须裁回顶栏内，否则盖住下方会话列表 */
}
/* 光晕层 A：品牌蓝 + 青（向右漂） */
.topbar::before,
.topbar::after {
  content: '';
  position: absolute;
  inset: -40% -6%;
  pointer-events: none;
  will-change: transform;
}
.topbar::before {
  background:
    radial-gradient(320px 190px at 7% 30%, rgba(29, 93, 228, 0.5), transparent 70%),
    radial-gradient(260px 170px at 40% 110%, rgba(34, 211, 238, 0.16), transparent 72%);
  animation: aurora-a 18s ease-in-out infinite alternate;
}
/* 光晕层 B：靛蓝 + 暖橙（向左漂，与 A 反向产生视差） */
.topbar::after {
  background:
    radial-gradient(280px 170px at 66% -30%, rgba(122, 162, 255, 0.3), transparent 70%),
    radial-gradient(220px 150px at 97% 115%, rgba(240, 130, 30, 0.2), transparent 72%);
  animation: aurora-b 24s ease-in-out infinite alternate;
}
@keyframes aurora-a {
  from { transform: translate3d(-16px, 0, 0) scale(1.02); }
  to { transform: translate3d(22px, 0, 0) scale(1.07); }
}
@keyframes aurora-b {
  from { transform: translate3d(20px, 0, 0) scale(1.05); }
  to { transform: translate3d(-18px, 0, 0) scale(1.02); }
}
@media (prefers-reduced-motion: reduce) {
  .topbar::before, .topbar::after { animation: none; }
}
/* 顶栏内容抬到光晕之上 */
.topbar .left, .topbar .right { position: relative; z-index: 1; }
.brand { display: flex; align-items: center; gap: 9px; user-select: none; }
.brand-text { display: flex; flex-direction: column; line-height: 1.15; }
.name {
  font-size: 13px; font-weight: 600; letter-spacing: 1px;
  background: linear-gradient(90deg, #ffffff 30%, #a8c6ff 100%); /* 冷光渐变字 */
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
.sub { font-size: 10px; color: rgba(255, 255, 255, 0.55); }
.right { display: flex; align-items: center; gap: 12px; user-select: none; }
/* 左栏底部设置按钮组：整体 margin-top:auto 推到 rail 最底部 */
.rail-bottom {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.rail-settings { /* 保留类名兼容，但贴底由 rail-bottom 负责 */ }
.back-btn {
  width: auto; /* 覆盖 .icon-btn 的 28px 固定宽，让文字撑开 */
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 26px;
  padding: 0 9px;
  border: 1px solid rgba(255, 255, 255, 0.25);
  border-radius: var(--r-sm);
  background: rgba(255, 255, 255, 0.08);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.15);
  color: rgba(255, 255, 255, 0.8);
  font-size: 12px;
  transition: all 0.18s;
}
.back-btn:hover {
  border-color: rgba(160, 195, 255, 0.7);
  background: rgba(29, 93, 228, 0.35);
  box-shadow: 0 0 10px rgba(29, 93, 228, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.2);
  color: #fff;
}
/* 用户信息卡：磨砂玻璃 + 蓝靛渐变头像；退出按钮悬停转红（危险语义） */
.topbar .user-chip {
  padding: 3px 5px 3px 4px;
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.14), rgba(255, 255, 255, 0.05));
  border: 1px solid rgba(255, 255, 255, 0.18);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.18), 0 2px 6px rgba(0, 0, 0, 0.15);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  transition: border-color 0.18s, box-shadow 0.18s;
}
.topbar .user-chip:hover {
  border-color: rgba(160, 195, 255, 0.45);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.22), 0 4px 10px rgba(29, 93, 228, 0.3);
}
.topbar .user-avatar {
  background: linear-gradient(135deg, #2f6ff0, #6d4de0);
  box-shadow: 0 0 8px rgba(29, 93, 228, 0.45);
}
.topbar .user-chip .icon-btn {
  width: 24px; height: 24px; border-radius: 50%;
  transition: background 0.18s, color 0.18s, box-shadow 0.18s;
}
.topbar .user-chip .icon-btn:hover {
  background: rgba(229, 72, 77, 0.85);
  color: #fff;
  box-shadow: 0 0 8px rgba(229, 72, 77, 0.45);
}
.left { display: flex; align-items: center; gap: 16px; min-width: 0; }

.layout {
  flex: 1;
  display: flex;
  gap: 8px;
  padding: 8px;
  min-height: 0;
}
/* 侧栏整体（导航 + 列表）共用一张卡片的阴影与圆角，中间无缝 */
.side-unit {
  display: flex;
  flex-shrink: 0;
  border-radius: var(--r-md);
  box-shadow: var(--shadow-card);
  overflow: hidden;
}

.col-side {
  /* 宽度由 useBoundaryResize 控制（初始 264，拖拽 220~420，localStorage 持久化） */
  background: var(--c-panel);
  overflow: hidden;
}

/* 左侧导航栏（微信式图标栏）：与顶栏同色系，顶部一抹品牌蓝辉光呼应极光 */
.rail {
  width: 46px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 10px 0;
  background:
    radial-gradient(150px 100px at 50% -20%, rgba(29, 93, 228, 0.45), transparent 75%),
    linear-gradient(180deg, var(--c-navy), var(--c-navy-2));
}
.rail-btn {
  position: relative;
  width: 34px; height: 34px;
  display: flex; align-items: center; justify-content: center;
  border: none; border-radius: var(--r-sm);
  background: none;
  color: rgba(255, 255, 255, 0.55);
  cursor: pointer;
  transition: background 0.18s, color 0.18s, transform 0.18s, box-shadow 0.18s;
}
.rail-btn:hover {
  background: rgba(255, 255, 255, 0.12);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.12);
  color: #fff;
  transform: translateY(-1px);
}
.rail-btn:active { transform: translateY(0) scale(0.94); }
.rail-btn.on {
  background: linear-gradient(135deg, #2f6ff0, #1d5de4);
  color: #fff;
  box-shadow: 0 0 12px rgba(29, 93, 228, 0.55), inset 0 1px 0 rgba(255, 255, 255, 0.25);
}
.col-main {
  flex: 1;
  background: var(--c-panel);
  border-radius: var(--r-md);
  box-shadow: var(--shadow-card);
  overflow: hidden;
  min-width: 0;
}
</style>
