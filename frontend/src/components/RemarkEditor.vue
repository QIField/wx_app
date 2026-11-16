<script setup>
/** 统一备注编辑器：备注名称 + 自动报价开关 + 标签（查看/编辑一体）。
 *  由聊天侧栏（ChatSidePanel）与通讯录详情（ContactDetail）复用，
 *  数据源统一走 remark-config API——同一目标全场景读同一行配置。 */
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  /** (targetKey) => Promise<config> */
  fetch: { type: Function, required: true },
  /** (targetKey, payload) => Promise<config> */
  save: { type: Function, required: true },
  /** 目标条目 id：变化即重载（切换联系人/群/群成员） */
  targetKey: { type: [String, Number], default: '' },
})
const emit = defineEmits(['saved'])

const loading = ref(false)
const loadErr = ref('')
const cfg = ref(null)
const editing = ref(false)
const saving = ref(false)
const err = ref('')
const draftName = ref('')
const draftQuote = ref(false)
const draftTags = ref([])
const tagInput = ref('')

async function load() {
  if (!props.targetKey) { cfg.value = null; return }
  loading.value = true
  loadErr.value = ''
  try {
    cfg.value = await props.fetch(props.targetKey)
  } catch (e) {
    cfg.value = null
    loadErr.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

watch(() => props.targetKey, () => {
  editing.value = false
  err.value = ''
  load()
}, { immediate: true })

function startEdit() {
  draftName.value = cfg.value?.remark_name || ''
  draftQuote.value = !!cfg.value?.auto_quote_enabled
  draftTags.value = [...(cfg.value?.tags || [])]
  tagInput.value = ''
  err.value = ''
  editing.value = true
}

function addTag() {
  const t = tagInput.value.trim()
  if (!t) return
  if (t.length > 12) { err.value = '单个标签不能超过 12 字'; return }
  if (draftTags.value.length >= 10) { err.value = '标签最多 10 个'; return }
  if (!draftTags.value.includes(t)) draftTags.value.push(t)
  tagInput.value = ''
  err.value = ''
}

function removeTag(i) {
  draftTags.value.splice(i, 1)
  err.value = ''
}

async function saveEdit() {
  if (draftName.value.trim().length > 100) {
    err.value = '备注不能超过 100 字'
    return
  }
  saving.value = true
  try {
    cfg.value = await props.save(props.targetKey, {
      remark_name: draftName.value.trim(),
      auto_quote_enabled: draftQuote.value,
      tags: [...draftTags.value],
    })
    editing.value = false
    emit('saved', cfg.value)
    ElMessage.success('备注设置已保存')
  } catch (e) {
    err.value = e.message || '保存失败'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="rk">
    <div v-if="loading" class="rk-state">加载中…</div>
    <div v-else-if="loadErr" class="rk-state">{{ loadErr }}</div>

    <template v-else-if="cfg">
      <!-- 查看态 -->
      <template v-if="!editing">
        <div class="rk-row"><span class="k">备注名称</span><span :class="{ dim: !cfg.remark_name }">{{ cfg.remark_name || '暂无备注' }}</span></div>
        <div class="rk-row">
          <span class="k">自动报价</span>
          <span class="quote-chip" :class="{ on: cfg.auto_quote_enabled }">{{ cfg.auto_quote_enabled ? '已开启' : '未开启' }}</span>
        </div>
        <div class="rk-row">
          <span class="k">标签</span>
          <span class="tag-list">
            <span v-for="t in cfg.tags" :key="t" class="chip">{{ t }}</span>
            <span v-if="!cfg.tags.length" class="dim">暂无标签</span>
          </span>
        </div>
        <div class="rk-actions">
          <el-button size="small" type="primary" plain @click="startEdit">编辑</el-button>
        </div>
      </template>

      <!-- 编辑态 -->
      <template v-else>
        <div class="rk-edit">
          <input
            v-model="draftName"
            class="rk-input"
            placeholder="备注名称（≤100 字）"
            maxlength="100"
          >
          <div class="rk-quote">
            <span class="q-label">自动报价</span>
            <el-switch v-model="draftQuote" />
          </div>
          <div class="rk-edit-row">
            <span class="tag-list">
              <span v-for="(t, i) in draftTags" :key="t" class="chip">
                {{ t }}<button class="chip-x" title="删除标签" @click="removeTag(i)">×</button>
              </span>
              <span v-if="!draftTags.length" class="dim">暂无标签</span>
            </span>
          </div>
          <div class="rk-edit-row">
            <input
              v-model="tagInput"
              class="rk-input"
              placeholder="输入标签后回车添加（≤12 字）"
              @keydown.enter.prevent="addTag"
            >
            <span class="cnt num">{{ draftTags.length }}/10</span>
          </div>
          <div class="rk-actions">
            <el-button size="small" type="primary" :loading="saving" @click="saveEdit">保存</el-button>
            <el-button size="small" @click="editing = false">取消</el-button>
            <span v-if="err" class="rk-err">{{ err }}</span>
          </div>
        </div>
      </template>
    </template>
  </div>
</template>

<style scoped>
/* 纯点选/展示场景禁止划选；输入框保留可选中文本 */
.rk { padding: 12px 16px; user-select: none; font-size: 12.5px; }
.rk input { user-select: text; }

.rk-row {
  display: flex; gap: 12px; align-items: flex-start;
  padding: 6px 0;
  border-bottom: 1px dashed #eef1f6;
}
.rk-row:last-of-type { border-bottom: none; }
.k { width: 60px; flex-shrink: 0; color: var(--c-text-sub); }
.dim { color: var(--c-text-sub); }

.quote-chip {
  font-size: 11px; line-height: 20px; padding: 0 8px; border-radius: 3px;
  background: #f1f3f7; color: var(--c-text-sub); border: 1px solid var(--c-border);
}
.quote-chip.on { background: #e8f7ee; color: #1a7f4b; border-color: #b5e3c9; }

.tag-list { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; min-width: 0; }
.chip {
  display: inline-flex; align-items: center; gap: 3px;
  font-size: 11px; line-height: 20px; padding: 0 8px; border-radius: 3px;
  background: var(--c-primary-soft); color: var(--c-primary-deep);
  border: 1px solid #b9d0ff;
}
.chip-x {
  border: none; background: none; cursor: pointer;
  font-size: 13px; line-height: 1; color: var(--c-primary-deep); padding: 0; opacity: 0.6;
}
.chip-x:hover { opacity: 1; color: var(--c-danger); }

.rk-actions { display: flex; align-items: center; gap: 8px; padding-top: 10px; }
.rk-err { font-size: 11.5px; color: var(--c-warn); }

.rk-edit-row { display: flex; align-items: center; gap: 8px; padding: 6px 0; }
.rk-input {
  flex: 1; min-width: 0; height: 28px; padding: 0 8px;
  border: 1px solid var(--c-border); border-radius: var(--r-sm);
  font-family: inherit; font-size: 12.5px; color: var(--c-text);
  outline: none; background: #fff;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.rk-input:focus { border-color: var(--c-primary); box-shadow: 0 0 0 2px rgba(29, 93, 228, 0.12); }
.cnt { font-size: 11px; color: var(--c-text-sub); flex-shrink: 0; }

.rk-quote { display: flex; align-items: center; gap: 8px; padding: 8px 0; }
.q-label { font-size: 12.5px; }

.rk-state { padding: 16px 0; color: var(--c-text-sub); font-size: 12px; }
</style>
