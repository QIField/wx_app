<script setup>
/** 跨组织设备选择器：从设备字典勾选关联设备（多账号可共用同一台，不做互斥）。
 * v-model 为设备 id 数组，整体替换语义由调用方提交 device_ids 承接。 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps({
  devices: { type: Array, default: () => [] }, // 设备字典（含 bound_users）
  orgs: { type: Array, default: () => [] },    // 启用中组织（筛选用）
  disabled: { type: Boolean, default: false },
})
const model = defineModel({ type: Array, default: () => [] })

const open = ref(false)
const kw = ref('')
const org = ref('')
const root = ref(null)

const selected = computed(() => model.value)

const boxText = computed(() =>
  selected.value.length ? `已选 ${selected.value.length} 台设备 · 点击调整` : '从设备库选择（可跨组织）')

const filtered = computed(() => {
  const k = kw.value.trim().toLowerCase()
  return props.devices.filter((d) => {
    if (org.value && d.org_id !== Number(org.value)) return false
    if (k && !`${d.name} ${d.openid} ${d.org_name}`.toLowerCase().includes(k)) return false
    return true
  })
})

const usedCount = (d) => (d.bound_users || []).length
const nameOf = (id) => {
  const d = props.devices.find((x) => x.id === id)
  return d ? (d.name || d.openid) : `#${id}`
}

function toggleOne(id) {
  model.value = selected.value.includes(id)
    ? selected.value.filter((x) => x !== id)
    : [...selected.value, id]
}

function removeOne(id) {
  model.value = selected.value.filter((x) => x !== id)
}

function onDocClick(e) {
  if (root.value && !root.value.contains(e.target)) open.value = false
}
onMounted(() => document.addEventListener('click', onDocClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocClick))
</script>

<template>
  <div ref="root" class="picker">
    <button type="button" class="picker-box" :disabled="disabled" @click="open = !open">
      <span class="picker-box-text">{{ boxText }}</span>
      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
    </button>
    <div v-if="open" class="picker-panel">
      <div class="picker-search">
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
        <input v-model="kw" type="text" placeholder="搜索设备名称 / ID">
      </div>
      <div class="picker-orgs">
        <button type="button" class="pchip" :class="{ on: org === '' }" @click="org = ''">全部组织</button>
        <button v-for="o in orgs" :key="o.id" type="button" class="pchip"
                :class="{ on: org === String(o.id) }" @click="org = String(o.id)">{{ o.name }}</button>
      </div>
      <div class="picker-list">
        <button v-for="d in filtered" :key="d.id" type="button" class="pitem"
                :class="{ sel: selected.includes(d.id) }" @click="toggleOne(d.id)">
          <span class="pi-check">
            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
          </span>
          <span class="pi-main">
            <span class="pi-name">{{ d.name || d.openid }}</span>
            <span class="pi-sub num">{{ d.openid }}{{ usedCount(d) ? ` · ${usedCount(d)} 个账号共用` : '' }}</span>
          </span>
          <span class="pi-side">
            <span class="tag tag-blue">{{ d.org_name || '未分配' }}</span>
            <span v-if="usedCount(d)" class="pi-used">已有 {{ usedCount(d) }} 个账号关联</span>
          </span>
        </button>
        <div v-if="!filtered.length" class="empty" style="padding:18px 0;"><span>没有符合条件的设备</span></div>
      </div>
      <div class="picker-foot">设备可跨组织选择、多账号共用 · 解除关联不影响他人</div>
    </div>
    <div v-if="selected.length" class="picker-chips">
      <span v-for="id in selected" :key="id" class="sel-chip">
        {{ nameOf(id) }}
        <button type="button" class="chip-x" title="移除" @click="removeOne(id)">
          <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
        </button>
      </span>
    </div>
  </div>
</template>

<style scoped>
.picker-box {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  width: 100%; padding: 9px 12px; font-size: 13px; color: var(--c-text);
  border: 1px solid var(--c-border); border-radius: var(--r-md); background: #fafbfd;
  cursor: pointer; transition: border-color 0.15s, background 0.15s;
}
.picker-box:hover:not(:disabled) { border-color: var(--c-primary); background: var(--c-primary-soft); }
.picker-box:disabled { cursor: not-allowed; color: var(--c-text-sub); }
.picker-box-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.picker-panel {
  /* 弹窗表单内使用：内联展开而非下拉浮层，避免被 modal-body 的 overflow:auto 裁剪 */
  margin-top: 6px;
  background: #fff; border: 1px solid var(--c-border); border-radius: var(--r-md);
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.08); padding: 10px;
}
.picker-search {
  display: flex; align-items: center; gap: 6px; padding: 6px 10px;
  border: 1px solid var(--c-border); border-radius: var(--r-md); color: var(--c-text-sub);
}
.picker-search input { flex: 1; min-width: 0; border: none; outline: none; background: none; font-size: 13px; color: var(--c-text); }
.picker-orgs { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 8px; }
.pchip {
  padding: 3px 10px; font-size: 12px; border: 1px solid var(--c-border);
  border-radius: 999px; background: #fff; color: var(--c-text-sub); cursor: pointer;
}
.pchip.on { background: var(--c-primary-soft); border-color: var(--c-primary); color: var(--c-primary-deep); }

.picker-list { max-height: 240px; overflow-y: auto; margin-top: 8px; }
.pitem {
  display: flex; align-items: center; gap: 8px; width: 100%;
  padding: 8px 10px; border: none; border-radius: var(--r-md);
  background: none; cursor: pointer; text-align: left;
}
.pitem:hover { background: #f5f7fb; }
.pitem.sel { background: var(--c-primary-soft); }
.pi-check {
  width: 16px; height: 16px; flex-shrink: 0; border: 1.5px solid var(--c-border-strong);
  border-radius: 4px; display: flex; align-items: center; justify-content: center; color: #fff;
}
.pitem.sel .pi-check { background: var(--c-primary); border-color: var(--c-primary); }
.pi-main { flex: 1; min-width: 0; line-height: 1.35; }
.pi-name { display: block; font-size: 13px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pi-sub { display: block; font-size: 11px; color: var(--c-text-sub); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pi-side { display: flex; flex-direction: column; align-items: flex-end; gap: 3px; flex-shrink: 0; }
.pi-used { font-size: 11px; color: var(--c-warn); }
.picker-foot { margin-top: 8px; padding-top: 8px; border-top: 1px dashed var(--c-border); font-size: 11px; color: var(--c-text-sub); }

.picker-chips { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 8px; }
.sel-chip {
  display: inline-flex; align-items: center; gap: 4px; padding: 3px 6px 3px 10px;
  font-size: 12px; background: var(--c-primary-soft); color: var(--c-primary-deep);
  border: 1px solid var(--c-primary); border-radius: 999px;
}
.chip-x {
  display: flex; align-items: center; justify-content: center; width: 16px; height: 16px;
  border: none; border-radius: 50%; background: none; color: inherit; cursor: pointer;
}
.chip-x:hover { background: rgba(15, 23, 42, 0.12); }
</style>
