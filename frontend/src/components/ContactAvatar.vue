<script setup>
/** 联系人/会话头像（wxid 脱敏契约·三态统一）：有图 → 图片；名称未解析 →
 *  匿名人形（色相随 alias 稳定）；否则 → 名称首字色块。群聊自动加 group 类（绿底）。
 *  尺寸/圆角由宿主 class 控制（透传到根元素），与原 .avatar 用法一致。 */
import { computed } from 'vue'
import AnonAvatar from './AnonAvatar.vue'

const props = defineProps({
  name: { type: String, default: '' },
  alias: { type: String, default: '' },
  avatar: { type: String, default: '' },
  chatType: { type: Number, default: 1 },
})

const isGroup = computed(() => props.chatType === 2)
const letter = computed(() => (props.name || '').slice(0, 1).toUpperCase())
</script>

<template>
  <span class="contact-avatar" :class="{ group: isGroup }">
    <img v-if="avatar" :src="avatar" alt="" referrerpolicy="no-referrer">
    <AnonAvatar v-else-if="!name" :alias="alias" />
    <template v-else>{{ letter }}</template>
  </span>
</template>

<style scoped>
.contact-avatar {
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0; overflow: hidden;
}
.contact-avatar img { width: 100%; height: 100%; object-fit: cover; background: var(--c-surface); }
.contact-avatar :deep(.anon-avatar) { width: 100%; height: 100%; }
</style>
