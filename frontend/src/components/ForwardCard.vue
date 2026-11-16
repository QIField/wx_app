<script setup>
/** 合并转发卡片（msg_type=9，业务端本地消息）：标题 + 前两条预览 + 页脚，
 * 点开拉快照回看（ForwardRecord 由父层承载）。原消息删除不影响快照内容。
 * 多选模式下点击是勾选而非回看。 */
const props = defineProps({
  msg: { type: Object, required: true },
  selectable: { type: Boolean, default: false },
})
const emit = defineEmits(['toggle', 'openrecord'])
</script>

<template>
  <button
    class="fwd-card"
    type="button"
    :title="selectable ? '' : '点击查看聊天记录'"
    @click.stop="selectable ? emit('toggle', msg.id) : emit('openrecord', msg)"
  >
    <span class="fwd-title">{{ msg.payload?.title || msg.content || '聊天记录' }}</span>
    <span v-for="(p, i) in (msg.payload?.preview || []).slice(0, 2)" :key="i" class="fwd-line">{{ p }}</span>
    <span class="fwd-foot">
      <span class="badge">聊天记录</span>
      <span class="fwd-cnt">{{ msg.payload?.count ?? '' }}条消息</span>
    </span>
  </button>
</template>

<style scoped>
/* 合并转发卡片：白底窄卡，观感与微信「聊天记录」卡片一致 */
.fwd-card {
  display: flex; flex-direction: column; gap: 3px;
  width: 210px; padding: 10px;
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
  background: #fff;
  cursor: pointer;
  text-align: left;
  transition: border-color 0.15s;
}
.fwd-card:hover { border-color: var(--c-primary); }
.fwd-title {
  font-size: 13px; font-weight: 600; line-height: 1.4;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.fwd-line {
  font-size: 12px; color: var(--c-text-sub); line-height: 1.4;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.fwd-foot {
  margin-top: 5px; padding-top: 6px;
  border-top: 1px solid var(--c-border);
  display: flex; align-items: center; gap: 6px;
}
.fwd-cnt { font-size: 11px; color: var(--c-text-sub); }

.badge {
  flex-shrink: 0;
  font-size: 10px; color: var(--c-primary);
  background: var(--c-primary-soft);
  border-radius: 3px; padding: 1px 5px;
}
</style>
