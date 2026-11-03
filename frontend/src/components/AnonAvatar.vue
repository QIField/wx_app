<script setup>
/** 匿名头像（wxid 脱敏契约）：人形图标 + 由 alias 决定的稳定色相。
 *  同一人恒定、不同人互异（群聊中多个未命名成员可区分）。
 *  尺寸/圆角随宿主 class 控制（与普通 .avatar 一致）。 */
import { computed } from 'vue'
import { anonStyle } from '../utils/format'

const props = defineProps({
  alias: { type: String, default: '' },
})

const style = computed(() => anonStyle(props.alias))
</script>

<template>
  <span class="anon-avatar" :style="style" :title="alias ? `匿名标识 ${alias}` : '匿名'">
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7z" />
    </svg>
  </span>
</template>

<style scoped>
.anon-avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  overflow: hidden;
}
.anon-avatar svg {
  width: 62%;
  height: 62%;
  fill: rgba(255, 255, 255, 0.92);
}
</style>
