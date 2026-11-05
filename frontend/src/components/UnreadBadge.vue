<script setup>
/** 未读红点：统一"出现规则 + 视觉"（会话列表 / 通讯录 / 侧栏总未读共用）。
 *  count<=0 不渲染；>99 显示 99+；variant 区分浅色面板（row）与深色导航（rail）；
 *  dot=true 退化为纯红点不显示数字（免打扰会话的微信同款弱化提示）。 */
import { computed } from 'vue'
import { formatBadgeCount } from '../utils/badge'

const props = defineProps({
  count: { type: Number, default: 0 },
  variant: { type: String, default: 'row' }, // row | rail
  dot: { type: Boolean, default: false },
})

const label = computed(() => formatBadgeCount(props.count))
const wide = computed(() => props.count > 9)
</script>

<template>
  <Transition name="unread">
    <span
      v-if="count > 0"
      class="unread"
      :class="[`is-${variant}`, { wide, dot }]"
      role="status"
      :aria-label="`${count} 条未读消息`"
    >{{ label }}</span>
  </Transition>
</template>

<style scoped>
/* 简约红点：纯色实心胶囊，无渐变、无阴影、无光圈 */
.unread {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  min-width: 16px;
  height: 16px;
  padding: 0 5px;
  border-radius: 8px;
  background: var(--c-danger);
  color: #fff;
  font-family: var(--font-num);
  font-size: 10px;
  font-weight: 600;
  line-height: 1;
}
.unread.wide { padding: 0 6px; }

/* 免打扰会话：数字退化为纯红点（有消息但不催促，微信同款） */
.unread.dot {
  min-width: 8px;
  width: 8px;
  height: 8px;
  padding: 0;
  border-radius: 50%;
  font-size: 0;
}

/* 深色侧栏：悬浮在导航按钮右上角，同样纯色，不加描边与光晕。
   类名用 is-rail 前缀，避免与页面 .rail（导航栏）选择器撞车导致样式被覆盖 */
.unread.is-rail {
  position: absolute;
  top: -4px;
  right: -4px;
  min-width: 15px;
  height: 15px;
  padding: 0 4px;
}
.unread.is-rail.wide { padding: 0 5px; }

/* 出现/消失只做轻微淡入淡出，避免抢视线 */
.unread-enter-active,
.unread-leave-active { transition: opacity 0.12s ease; }
.unread-enter-from,
.unread-leave-to { opacity: 0; }
</style>
