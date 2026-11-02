<script setup>
/** 顶栏聊天账号卡片组：显示名 + 在线点 + 未读徽标，点击切换当前查看的设备。 */
import { useChatStore } from '../stores/chat'

const chat = useChatStore()
</script>

<template>
  <div class="device-cards">
    <button
      v-for="d in chat.devices"
      :key="d.openid"
      class="dev-card"
      :class="{ on: d.openid === chat.activeOpenid }"
      :title="`${d.display_name}（${d.online === 1 ? '在线' : d.online === 0 ? '离线' : '检测中'}）`"
      @click="chat.switchDevice(d.openid)"
    >
      <span class="dev-dot" :class="{ on: d.online === 1 }"></span>
      <span class="dev-name">{{ d.display_name }}</span>
      <span v-if="d.unread" class="dev-unread num">{{ d.unread > 99 ? '99+' : d.unread }}</span>
    </button>
    <span v-if="!chat.devices.length" class="dev-empty">未绑定聊天账号</span>
  </div>
</template>

<style scoped>
/* 磨砂玻璃胶囊 + 内侧高光，悬浮上浮，激活渐变发光 */
.device-cards {
  display: flex; align-items: center; gap: 7px;
  min-width: 0; overflow-x: auto; scrollbar-width: none;
}
.device-cards::-webkit-scrollbar { display: none; }
.dev-card {
  position: relative;
  display: inline-flex; align-items: center; gap: 6px;
  height: 28px; padding: 0 11px;
  max-width: 170px; flex-shrink: 0;
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 14px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.14), rgba(255, 255, 255, 0.05));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.18), 0 2px 6px rgba(0, 0, 0, 0.18);
  color: rgba(255, 255, 255, 0.88);
  font-size: 12px; line-height: 1;
  cursor: pointer;
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  transition: transform 0.18s, box-shadow 0.18s, border-color 0.18s, background 0.18s;
}
.dev-card:hover {
  transform: translateY(-1px);
  border-color: rgba(160, 195, 255, 0.6);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.22), 0 4px 12px rgba(29, 93, 228, 0.35);
  color: #fff;
}
.dev-card:active { transform: translateY(0) scale(0.97); }
.dev-card.on {
  background: linear-gradient(135deg, #2f6ff0 0%, #1d5de4 45%, #3a55c9 100%);
  border-color: rgba(160, 195, 255, 0.85);
  color: #fff;
  box-shadow:
    0 0 0 1px rgba(90, 140, 255, 0.25),
    0 4px 14px rgba(29, 93, 228, 0.55),
    inset 0 1px 0 rgba(255, 255, 255, 0.3);
}
.dev-dot { width: 6px; height: 6px; border-radius: 50%; background: #8b93a3; flex-shrink: 0; transition: background 0.18s, box-shadow 0.18s; }
.dev-card.on .dev-dot { background: #a9f0cd; box-shadow: 0 0 6px rgba(83, 240, 165, 0.8); }
.dev-dot.on { background: #35d07f; box-shadow: 0 0 5px #35d07f; }
.dev-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
/* 未读徽标：红渐变 + 顶栏底色描边（像嵌在卡上）+ 呼吸脉冲 */
.dev-unread {
  position: absolute; top: -7px; right: -7px;
  min-width: 17px; height: 17px; padding: 0 4px;
  border-radius: 9px;
  background: linear-gradient(135deg, #ff6b6d, #e5484d);
  border: 1.5px solid rgba(17, 32, 66, 0.95);
  color: #fff; font-size: 10px; font-weight: 700; line-height: 14px; text-align: center;
  animation: unread-pulse 2s ease-in-out infinite;
}
@keyframes unread-pulse {
  0%, 100% { box-shadow: 0 2px 6px rgba(229, 72, 77, 0.5), 0 0 0 0 rgba(229, 72, 77, 0.45); }
  50% { box-shadow: 0 2px 6px rgba(229, 72, 77, 0.5), 0 0 0 5px rgba(229, 72, 77, 0); }
}
.dev-empty { font-size: 12px; color: rgba(255, 255, 255, 0.45); user-select: none; }
@media (prefers-reduced-motion: reduce) {
  .dev-unread { animation: none; }
}
</style>
