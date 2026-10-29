<script setup>
/** 右栏：客户资料骨架。第⑤步接入报价处理台与业务端自建客户数据。 */
import { useChatStore } from '../stores/chat'

const chat = useChatStore()
</script>

<template>
  <div class="info">
    <div class="head">资料</div>
    <el-empty
      v-if="!chat.currentConv"
      description="选中会话后展示客户资料"
      :image-size="70"
    />
    <div v-else class="body">
      <div class="field"><span class="k">名称</span>{{ chat.currentConv.name || '-' }}</div>
      <div class="field"><span class="k">wxid</span>{{ chat.currentConv.wxid }}</div>
      <div class="field"><span class="k">类型</span>{{ chat.currentConv.chat_type === 2 ? '群聊' : '单聊' }}</div>
      <div class="placeholder">客户资料 / 报价处理台（第⑤步接入）</div>
    </div>
  </div>
</template>

<style scoped>
.info { display: flex; flex-direction: column; height: 100%; }
.head {
  padding: 14px 20px; font-weight: 600;
  border-bottom: 1px solid var(--c-border);
}
.body { padding: 16px 20px; }
.field { margin-bottom: 12px; font-size: 13px; word-break: break-all; }
.k {
  display: inline-block; width: 52px;
  color: var(--c-text-sub);
}
.placeholder {
  margin-top: 24px; padding: 24px 12px;
  border: 1px dashed var(--c-border); border-radius: var(--r-md);
  color: var(--c-text-sub); font-size: 12px; text-align: center;
}
</style>
