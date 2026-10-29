<script setup>
/** 左栏：会话列表（未读角标、置顶优先、最后一条摘要）。 */
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
  <div class="layout">
    <aside class="col-side"><ConvList /></aside>
    <main class="col-main"><ChatPanel /></main>
    <aside class="col-info"><InfoPanel /></aside>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  height: 100%;
  gap: 1px;
  background: var(--c-border);
}
.col-side { width: 300px; background: var(--c-panel); }
.col-main { flex: 1; background: var(--c-panel); min-width: 0; }
.col-info { width: 320px; background: var(--c-panel); }
</style>
