<script setup>
/** 通用右键菜单弹层：Teleport 到 body，按坐标贴边自动翻转，收起时机统一收口。
 *  items: [{ key, label, checked?, sepBefore? }]；checked 渲染右侧对勾（开关类菜单项）。 */
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps({
  pos: { type: Object, default: null }, // { x, y }；null 即收起
  items: { type: Array, default: () => [] },
})
const emit = defineEmits(['select', 'close'])

const el = ref(null)

/** 打开后按实际尺寸贴边翻转（右侧/底部放不下时往回收）。 */
watch(() => props.pos, async (p) => {
  if (!p) return
  await nextTick()
  const box = el.value
  if (!box) return
  const w = box.offsetWidth
  const h = box.offsetHeight
  box.style.left = Math.max(8, p.x + w > window.innerWidth - 8 ? window.innerWidth - w - 8 : p.x) + 'px'
  box.style.top = Math.max(8, p.y + h > window.innerHeight - 8 ? window.innerHeight - h - 8 : p.y) + 'px'
})

/* 收起时机：点击菜单外任意处 / Esc / 页面滚动 / 窗口尺寸变化 / 失焦 */
const onDocClick = (e) => {
  if (el.value && !el.value.contains(e.target)) emit('close')
}
const onKeydown = (e) => {
  if (e.key === 'Escape') emit('close')
}
const onScroll = () => emit('close')
window.addEventListener('click', onDocClick)
window.addEventListener('keydown', onKeydown)
window.addEventListener('scroll', onScroll, true)
window.addEventListener('resize', onScroll)
window.addEventListener('blur', onScroll)
onBeforeUnmount(() => {
  window.removeEventListener('click', onDocClick)
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('scroll', onScroll, true)
  window.removeEventListener('resize', onScroll)
  window.removeEventListener('blur', onScroll)
})
</script>

<template>
  <Teleport to="body">
    <div v-if="pos" ref="el" class="ctx-menu" role="menu" aria-label="操作菜单">
      <template v-for="item in items" :key="item.key">
        <div v-if="item.sepBefore" class="ctx-sep"></div>
        <button
          class="ctx-item"
          :role="item.checked === undefined ? 'menuitem' : 'menuitemradio'"
          :aria-checked="item.checked"
          @click="emit('select', item.key)"
        >
          <span>{{ item.label }}</span>
          <svg v-if="item.checked" class="check" xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
        </button>
      </template>
    </div>
  </Teleport>
</template>

<style scoped>
/* 右键菜单：白底细边框 + 浮起阴影，贴微信 PC 观感 */
.ctx-menu {
  position: fixed;
  min-width: 148px;
  padding: 4px;
  background: #fff;
  border: 1px solid var(--c-border-strong);
  border-radius: var(--r-md);
  box-shadow: 0 6px 24px rgba(20, 38, 77, 0.16);
  z-index: 2100;
  animation: ctx-pop 0.12s ease both;
}
@keyframes ctx-pop {
  from { opacity: 0; transform: scale(0.96); }
  to { opacity: 1; transform: none; }
}
.ctx-item {
  display: flex; align-items: center; justify-content: space-between; gap: 10px;
  width: 100%; padding: 7px 10px;
  border: none; border-radius: var(--r-sm);
  background: none; color: var(--c-text);
  font-size: 13px; text-align: left;
  cursor: pointer;
  transition: background 0.1s;
}
.ctx-item:hover { background: var(--c-primary-soft); color: var(--c-primary-deep); }
.ctx-item .check { color: var(--c-ok); flex-shrink: 0; }
.ctx-sep { height: 1px; margin: 4px 6px; background: var(--c-border); }
</style>
