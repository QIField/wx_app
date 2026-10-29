<script setup>
/** 右栏：客户资料区（本期为美观预留，报价处理台后续接入）。 */
import { computed } from 'vue'
import { useChatStore } from '../stores/chat'

const chat = useChatStore()
const conv = computed(() => chat.currentConv)
</script>

<template>
  <div class="info">
    <div v-if="!conv" class="empty">
      <div class="ring">?</div>
      <p>选中左侧会话后<br />这里展示客户资料</p>
    </div>

    <template v-else>
      <div class="card profile">
        <div class="avatar">{{ (conv.name || conv.wxid).slice(0, 1) }}</div>
        <div class="who">
          <div class="name">{{ conv.name || conv.wxid }}</div>
          <div class="wxid">{{ conv.wxid }}</div>
        </div>
      </div>

      <div class="card fields">
        <div class="field"><span class="k">类型</span><span class="v">{{ conv.chat_type === 2 ? '群聊' : '单聊' }}</span></div>
        <div class="field"><span class="k">未读</span><span class="v">{{ conv.unread_count }}</span></div>
        <div class="field"><span class="k">最后消息</span><span class="v">{{ conv.last_msg || '—' }}</span></div>
      </div>

      <div class="card slot">
        <div class="slot-title">扩展区域</div>
        <div class="slot-desc">客户资料编辑、报价处理台等功能将在此接入</div>
        <div class="skel"></div>
        <div class="skel short"></div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.info { height: 100%; overflow-y: auto; padding: 16px; }
.empty {
  height: 100%;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 14px;
  color: var(--c-text-sub); font-size: 13px; text-align: center;
}
.ring {
  width: 56px; height: 56px; border-radius: 50%;
  border: 2px dashed var(--c-border-strong);
  display: flex; align-items: center; justify-content: center;
  font-size: 20px; color: var(--c-text-sub);
}

.card {
  background: var(--c-bg);
  border-radius: var(--r-md);
  padding: 14px;
  margin-bottom: 12px;
}
.profile { display: flex; align-items: center; gap: 12px; }
.avatar {
  width: 44px; height: 44px; border-radius: var(--r-sm);
  background: var(--c-primary); color: #fff;
  font-size: 18px; font-weight: 600;
  display: flex; align-items: center; justify-content: center;
}
.who { min-width: 0; }
.name { font-weight: 600; }
.wxid { font-size: 12px; color: var(--c-text-sub); margin-top: 2px; }

.fields .field { display: flex; padding: 6px 0; font-size: 13px; }
.fields .k { width: 70px; color: var(--c-text-sub); flex-shrink: 0; }
.fields .v { color: var(--c-text); min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.slot-title { font-weight: 600; font-size: 13px; }
.slot-desc { font-size: 12px; color: var(--c-text-sub); margin: 6px 0 12px; }
.skel {
  height: 40px; border-radius: var(--r-sm);
  background: linear-gradient(90deg, #eceff4 25%, #f5f7fa 50%, #eceff4 75%);
  background-size: 200% 100%;
  animation: shine 1.5s infinite;
  margin-bottom: 8px;
}
.skel.short { width: 60%; }
@keyframes shine { to { background-position: -200% 0; } }
</style>
