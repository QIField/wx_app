<script setup>
/** 我的自定义铃声：上传入口（格式/大小预校验）+ 列表展示 + 删除管理。
 *  列表拉取后写入 ringtones 内存缓存并校正当前铃声（refreshRingtone）；
 *  试听/选中经事件上抛，由设置弹窗统一调度（复用互斥与复位逻辑）。
 *  删除用「再点一次确认」防误触，不引确认弹窗依赖。 */
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { deleteRingtone, fetchRingtones, uploadRingtone } from '../api'
import { setCustomRingtones } from '../utils/ringtones'
import { refreshRingtone } from '../utils/notify'

const props = defineProps({
  current: { type: String, default: '' }, // 当前选中铃声 id（含 custom: 前缀）
  previewingId: { type: String, default: '' }, // 正在试听的铃声 id
})
const emit = defineEmits(['preview', 'select', 'deleted'])

const ALLOWED_EXTS = ['mp3', 'm4a', 'wav', 'ogg']
const MAX_BYTES = 5 * 1024 * 1024

const rows = ref([]) // 后端行数组（裸 id，展示用；选择时拼 cid）
const uploading = ref(false)
const pendingDelId = ref('') // 待二次确认删除的行 id
let delConfirmTimer = null

const fileInput = ref(null)

onMounted(load)

/** 拉取列表 → 写铃声缓存 → 校正当前铃声（存的自定义铃声被删时回退默认）。 */
async function load() {
  try {
    const data = await fetchRingtones()
    rows.value = data || []
    setCustomRingtones(rows.value)
    refreshRingtone()
  } catch (e) {
    ElMessage.error(e.message || '自定义铃声加载失败')
  }
}

/** 触发文件选择（隐藏 input）。 */
function pickFile() {
  fileInput.value?.click()
}

/** 上传前预校验：扩展名 + 大小；不通过直接提示，不发请求。 */
function onFileChange(e) {
  const file = e.target.files?.[0]
  e.target.value = '' // 复位，允许重选同一个文件
  if (!file) return
  const ext = (file.name.split('.').pop() || '').toLowerCase()
  if (!ALLOWED_EXTS.includes(ext)) {
    ElMessage.error('不支持的格式，仅支持 MP3、M4A、WAV、OGG')
    return
  }
  if (file.size > MAX_BYTES) {
    ElMessage.error('铃声文件超过 5MB 上限')
    return
  }
  doUpload(file)
}

async function doUpload(file) {
  uploading.value = true
  try {
    const row = await uploadRingtone(file)
    ElMessage.success(`铃声「${row.name}」上传成功`)
    await load()
  } catch (e) {
    ElMessage.error(e.message || '上传失败，请重试')
  } finally {
    uploading.value = false
  }
}

/** 删除：第一次点进入确认态（3 秒超时自动取消），再点才真删。 */
function onRemove(row) {
  if (pendingDelId.value !== row.id) {
    pendingDelId.value = row.id
    if (delConfirmTimer) clearTimeout(delConfirmTimer)
    delConfirmTimer = setTimeout(() => { pendingDelId.value = '' }, 3000)
    return
  }
  clearTimeout(delConfirmTimer)
  delConfirmTimer = null
  pendingDelId.value = ''
  doDelete(row)
}

async function doDelete(row) {
  try {
    await deleteRingtone(row.id)
    ElMessage.success(`已删除铃声「${row.name}」`)
    emit('deleted', row.cid)
    await load()
  } catch (e) {
    ElMessage.error(e.message || '删除失败，请重试')
  }
}

/** 字节数 → 展示尺寸。 */
function fmtSize(n) {
  if (n >= 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)}MB`
  if (n >= 1024) return `${Math.round(n / 1024)}KB`
  return `${n}B`
}
</script>

<template>
  <div class="custom-sec">
    <div class="sec-head">
      <span>我的自定义铃声</span>
      <button class="upload-btn" :disabled="uploading" @click="pickFile">
        <svg v-if="!uploading" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14"/><path d="M5 12h14"/></svg>
        <span v-else class="spin" />
        {{ uploading ? '上传中…' : '上传铃声' }}
      </button>
      <input ref="fileInput" type="file" accept=".mp3,.m4a,.wav,.ogg,audio/*" hidden @change="onFileChange">
    </div>

    <ul v-if="rows.length" class="ring-list">
      <li v-for="r in rows" :key="r.id" class="ring-row" :class="{ playing: previewingId === r.cid }">
        <label class="pick" title="设为消息提示音">
          <input
            type="radio"
            name="ringtone"
            :value="r.cid"
            :checked="current === r.cid"
            @change="emit('select', r.cid)"
          >
          <span class="radio-ui"></span>
        </label>
        <div class="meta">
          <div class="name">
            {{ r.name }}
            <span v-if="current === r.cid" class="tag cur">当前</span>
          </div>
          <div class="desc">{{ r.fmt.toUpperCase() }} · {{ fmtSize(r.size) }}</div>
        </div>
        <button class="play" @click="emit('preview', r.cid)">
          <span class="wave"><i /><i /><i /><i /></span>
          <svg v-if="previewingId !== r.cid" width="12" height="12" viewBox="0 0 24 24" fill="currentColor" stroke="none"><polygon points="6 3 20 12 6 21 6 3"/></svg>
          <svg v-else width="12" height="12" viewBox="0 0 24 24" fill="currentColor" stroke="none"><rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/></svg>
          {{ previewingId === r.cid ? '停止' : '试听' }}
        </button>
        <button
          class="del"
          :class="{ confirm: pendingDelId === r.id }"
          :title="pendingDelId === r.id ? '再次点击确认删除' : '删除'"
          @click="onRemove(r)"
        >
          {{ pendingDelId === r.id ? '确认删除' : '删除' }}
        </button>
      </li>
    </ul>
    <p v-else class="empty">还没有自定义铃声，点击右上角「上传铃声」添加</p>
  </div>
</template>

<style scoped>
.custom-sec { margin-top: 10px; padding-top: 10px; border-top: 1px dashed var(--c-border); }
.sec-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 8px;
  user-select: none;
}
.sec-head span { font-size: 12px; font-weight: 600; color: var(--c-text-sub); letter-spacing: 1px; }
.upload-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 24px;
  padding: 0 8px;
  font-size: 11px;
  color: var(--c-primary);
  background: none;
  border: 1px solid var(--c-primary);
  border-radius: var(--r-md);
  cursor: pointer;
  user-select: none;
  transition: background 0.15s;
}
.upload-btn:hover { background: var(--c-primary-soft); }
.upload-btn:disabled { opacity: 0.6; cursor: default; }
.spin {
  width: 10px;
  height: 10px;
  border: 1.5px solid var(--c-primary);
  border-top-color: transparent;
  border-radius: 50%;
  animation: sp 0.7s linear infinite;
}
@keyframes sp { to { transform: rotate(360deg); } }

.ring-list { list-style: none; margin: 0; padding: 0; }
.ring-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 8px;
  border-radius: var(--r-md);
  user-select: none;
  transition: background 0.15s;
}
.ring-row:hover { background: #f7f9fc; }

.pick { display: flex; align-items: center; cursor: pointer; flex-shrink: 0; }
.pick input { position: absolute; opacity: 0; width: 0; height: 0; }
.radio-ui {
  display: block;
  width: 16px;
  height: 16px;
  border: 1.5px solid var(--c-border-strong);
  border-radius: 50%;
  position: relative;
  transition: border-color 0.15s;
}
.pick:hover .radio-ui { border-color: var(--c-primary); }
.pick input:checked + .radio-ui { border-color: var(--c-primary); }
.pick input:checked + .radio-ui::after {
  content: '';
  position: absolute;
  inset: 3px;
  background: var(--c-primary);
  border-radius: 50%;
}

.meta { flex: 1; min-width: 0; }
.name { font-size: 13px; font-weight: 600; display: flex; align-items: center; gap: 6px; }
.desc { font-size: 11px; color: var(--c-text-sub); margin-top: 2px; }
.tag {
  font-size: 10px;
  font-weight: 400;
  letter-spacing: 0.5px;
  border-radius: 3px;
  padding: 0.5px 6px;
  flex-shrink: 0;
}
.tag.cur { color: var(--c-primary); background: var(--c-primary-soft); border: 1px solid #c9dcff; }

.play {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-width: 74px;
  height: 30px;
  flex-shrink: 0;
  padding: 0 10px;
  font-size: 12px;
  white-space: nowrap;
  color: var(--c-text-sub);
  background: var(--c-bg);
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
  cursor: pointer;
  user-select: none;
  transition: color 0.15s, border-color 0.15s, background 0.15s;
}
.play:hover { color: var(--c-primary); border-color: var(--c-primary); background: var(--c-primary-soft); }
.wave { display: none; align-items: flex-end; gap: 2px; height: 14px; }
.wave i { width: 3px; border-radius: 1px; background: var(--c-primary); animation: wv 0.7s ease-in-out infinite; }
.wave i:nth-child(1) { height: 6px; }
.wave i:nth-child(2) { height: 12px; animation-delay: 0.15s; }
.wave i:nth-child(3) { height: 8px; animation-delay: 0.3s; }
.wave i:nth-child(4) { height: 13px; animation-delay: 0.45s; }
@keyframes wv { 0%, 100% { transform: scaleY(0.4); } 50% { transform: scaleY(1); } }
.ring-row.playing .wave { display: flex; }
.ring-row.playing .play { color: var(--c-primary); border-color: var(--c-primary); background: var(--c-primary-soft); }

.del {
  height: 30px;
  flex-shrink: 0;
  padding: 0 8px;
  font-size: 12px;
  white-space: nowrap;
  color: var(--c-text-sub);
  background: none;
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
  cursor: pointer;
  user-select: none;
  transition: color 0.15s, border-color 0.15s, background 0.15s;
}
.del:hover { color: #d64541; border-color: #d64541; background: #fdf0ef; }
.del.confirm { color: #fff; background: #d64541; border-color: #d64541; }

.empty {
  margin: 0;
  padding: 14px 0 4px;
  font-size: 11px;
  color: var(--c-border-strong);
  text-align: center;
  user-select: none;
}
</style>
