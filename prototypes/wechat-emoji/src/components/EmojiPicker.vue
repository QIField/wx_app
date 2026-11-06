<script setup>
/** 表情选择面板：微信同款底部弹层。
 *  Tab1 微信表情：113 个 `[名称]` 码（点击插入文本，微信原生互通）
 *  Tab2 Emoji：常用 Unicode 字符（系统字体渲染）
 *  最近使用：localStorage 持久化。组件不直接改输入框，select 上抛给输入区。
 */
import { computed, ref } from 'vue'
import { WX_FACES, UNICODE_EMOJIS, faceUrlOf } from '../data/wxEmojis'
import { recentWxFaces, pushRecentWxFace } from '../utils/emoji'

const props = defineProps({
  visible: { type: Boolean, default: false },
})
const emit = defineEmits(['select'])

const tab = ref('wx')
const recents = ref(recentWxFaces())

const showRecents = computed(() => tab.value === 'wx' && recents.value.length > 0)

function pickWx(name) {
  pushRecentWxFace(name)
  recents.value = recentWxFaces()
  emit('select', { kind: 'wx', name })
}
function pickUnicode(ch) {
  emit('select', { kind: 'unicode', char: ch })
}
</script>

<template>
  <transition name="panel">
    <div v-if="visible" class="picker">
      <div class="tabs">
        <button type="button" class="tab" :class="{ on: tab === 'wx' }" @click="tab = 'wx'">微信表情</button>
        <button type="button" class="tab" :class="{ on: tab === 'unicode' }" @click="tab = 'unicode'">Emoji</button>
        <span class="count">{{ tab === 'wx' ? `共 ${WX_FACES.length} 个 · 发送 [码] 微信原生互通` : '系统字体原生渲染' }}</span>
      </div>

      <!-- 最近使用：仅微信表情 Tab 显示 -->
      <div v-if="showRecents" class="recents">
        <span class="r-label">最近使用</span>
        <button
          v-for="name in recents" :key="'r' + name" type="button" class="cell r-cell"
          :title="`[${name}]`" @click="pickWx(name)"
        >
          <img :src="faceUrlOf(name)" :alt="name" loading="lazy" />
        </button>
      </div>

      <div class="grid-wrap">
        <div v-if="tab === 'wx'" class="grid" role="listbox" aria-label="微信表情">
          <button
            v-for="name in WX_FACES" :key="name" type="button" class="cell"
            :title="`[${name}]`" @click="pickWx(name)"
          >
            <img :src="faceUrlOf(name)" :alt="name" loading="lazy" />
          </button>
        </div>
        <div v-else class="grid" role="listbox" aria-label="Emoji">
          <button
            v-for="ch in UNICODE_EMOJIS" :key="ch" type="button" class="cell u-cell"
            :title="ch" @click="pickUnicode(ch)"
          >{{ ch }}</button>
        </div>
      </div>
    </div>
  </transition>
</template>

<style scoped>
.picker {
  position: absolute;
  left: 0;
  right: 0;
  bottom: calc(100% + 8px);
  height: 288px;
  display: flex;
  flex-direction: column;
  background: var(--c-panel);
  border: 1px solid var(--c-border);
  border-radius: var(--r-lg);
  box-shadow: 0 8px 28px rgba(23, 35, 58, 0.14);
  overflow: hidden;
}
.panel-enter-active, .panel-leave-active { transition: opacity 0.15s ease, transform 0.15s ease; }
.panel-enter-from, .panel-leave-to { opacity: 0; transform: translateY(8px); }

.tabs { display: flex; align-items: center; gap: 4px; padding: 8px 10px 0; border-bottom: 1px solid var(--c-border); }
.tab {
  border: none; background: none; cursor: pointer;
  font-family: var(--font-ui); font-size: 13px; color: var(--c-text-sub);
  padding: 6px 12px; border-radius: var(--r-md) var(--r-md) 0 0;
  border-bottom: 2px solid transparent;
  transition: color 0.15s;
}
.tab:hover { color: var(--c-text); }
.tab.on { color: var(--c-primary); border-bottom-color: var(--c-primary); font-weight: 600; }
.count { margin-left: auto; font-size: 11px; color: var(--c-text-sub); }

.recents {
  display: flex; align-items: center; gap: 2px;
  padding: 5px 10px;
  border-bottom: 1px dashed var(--c-border);
  background: var(--c-surface);
  overflow: hidden;
}
.r-label { flex-shrink: 0; font-size: 11px; color: var(--c-text-sub); margin-right: 6px; }
.r-cell { background: none; }

.grid-wrap { flex: 1; overflow-y: auto; padding: 6px; }
.grid { display: grid; grid-template-columns: repeat(9, 1fr); }
.cell {
  width: 36px; height: 36px; padding: 4px;
  display: flex; align-items: center; justify-content: center;
  border: none; border-radius: var(--r-sm); background: none; cursor: pointer;
  transition: background 0.12s;
}
.cell:hover { background: var(--c-primary-soft); }
.cell img { width: 26px; height: 26px; }
.u-cell { font-size: 22px; font-family: 'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', sans-serif; }
</style>
