<script setup>
/** 帮助中心壳：左侧目录导航 + 右侧内容滚动容器。
 *  目录点击平滑滚动定位，滚动时自动高亮当前章节（rAF 节流）。
 *  章节正文按职责拆分在 HelpBasics（基础使用）与 HelpOperations（操作/速查）两个子组件中。 */
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import HelpBasics from './HelpBasics.vue'
import HelpOperations from './HelpOperations.vue'

const CONTENT_SCROLL_ID = 'help-content-scroll'

const chapters = ref([
  { id: 'overview', title: '快速开始' },
  { id: 'conversation', title: '会话管理' },
  { id: 'contacts', title: '通讯录' },
  { id: 'chat', title: '聊天功能' },
  { id: 'message-actions', title: '消息操作' },
  { id: 'quick-quote', title: '快捷报价' },
  { id: 'settings', title: '设置' },
  { id: 'shortcuts', title: '快捷键速查' },
])

const activeChapter = ref('overview')
const contentEl = ref(null)

/** 目录项点击 → 平滑滚动到对应章节 */
function jumpTo(id) {
  activeChapter.value = id
  nextTick(() => {
    const target = contentEl.value?.querySelector(`[data-chapter="${id}"]`)
    const wrap = contentEl.value
    if (target && wrap) {
      wrap.scrollTo({
        top: target.offsetTop - 12,
        behavior: 'smooth',
      })
    }
  })
}

/** 滚动监听：各章节顶缘进入可视区时高亮对应目录项 */
let scrollRaf = null
function onContentScroll() {
  if (scrollRaf) return
  scrollRaf = requestAnimationFrame(() => {
    scrollRaf = null
    const wrap = contentEl.value
    if (!wrap) return
    const wrapTop = wrap.scrollTop + 20
    let current = chapters.value[0].id
    for (const c of chapters.value) {
      const el = wrap.querySelector(`[data-chapter="${c.id}"]`)
      if (el && el.offsetTop <= wrapTop) current = c.id
    }
    if (current !== activeChapter.value) activeChapter.value = current
  })
}

onMounted(() => contentEl.value?.addEventListener('scroll', onContentScroll, { passive: true }))
onBeforeUnmount(() => {
  contentEl.value?.removeEventListener('scroll', onContentScroll)
  if (scrollRaf) cancelAnimationFrame(scrollRaf)
})
</script>

<template>
  <div class="help-center">
    <!-- 左侧目录 -->
    <aside class="toc">
      <div class="toc-head">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/></svg>
        <span>帮助中心</span>
      </div>
      <nav class="toc-nav">
        <button
          v-for="c in chapters" :key="c.id"
          class="toc-item" :class="{ on: activeChapter === c.id }"
          @click="jumpTo(c.id)"
        >
          <span class="toc-dot"></span>
          <span class="toc-label">{{ c.title }}</span>
        </button>
      </nav>
      <div class="toc-foot">
        <span class="ver">SI 客服系统 · 帮助文档</span>
      </div>
    </aside>

    <!-- 右侧内容 -->
    <main ref="contentEl" class="content" :id="CONTENT_SCROLL_ID">
      <HelpBasics />
      <HelpOperations />
      <div class="content-foot">SI 客服系统 · 帮助文档 &nbsp;·&nbsp; 如需反馈请联系系统管理员</div>
    </main>
  </div>
</template>

<style scoped>
.help-center {
  display: flex;
  height: 100%;
  background: var(--c-bg);
  overflow: hidden;
}

/* ===== 左侧目录 ===== */
.toc {
  width: 200px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--c-panel);
  border-right: 1px solid var(--c-border);
  overflow: hidden;
}
.toc-head {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 14px 14px 10px;
  font-weight: 700;
  font-size: 13px;
  color: var(--c-primary);
  border-bottom: 1px solid var(--c-border);
}
.toc-nav {
  flex: 1;
  overflow-y: auto;
  padding: 8px 8px;
}
.toc-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 7px 10px;
  border: none;
  border-radius: var(--r-md);
  background: none;
  color: var(--c-text-sub);
  font-size: 12px;
  font-family: inherit;
  text-align: left;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.toc-item:hover {
  background: var(--c-primary-soft);
  color: var(--c-primary);
}
.toc-item.on {
  background: var(--c-primary-soft);
  color: var(--c-primary-deep);
  font-weight: 600;
}
.toc-dot {
  width: 6px;
  height: 6px;
  flex-shrink: 0;
  border-radius: 50%;
  background: var(--c-border-strong);
  transition: background 0.15s, transform 0.15s;
}
.toc-item.on .toc-dot {
  background: var(--c-primary);
  transform: scale(1.5);
}
.toc-foot {
  padding: 10px 14px;
  border-top: 1px solid var(--c-border);
  font-size: 10px;
  color: var(--c-border-strong);
}

/* ===== 右侧内容 ===== */
.content {
  flex: 1;
  overflow-y: auto;
  padding: 24px 40px 40px;
  scroll-behavior: smooth;
}

.content-foot {
  margin-top: 40px;
  padding-top: 20px;
  border-top: 1px solid var(--c-border);
  text-align: center;
  font-size: 11px;
  color: var(--c-border-strong);
}

/* 响应式：窄屏收起目录 */
@media (max-width: 900px) {
  .toc { width: 150px; }
  .content { padding: 20px 24px 30px; }
}
</style>
