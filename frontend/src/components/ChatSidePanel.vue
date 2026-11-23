<script setup>
/** 聊天右侧「客户资料」侧栏：头部信息 + 统一备注编辑器。
 *  由 ChatPanel 触发展开（点头像 / 顶部备注名），收起走头部按钮或 Esc；
 *  群成员目标时展示所属群来源，配置仍为该用户的用户级（全局生效）。 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import ContactAvatar from './ContactAvatar.vue'
import RemarkEditor from './RemarkEditor.vue'

const props = defineProps({
  /** { key, apiId, title, subtitle, alias, avatar, chatType, fetch, save, fromGroup, _convId } */
  target: { type: Object, required: true },
})
const emit = defineEmits(['close', 'saved'])

function onKey(e) {
  if (e.key === 'Escape') emit('close')
}
onMounted(() => window.addEventListener('keydown', onKey))
onUnmounted(() => window.removeEventListener('keydown', onKey))

</script>

<template>
  <aside class="rk-side">
    <div class="rk-head">
      <ContactAvatar
        :name="target.title"
        :alias="target.alias"
        :avatar="target.avatar"
        :chat-type="target.chatType"
        class="rk-ava"
      />
      <div class="rk-title">
        <div class="rk-name">{{ target.title }}</div>
        <!-- 脱敏契约：展示匿名标识，不出现 wxid -->
        <div v-if="target.subtitle" class="rk-sub num">{{ target.subtitle }}</div>
      </div>
      <button class="rk-collapse" title="收起" aria-label="收起资料侧栏" @click="emit('close')">
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m15 18-6-6 6-6"/></svg>
      </button>
    </div>

    <div class="rk-body">
      <div v-if="target.fromGroup" class="rk-from">来自群聊成员</div>
      <RemarkEditor
        :key="target.key"
        :fetch="target.fetch"
        :save="target.save"
        :target-key="target.apiId"
        @saved="emit('saved', $event)"
      />
    </div>
  </aside>
</template>

<style scoped>
.rk-side {
  width: 300px; flex-shrink: 0;
  height: 100%;
  display: flex; flex-direction: column;
  overflow: hidden;
  border-left: 1px solid var(--c-border);
  background: var(--c-panel);
  user-select: none;
}
.rk-side input { user-select: text; }

.rk-head {
  display: flex; align-items: center; gap: 12px;
  padding: 16px 14px;
  border-bottom: 1px solid var(--c-border);
  background: linear-gradient(180deg, #fafbfd, #fff);
}
.rk-ava {
  width: 44px; height: 44px; flex-shrink: 0;
  border-radius: var(--r-md);
  background: var(--c-primary);
  color: #fff; font-size: 17px; font-weight: 600;
  display: flex; align-items: center; justify-content: center;
}
.rk-ava.group { background: var(--c-ok); }
.rk-title { flex: 1; min-width: 0; }
.rk-name { font-size: 15px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rk-sub { margin-top: 3px; font-size: 11px; color: var(--c-text-sub); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rk-collapse {
  flex-shrink: 0;
  width: 26px; height: 26px;
  display: flex; align-items: center; justify-content: center;
  border: 1px solid var(--c-border); border-radius: var(--r-sm);
  background: #fff; color: var(--c-text-sub); cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
}
.rk-collapse:hover { color: var(--c-primary); border-color: var(--c-primary); }

.rk-body { flex: 1; overflow-y: auto; }
.rk-from {
  margin: 10px 16px 0;
  font-size: 11px; color: var(--c-text-sub);
  background: #f5f7fa; border-radius: var(--r-sm);
  padding: 5px 8px;
}

</style>
