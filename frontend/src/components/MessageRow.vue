<script setup>
/** 单条消息行：文本气泡 / 图片语音视频 / 链接文件卡片 / 微信样式系统灰条。
 *
 * 灰条三类来源：撤回通知（自己撤回的可"重新编辑"）、后端兜底系统行、
 * 残留的微信系统 XML（拍一拍等）。图片点击交给父组件做全屏预览。
 */
import { computed } from 'vue'
import { getToken } from '../api'
import { appInfoOf, canReEdit, fileTitleOf, hostOf, isSystemXml } from '../utils/message'

const props = defineProps({
  msg: { type: Object, required: true }, // timeline 展开后的单条消息
  conv: { type: Object, default: null }, // 当前会话（头像/昵称取值用）
})
const emit = defineEmits(['preview', 'reedit'])

const STATUS_LABEL = { 0: '发送中', 1: '已发送', 2: '失败' }

/* 媒体地址：<img>/<audio>/<video> 带不了 Authorization 头，统一走 ?token= 兜底 */
function mediaUrl(m) {
  return `/api/messages/${m.id}/media?token=${encodeURIComponent(getToken())}`
}

/* 行头像：in=客户（群消息取发言人首字，单聊取会话名首字）；out=客服 */
function avatarOf(m) {
  if (m.direction === 2) return '客'
  const s = props.conv?.chat_type === 2 ? (m.sender_name || '客') : (props.conv?.name || props.conv?.wxid || '?')
  return s.slice(0, 1).toUpperCase()
}

/* 入方向消息的微信头像：单聊取会话头像，群聊取发言人头像（无则首字兜底） */
function picOf(m) {
  if (m.direction === 2) return null
  if (props.conv?.chat_type === 2) return m.sender_avatar || null
  return props.conv?.avatar || null
}
function nameOf(m) {
  if (m.direction === 2) return '客服'
  return props.conv?.chat_type === 2 ? (m.sender_name || '成员') : (props.conv?.name || props.conv?.wxid)
}

/* 系统灰条判断：撤回标记 / 兜底系统行 / 残留系统 XML */
const isSys = computed(
  () => props.msg.payload?.revoked || props.msg.payload?.system || isSystemXml(props.msg)
)

/* 灰条文案：与微信一致（"你撤回了一条消息"/"「昵称」撤回了一条消息"） */
const sysText = computed(() => {
  const m = props.msg
  if (m.payload?.system) return m.content || '[系统消息]'
  if (m.payload?.revoked) {
    if (m.direction === 2) return '你撤回了一条消息'
    const who = props.conv?.chat_type === 2 ? `「${m.sender_name || '成员'}」` : '对方'
    return `${who}撤回了一条消息`
  }
  return '[系统消息]'
})

/* 仅自己发的纯文本撤回后可重新编辑（微信同款限制） */
const showReEdit = computed(() => canReEdit(props.msg))

/* 链接/文件卡片信息（payload.app 优先，旧数据前端解析 XML 兜底） */
const app = computed(() => (props.msg.msg_type === 5 ? appInfoOf(props.msg) : {}))
const fileTitle = computed(() => (props.msg.msg_type === 3 ? fileTitleOf(props.msg) : ''))

/* 图片/表情/视频撑满气泡：去掉内边距（微信样式） */
const isTight = computed(() => [2, 4, 7].includes(props.msg.msg_type))

function onReEdit() {
  emit('reedit', props.msg.content)
}
</script>

<template>
  <!-- 系统灰条：居中一行，微信撤回样式 -->
  <div v-if="isSys" class="sysline">
    <span>{{ sysText }}</span>
    <a v-if="showReEdit" class="re-edit" href="#" @click.prevent="onReEdit">重新编辑</a>
  </div>

  <div v-else class="msg" :class="msg.direction === 2 ? 'out' : 'in'">
    <img v-if="picOf(msg)" class="avatar img" :src="picOf(msg)" alt="" referrerpolicy="no-referrer" />
    <span v-else class="avatar" :class="msg.direction === 2 ? 'agent' : 'client'">{{ avatarOf(msg) }}</span>
    <div class="body">
      <div class="name">{{ nameOf(msg) }}</div>
      <div class="bubble" :class="{ tight: isTight }">
        <img
          v-if="msg.msg_type === 2"
          class="media img"
          :src="mediaUrl(msg)"
          alt="图片消息"
          title="点击查看大图"
          referrerpolicy="no-referrer"
          @click="emit('preview', mediaUrl(msg))"
        />
        <audio v-else-if="msg.msg_type === 6" class="media audio" :src="mediaUrl(msg)" controls preload="none"></audio>
        <video v-else-if="msg.msg_type === 4" class="media video" :src="mediaUrl(msg)" controls preload="metadata"></video>
        <img v-else-if="msg.msg_type === 7" class="media emoji" :src="mediaUrl(msg)" alt="表情" referrerpolicy="no-referrer" />

        <!-- 文件卡片：图标 + 文件名 + 下载 -->
        <a v-else-if="msg.msg_type === 3" class="file-card" :href="mediaUrl(msg)" download>
          <span class="badge">文件</span>
          <span class="fc-main">
            <span class="fc-title">{{ fileTitle }}</span>
            <span class="fc-sub">点击下载</span>
          </span>
        </a>

        <!-- 链接卡片：标题 + 摘要 + 域名 -->
        <a
          v-else-if="msg.msg_type === 5 && app.url"
          class="link-card"
          :href="app.url"
          target="_blank"
          rel="noopener"
        >
          <span class="lc-title">{{ app.title || '[链接]' }}</span>
          <span v-if="app.desc" class="lc-desc">{{ app.desc }}</span>
          <span class="lc-host"><span class="badge">链接</span><span class="host">{{ hostOf(app.url) }}</span></span>
        </a>
        <div v-else-if="msg.msg_type === 5" class="content type-label">[链接]</div>

        <div v-else-if="msg.msg_type !== 1" class="content type-label">[未知类型]</div>
        <div v-else class="content">{{ msg.content }}</div>

        <div class="meta">
          <span v-if="msg.direction === 2" :class="['st', { fail: msg.status === 2 }]">{{ STATUS_LABEL[msg.status] }}</span>
          <span class="num">{{ msg.create_time?.slice(11, 16) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sysline {
  text-align: center;
  margin: 10px 0;
  font-size: 12px;
  color: var(--c-text-sub);
}
.re-edit { margin-left: 8px; color: var(--c-primary); }
.re-edit:hover { text-decoration: underline; }

.msg { display: flex; gap: 8px; margin-bottom: 12px; animation: pop 0.22s both; }
@keyframes pop {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: none; }
}
.msg.out { flex-direction: row-reverse; }

.avatar {
  width: 30px; height: 30px; flex-shrink: 0;
  border-radius: var(--r-sm);
  color: #fff; font-size: 13px; font-weight: 600;
  display: flex; align-items: center; justify-content: center;
  margin-top: 16px;
}
.avatar.client { background: var(--c-ok); }
.avatar.agent { background: var(--c-primary); }
.avatar.img { object-fit: cover; background: var(--c-surface); }

.body { max-width: 72%; min-width: 0; display: flex; flex-direction: column; }
.msg.out .body { align-items: flex-end; }
.name { font-size: 11px; color: var(--c-text-sub); margin-bottom: 2px; user-select: none; }

.bubble {
  padding: 7px 10px;
  border-radius: var(--r-lg);
  background: var(--c-panel);
  border: 1px solid var(--c-border);
  width: fit-content;
}
.msg.in .bubble { border-top-left-radius: 3px; }
.msg.out .bubble { background: var(--c-primary-soft); border-color: #c9dbff; border-top-right-radius: 3px; }
/* 媒体气泡：图片贴边（微信样式） */
.bubble.tight { padding: 2px; overflow: hidden; }

/* 媒体消息：图片/表情/语音/视频直接渲染 */
.media { display: block; }
.media.img { max-width: 200px; max-height: 200px; border-radius: var(--r-sm); cursor: zoom-in; }
.media.emoji { width: 120px; }
.media.audio { width: 240px; height: 36px; }
.media.video { max-width: 240px; border-radius: var(--r-sm); }

/* 链接/文件卡片 */
.link-card, .file-card {
  display: flex; flex-direction: column; gap: 4px;
  width: 200px; padding: 10px;
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
  background: #fff;
  color: var(--c-text); text-decoration: none;
  transition: border-color 0.15s;
}
.link-card:hover, .file-card:hover { border-color: var(--c-primary); }
.file-card { flex-direction: row; align-items: center; gap: 8px; }
.badge {
  flex-shrink: 0;
  font-size: 10px; color: var(--c-primary);
  background: var(--c-primary-soft);
  border-radius: 3px; padding: 1px 5px;
}
.fc-main { display: flex; flex-direction: column; min-width: 0; }
.fc-title { font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fc-sub { font-size: 11px; color: var(--c-text-sub); }
.lc-title {
  font-size: 13px; font-weight: 600; line-height: 1.4;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.lc-desc {
  font-size: 12px; color: var(--c-text-sub); line-height: 1.4;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.lc-host { font-size: 11px; color: var(--c-text-sub); display: flex; align-items: center; gap: 6px; min-width: 0; }
.lc-host .host { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.content { white-space: pre-wrap; word-break: break-word; line-height: 1.55; }
.type-label { color: var(--c-primary); }
.meta {
  margin-top: 3px; font-size: 10px; color: var(--c-text-sub);
  display: flex; gap: 8px; justify-content: flex-end;
}
.st.fail { color: var(--c-danger); font-weight: 600; }
</style>
