<script setup>
/** 合并转发卡片回看：按消息 id 拉快照，微信「聊天记录」同款灰底逐条展示。
 *  数据来自 forward_snapshot 快照表——原消息删除不影响回看。
 */
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchForwardSnapshot } from '../api'

const props = defineProps({
  msgId: { type: Number, default: null }, // 卡片消息 id；null 即关闭
})
const emit = defineEmits(['close'])

const loading = ref(false)
const record = ref(null) // { title, count, items: [{seq, sender_name, content, create_time}] }

watch(() => props.msgId, async (id) => {
  record.value = null
  if (!id) return
  loading.value = true
  try {
    record.value = await fetchForwardSnapshot(id)
  } catch (exc) {
    ElMessage.error(exc.message || '聊天记录加载失败')
    emit('close')
  } finally {
    loading.value = false
  }
}, { immediate: true })
</script>

<template>
  <el-dialog
    :model-value="!!msgId"
    :title="record?.title || '聊天记录'"
    width="460px"
    :append-to-body="true"
    @close="emit('close')"
  >
    <div v-if="loading" v-loading="true" class="rec-loading"></div>
    <template v-else-if="record">
      <div class="rec-list">
        <div v-for="item in record.items" :key="item.seq" class="rec-item">
          <div class="rec-head">
            <img
              v-if="item.sender_avatar"
              class="rec-ava"
              :src="item.sender_avatar"
              alt=""
              referrerpolicy="no-referrer"
            />
            <span v-else class="rec-ava fallback">{{ (item.sender_name || '?').slice(0, 1) }}</span>
            <span class="rec-name">{{ item.sender_name }}</span>
          </div>
          <div class="rec-bubble">{{ item.content }}</div>
        </div>
      </div>
      <div class="rec-foot">共 {{ record.count }} 条消息 · 快照留档，原消息删除不影响回看</div>
    </template>
  </el-dialog>
</template>

<style scoped>
.rec-loading { height: 180px; }
.rec-list {
  max-height: 380px; overflow: auto;
  background: var(--c-surface);
  border-radius: var(--r-md);
  padding: 12px;
}
.rec-item { margin-bottom: 12px; }
.rec-item:last-child { margin-bottom: 0; }
.rec-head { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; user-select: none; }
.rec-ava {
  width: 22px; height: 22px; flex-shrink: 0;
  border-radius: 4px; object-fit: cover;
  background: var(--c-primary-soft);
  color: var(--c-primary); font-size: 11px; font-weight: 600;
  display: flex; align-items: center; justify-content: center;
}
.rec-name { font-size: 11px; color: var(--c-text-sub); }
.rec-bubble {
  display: inline-block;
  max-width: 82%;
  padding: 6px 10px;
  background: #fff;
  border: 1px solid var(--c-border);
  border-radius: var(--r-lg);
  border-top-left-radius: 3px;
  font-size: 13px; line-height: 1.55;
  white-space: pre-wrap; word-break: break-word;
}
.rec-foot {
  margin-top: 10px;
  font-size: 11px; color: var(--c-text-sub);
  text-align: center; user-select: none;
}
</style>
