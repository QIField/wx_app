<script setup>
/** @提及选择浮层（纯展示）：贴在输入框上方，列出群成员。
 *  交互状态由 ChatComposer 持有（检索词/高亮项），这里只负责渲染与上报选择，
 *  鼠标事件一律 mousedown.prevent，保证点击不会让输入框失焦、光标不跳。 */
import { nextTick, ref, watch } from 'vue'
import ContactAvatar from './ContactAvatar.vue'
import { memberNameHtml, memberPinyinHtml } from '../utils/mention'

const props = defineProps({
  visible: { type: Boolean, default: false },
  members: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
  query: { type: String, default: '' },
  active: { type: Number, default: 0 },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['select', 'update:active'])

const listEl = ref(null)

/** 键盘移动高亮后，把当前行滚进可视区（block:nearest 不会带动整个页面滚动）。 */
watch(() => props.active, async () => {
  await nextTick()
  listEl.value?.querySelector('.mp-row.on')?.scrollIntoView({ block: 'nearest' })
})
</script>

<template>
  <div v-if="visible" class="mention-pop" role="listbox" aria-label="群成员">
    <div class="mp-head">
      <span class="mp-title">选择提醒的人</span>
      <span class="mp-count num">
        {{ query ? `@${query} · ${members.length}/${total}` : `${total} 人` }}
      </span>
    </div>

    <div ref="listEl" class="mp-list">
      <div v-if="loading" class="mp-empty">正在加载群成员…</div>
      <div v-else-if="!total" class="mp-empty">这个群还没有成员名册，同步后再试</div>
      <div v-else-if="!members.length" class="mp-empty">
        未找到「{{ query }}」，换个关键词试试
      </div>
      <div
        v-for="(m, i) in members"
        :key="m.id"
        class="mp-row"
        :class="{ on: i === active }"
        role="option"
        :aria-selected="i === active"
        @mousedown.prevent="emit('select', m)"
        @mousemove="emit('update:active', i)"
      >
        <ContactAvatar
          class="mp-ava"
          :name="m.name"
          :alias="m.alias"
          :avatar="m.avatar"
        />
        <span class="mp-main">
          <span class="mp-name">
            <!-- eslint-disable-next-line vue/no-v-html -->
            <span v-html="memberNameHtml(m, query)" />
          </span>
          <!-- eslint-disable-next-line vue/no-v-html -->
          <span class="mp-py" v-html="memberPinyinHtml(m, query)" />
        </span>
        <span class="mp-enter">↵</span>
      </div>
    </div>

    <div class="mp-foot">
      <kbd>↑</kbd><kbd>↓</kbd><span>切换</span>
      <kbd>Enter</kbd><span>选择</span>
      <kbd>Esc</kbd><span>关闭</span>
    </div>
  </div>
</template>

<style scoped>
/* 浮层本体：相对 .composer-wrap 定位，贴在输入框上方 8px（left 由父级按 @ 位置算） */
.mention-pop {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 0;
  z-index: 20;
  background: var(--c-panel);
  border: 1px solid var(--c-border-strong);
  border-radius: var(--r-md);
  box-shadow: 0 12px 32px rgba(20, 38, 77, 0.16), 0 2px 6px rgba(20, 38, 77, 0.06);
  overflow: hidden;
  animation: mp-in 0.14s cubic-bezier(0.2, 0.8, 0.2, 1);
}
@keyframes mp-in {
  from { opacity: 0; transform: translateY(5px) scale(0.985); }
  to { opacity: 1; transform: none; }
}

.mp-head {
  height: 30px;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 10px;
  border-bottom: 1px solid var(--c-border);
  background: #f5f7fa;
}
.mp-title { font-size: 11px; color: var(--c-text-sub); letter-spacing: 0.4px; }
.mp-count { font-size: 10px; color: var(--c-primary); }

.mp-list { max-height: 288px; overflow-y: auto; padding: 4px; }

.mp-row {
  position: relative;
  width: 100%;
  display: flex; align-items: center; gap: 9px;
  padding: 6px 8px;
  border: none; background: none; cursor: pointer;
  border-radius: var(--r-sm);
  text-align: left;
  font-family: var(--font-ui);
  transition: background 0.1s;
}
.mp-row:hover { background: #f5f7fa; }
.mp-row.on {
  background: var(--c-primary-soft);
  box-shadow: inset 2px 0 0 var(--c-primary);
}
/* 尺寸/圆角走宿主 class，图片/匿名/首字三态由 ContactAvatar 内部处理。
   底色同会话列表头像：首字态用主色，匿名态由 AnonAvatar 内联样式覆盖为 alias 色相 */
.mp-ava {
  width: 26px; height: 26px; flex-shrink: 0;
  border-radius: 3px;
  background: var(--c-primary);
  color: #fff; font-size: 11.5px; font-weight: 600;
}
.mp-main { min-width: 0; flex: 1; }
.mp-name { display: flex; align-items: center; gap: 5px; font-size: 12.5px; color: var(--c-text); line-height: 1.35; }
.mp-row.on .mp-name { color: var(--c-primary-deep); }
.mp-py {
  display: block;
  margin-top: 1px;
  font-family: var(--font-num);
  font-size: 10.5px;
  color: #9aa7bd;
  letter-spacing: 0.2px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.mp-py :deep(i) { font-style: normal; margin: 0 3px; color: var(--c-border-strong); }
.mp-py :deep(mark),
.mp-name :deep(mark) {
  background: #fff0b3;
  color: inherit;
  border-radius: 2px;
  padding: 0 1px;
}
.mp-row.on :deep(mark) { background: #ffe27a; }

.mp-enter {
  flex-shrink: 0;
  font-family: var(--font-num);
  font-size: 12px;
  color: var(--c-border-strong);
  opacity: 0;
  transition: opacity 0.1s;
}
.mp-row.on .mp-enter { color: var(--c-primary); opacity: 1; }

.mp-empty { padding: 20px 12px; text-align: center; font-size: 11.5px; color: var(--c-text-sub); }

.mp-foot {
  height: 26px;
  display: flex; align-items: center; gap: 3px;
  padding: 0 8px;
  border-top: 1px solid var(--c-border);
  background: #f5f7fa;
  font-size: 10px;
  color: #9aa7bd;
  user-select: none;
}
.mp-foot span { margin: 0 5px 0 1px; }
kbd {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 16px; height: 16px;
  padding: 0 3px;
  font-family: var(--font-num); font-size: 9.5px; line-height: 1;
  color: var(--c-text-sub);
  background: #fff;
  border: 1px solid var(--c-border-strong);
  border-bottom-width: 2px;
  border-radius: 3px;
}
</style>
