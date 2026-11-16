<script setup>
/** 文件卡片（msg_type=3：文件名 + 下载）与链接卡片（msg_type=5：标题 + 摘要 + 域名）。
 * 文件下载直接走媒体地址；链接新窗口打开。链接缺 url 时显示 [链接] 占位。 */
import { computed } from 'vue'
import { appInfoOf, fileTitleOf, hostOf } from '../utils/message'
import { messageMediaUrlOf } from '../utils/media'

const props = defineProps({
  msg: { type: Object, required: true },
})

/* 文件名（payload 优先，旧数据前端解析 XML 兜底）；文件下载地址与展示同源 */
const fileTitle = computed(() => fileTitleOf(props.msg))
const href = computed(() => messageMediaUrlOf(props.msg))

/* 链接信息（payload.app 优先，旧数据前端解析 XML 兜底） */
const app = computed(() => appInfoOf(props.msg))
</script>

<template>
  <!-- 文件卡片：图标 + 文件名 + 下载 -->
  <a v-if="msg.msg_type === 3" class="card file-card" :href="href" :download="fileTitle">
    <span class="badge">文件</span>
    <span class="fc-main">
      <span class="fc-title">{{ fileTitle }}</span>
      <span class="fc-sub">点击下载</span>
    </span>
  </a>

  <!-- 链接卡片：标题 + 摘要 + 域名 -->
  <a v-else-if="app.url" class="card link-card" :href="app.url" target="_blank" rel="noopener">
    <span class="lc-title">{{ app.title || '[链接]' }}</span>
    <span v-if="app.desc" class="lc-desc">{{ app.desc }}</span>
    <span class="lc-host"><span class="badge">链接</span><span class="host">{{ hostOf(app.url) }}</span></span>
  </a>
  <div v-else class="type-label">[链接]</div>
</template>

<style scoped>
.link-card, .file-card {
  display: flex; flex-direction: column; gap: 4px;
  width: 200px; padding: 10px;
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
  background: #fff;
  color: var(--c-text); text-decoration: none;
  transition: border-color 0.15s;
}
.link-card:hover, .file-card:hover { border-color: var(--c-primary); }
.file-card { flex-direction: row; align-items: center; gap: 8px; }
.badge {
  flex-shrink: 0;
  font-size: 10px; color: var(--c-primary);
  background: var(--c-primary-soft);
  border-radius: 3px; padding: 1px 5px;
}
.fc-main { display: flex; flex-direction: column; min-width: 0; }
.fc-title { font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fc-sub { font-size: 11px; color: var(--c-text-sub); }
.lc-title {
  font-size: 13px; font-weight: 600; line-height: 1.4;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.lc-desc {
  font-size: 12px; color: var(--c-text-sub); line-height: 1.4;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.lc-host { font-size: 11px; color: var(--c-text-sub); display: flex; align-items: center; gap: 6px; min-width: 0; }
.lc-host .host { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.type-label { color: var(--c-primary); }
</style>
