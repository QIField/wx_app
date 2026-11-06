<script setup>
/** 单条消息行：文本气泡 / 图片语音视频 / 链接文件卡片 / 微信样式系统灰条。
 *
 * 灰条三类来源：撤回通知（自己撤回的可"重新编辑"）、后端兜底系统行、
 * 残留的微信系统 XML（拍一拍等）。图片点击交给父组件做全屏预览，
 * 气泡右键上抛父层弹操作菜单（复制等，见 ChatPanel）。
 */
import { computed, ref } from 'vue'
import { appInfoOf, canReEdit, fileTitleOf, hostOf, isSystemXml, quoteInfoOf, transferInfoOf } from '../utils/message'
import { renderEmojiHtml } from '../utils/emoji'
import { mediaUrlOf, IMG_BIG, IMG_THUMB } from '../utils/media'
import { displayNameOf } from '../utils/format'
import AnonAvatar from './AnonAvatar.vue'
import TransferCard from './TransferCard.vue'

const props = defineProps({
  msg: { type: Object, required: true }, // timeline 展开后的单条消息
  conv: { type: Object, default: null }, // 当前会话（头像/昵称取值用）
})
const emit = defineEmits(['preview', 'reedit', 'mediaload', 'menu'])

const STATUS_LABEL = { 0: '发送中', 1: '已发送', 2: '失败' }

/* ---------- 头像三态：真实图 / 匿名图标（脱敏契约）/ 首字 ---------- */

/* 入方向是否走匿名图标：单聊会话名未解析，或群发言人无头像（后端已随昵称一并置空） */
function isAnon(m) {
  if (m.direction === 2) return false
  if (props.conv?.chat_type === 2) return !m.sender_avatar
  return !props.conv?.name
}
/* 匿名头像编码：群消息用发言人 alias，单聊用会话 alias */
function anonAlias(m) {
  return props.conv?.chat_type === 2 ? (m.sender_alias || '') : (props.conv?.alias || '')
}

/* 首字兜底：in=客户（群消息取发言人名首字，单聊取会话名首字）；out=操作人姓名首字 */
function avatarOf(m) {
  if (m.direction === 2) return (m.operator_name || '客').slice(0, 1)
  const s = props.conv?.chat_type === 2 ? (m.sender_name || '客') : displayNameOf(props.conv) || '?'
  return s.slice(0, 1).toUpperCase()
}

/* 入方向消息的微信头像：单聊取会话头像，群聊取发言人头像（后端按名称解析与否控制下发） */
function picOf(m) {
  if (m.direction === 2) return null
  if (props.conv?.chat_type === 2) return m.sender_avatar || null
  return props.conv?.avatar || null
}
function nameOf(m) {
  // 出方向显示操作人快照（谁发的这条消息），历史数据回退"客服"
  if (m.direction === 2) return m.operator_name || m.sender_name || '客服'
  return props.conv?.chat_type === 2 ? (m.sender_name || '成员') : displayNameOf(props.conv)
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

/* 转账卡片：只展示 谁向谁转多少钱 + 手机操作提示（卡片本体见 TransferCard.vue）。
 * 转出方/收款方：入方向=客户→我；出方向=操作人→客户 */
const transfer = computed(() => transferInfoOf(props.msg))
const transferFrom = computed(() => nameOf(props.msg))
const transferTo = computed(() =>
  props.msg.direction === 2 ? displayNameOf(props.conv) || '客户' : '我'
)

/* 引用消息：新消息读 payload.quote；历史按链接入库的数据解析 XML 兜底 */
const quote = computed(() => quoteInfoOf(props.msg))

/* 文本消息渲染：[微笑] 等微信表情码 → 内联表情图（先转义防 XSS，未识别码原样显示） */
const contentHtml = computed(() => renderEmojiHtml(props.msg.content))
/* 引用块文本同样走表情渲染（被引用的原消息常含表情码） */
const quoteHtml = computed(() =>
  renderEmojiHtml((quote.value?.name ? `${quote.value.name}：` : '') + (quote.value?.text || '[原消息]'))
)

/* 引用块内的被引用图片：后端解析出原图片消息 id（media_id）才有，
 * 找不到原消息时回退 [图片] 标签 */
const quoteImg = computed(() => {
  const id = quote.value?.media_id
  return id ? mediaUrlOf({ id }, IMG_THUMB) : null
})
function quoteFullUrl() {
  return mediaUrlOf({ id: quote.value.media_id }, IMG_BIG)
}

/* 自己刚发的媒体：payload.path 是本服务上传文件的相对地址，直接用它预览。
   （媒体接口走的是中间方下载链路，只对收到的消息有 XML 参数，发出的消息拉不到） */
const localMedia = computed(() => props.msg.payload?.path || null)

/* 图片/表情/视频撑满气泡：去掉内边距（微信样式） */
const isTight = computed(() => [2, 4, 7].includes(props.msg.msg_type))

/* S2 尺寸预占位：后端下发缩略图宽高（payload.w/h，与原图同比例），按显示上限
 * 换算最终盒子，占位与加载后同尺寸 → 高度零突变。历史消息无宽高返回 null，
 * 走 min 占位 + 浏览器滚动锚定兜底（S1）。 */
function fitBox(w, h, maxW, maxH) {
  const nw = Number(w)
  const nh = Number(h)
  if (!nw || !nh) return null
  const s = Math.min(1, maxW / nw, maxH / nh)
  return { width: `${Math.round(nw * s)}px`, height: `${Math.round(nh * s)}px` }
}
const imgBox = computed(() => fitBox(props.msg.payload?.w, props.msg.payload?.h, 200, 200))
const qBox = computed(() => fitBox(quote.value?.w, quote.value?.h, 180, 120))

/* 媒体加载状态：加载前 shimmer 占位块，加载完淡入（组件按消息 id 复用，状态不串行） */
const loaded = ref(false)
/* 清晰图层（type=2）就绪标记：就绪后交叉淡入盖住缩略图层，无空框 */
const sharpOk = ref(false)
/* @load/@error 共用：坏图也撤占位，避免永远闪 shimmer；并通知父组件重新锚定底部 */
function onMediaOk() {
  if (!loaded.value) {
    loaded.value = true
    emit('mediaload')
  }
}

function onReEdit() {
  emit('reedit', props.msg.content)
}

/* 气泡右键 → 上抛给 ChatPanel 统一弹菜单（菜单状态收口在父层，行组件只报坐标与目标） */
function onMenu(e) {
  emit('menu', { msg: props.msg, x: e.clientX, y: e.clientY })
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
    <AnonAvatar v-else-if="isAnon(msg)" :alias="anonAlias(msg)" class="avatar" />
    <span v-else class="avatar" :class="msg.direction === 2 ? 'agent' : 'client'">{{ avatarOf(msg) }}</span>
    <div class="body">
      <div class="name">{{ nameOf(msg) }}</div>
      <div class="bubble" :class="{ tight: isTight }" :title="msg.create_time" @contextmenu.prevent="onMenu">
        <!-- 两层渐进加载：缩略图（type=3，小图且多已预下载走本地缓存）先画出盖住 shimmer；
             清晰图（type=2）就绪后绝对定位盖上来交叉淡入。全程只有"尺寸框 → 图"两段，无空框 -->
        <span v-if="msg.msg_type === 2" class="ph ph-img" :class="{ on: loaded }" :style="imgBox">
          <img
            class="media img"
            :style="imgBox"
            :src="localMedia || mediaUrlOf(msg, IMG_THUMB)"
            alt="图片消息"
            title="点击查看大图"
            referrerpolicy="no-referrer"
            decoding="async"
            @load="onMediaOk"
            @error="onMediaOk"
            @click="emit('preview', localMedia || mediaUrlOf(msg, IMG_BIG))"
          />
          <img
            v-if="!localMedia"
            class="layer-sharp fade"
            :class="{ ok: sharpOk }"
            :src="mediaUrlOf(msg)"
            alt=""
            referrerpolicy="no-referrer"
            decoding="async"
            @load="sharpOk = true"
          />
        </span>
        <audio v-else-if="msg.msg_type === 6" class="media audio" :src="mediaUrlOf(msg)" controls preload="none"></audio>
        <video v-else-if="msg.msg_type === 4" class="media video" :src="localMedia || mediaUrlOf(msg)" controls preload="metadata" @loadeddata="emit('mediaload')"></video>
        <span v-else-if="msg.msg_type === 7" class="ph ph-emoji" :class="{ on: loaded }">
          <img
            class="media emoji fade"
            :class="{ ok: loaded }"
            :src="mediaUrlOf(msg)"
            alt="表情"
            referrerpolicy="no-referrer"
            decoding="async"
            @load="onMediaOk"
            @error="onMediaOk"
          />
        </span>

        <!-- 文件卡片：图标 + 文件名 + 下载 -->
        <a v-else-if="msg.msg_type === 3" class="file-card" :href="localMedia || mediaUrlOf(msg)" :download="fileTitle">
          <span class="badge">文件</span>
          <span class="fc-main">
            <span class="fc-title">{{ fileTitle }}</span>
            <span class="fc-sub">点击下载</span>
          </span>
        </a>

        <!-- 引用消息：回复正文 + 引用内容（微信样式）。
             被引用的是图片且对上了原消息：不加灰底框，骨架屏占位直接渲染缩略图；
             其余情况走灰色引用块文字 -->
        <template v-else-if="quote">
          <div class="content">{{ quote.reply || '[引用]' }}</div>
          <template v-if="quoteImg">
            <span v-if="quote.name" class="q-text bare">{{ quote.name }}：</span>
            <span class="ph q-ph" :class="{ on: loaded }" :style="qBox">
              <img
                class="q-img fade"
                :class="{ ok: loaded }"
                :style="qBox"
                :src="quoteImg"
                alt="引用图片"
                title="点击查看大图"
                referrerpolicy="no-referrer"
                decoding="async"
                @load="onMediaOk"
                @error="onMediaOk"
                @click.stop="emit('preview', quoteFullUrl())"
              />
            </span>
          </template>
          <div v-else class="quote-box">
            <span class="q-text" v-html="quoteHtml"></span>
          </div>
        </template>

        <!-- 转账卡片：谁向谁转多少钱 + 手机操作提示，不渲染链接（收款只在手机上操作） -->
        <TransferCard
          v-else-if="transfer"
          :amount="transfer.amount"
          :desc="transfer.desc"
          :from-name="transferFrom"
          :to-name="transferTo"
        />

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
        <div v-else class="content" v-html="contentHtml"></div>

        <!-- 时间不再逐条显示（由时间分隔线承担），仅出方向保留发送状态；完整时间悬停气泡可见 -->
        <div v-if="msg.direction === 2" class="meta">
          <span :class="['st', { fail: msg.status === 2 }]">{{ STATUS_LABEL[msg.status] }}</span>
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
  user-select: none;
}
.re-edit { margin-left: 8px; color: var(--c-primary); }
.re-edit:hover { text-decoration: underline; }

.msg { display: flex; gap: 8px; margin-bottom: 12px; animation: pop 0.22s both; }
@keyframes pop {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: none; }
}
.msg.out { flex-direction: row-reverse; }

.avatar {
  width: 30px; height: 30px; flex-shrink: 0;
  border-radius: var(--r-sm);
  color: #fff; font-size: 13px; font-weight: 600;
  display: flex; align-items: center; justify-content: center;
  margin-top: 16px;
  user-select: none;
}
.avatar.client { background: var(--c-ok); }
.avatar.agent { background: var(--c-primary); }
.avatar.img { object-fit: cover; background: var(--c-surface); }

.body { max-width: 72%; min-width: 0; display: flex; flex-direction: column; }
.msg.out .body { align-items: flex-end; }
.name { font-size: 11px; color: var(--c-text-sub); margin-bottom: 2px; user-select: none; }
/* 出方向名字即操作人：主色徽标便于一眼看出"谁发的" */
.msg.out .name { color: var(--c-primary); font-weight: 600; }

.bubble {
  padding: 7px 10px;
  border-radius: var(--r-lg);
  background: var(--c-panel);
  border: 1px solid var(--c-border);
  width: fit-content;
}
.msg.in .bubble { border-top-left-radius: 3px; }
.msg.out .bubble { background: var(--c-primary-soft); border-color: #c9dbff; border-top-right-radius: 3px; }
/* 媒体气泡：图片/表情/视频贴边（微信样式）——白底、边框全去掉，图片即气泡 */
.bubble.tight,
.msg.in .bubble.tight,
.msg.out .bubble.tight { padding: 0; background: none; border: none; }

/* 媒体消息：图片/表情/语音/视频直接渲染 */
.media { display: block; }
.media.img { display: block; max-width: 200px; max-height: 200px; border-radius: var(--r-sm); cursor: zoom-in; }
/* 清晰图层：绝对定位盖在缩略图上交叉淡入（比例一致不会变形），不拦截点击 */
.layer-sharp { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; pointer-events: none; }
.media.emoji { width: 120px; }
.media.audio { width: 240px; height: 36px; }
.media.video { max-width: 240px; border-radius: var(--r-sm); }

/* 媒体占位：shimmer 常驻底层不撤（图片画出来盖住它），全程没有"空尺寸框"阶段 */
.ph {
  position: relative;
  display: block;
  overflow: hidden;
  border-radius: var(--r-sm);
  background: linear-gradient(100deg, #e2e8f2 40%, #f3f6fb 50%, #e2e8f2 60%);
  background-size: 200% 100%;
  animation: shimmer 1.1s linear infinite;
}
.ph.on { animation: none; } /* 图已盖住底纹，停掉动画省 CPU，背景留着当图下的底色 */
.ph-img { min-width: 140px; min-height: 105px; }
.ph-emoji { width: 120px; min-height: 90px; }
@keyframes shimmer { to { background-position: -200% 0; } }

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

/* 引用块：微信同款灰底 + 左侧竖线（仅文字引用用；图片引用走 .q-ph 骨架屏） */
.quote-box {
  margin-top: 5px; padding: 4px 8px;
  border-left: 2px solid var(--c-border);
  background: var(--c-surface);
  border-radius: 4px;
  font-size: 12px; line-height: 1.5; color: var(--c-text-sub);
  white-space: pre-wrap; word-break: break-word;
}
.q-text.bare { display: block; margin-top: 5px; font-size: 12px; color: var(--c-text-sub); }
/* 引用块内的被引用图片：骨架屏占位 + 缩略图（点击看大图），无灰底包裹 */
.q-ph { min-width: 120px; min-height: 90px; margin-top: 3px; }
.q-img {
  display: block; max-width: 180px; max-height: 120px;
  border-radius: 3px;
  cursor: zoom-in;
}
.fade { opacity: 0; transition: opacity 0.15s ease; }
.fade.ok { opacity: 1; }
.meta {
  margin-top: 3px; font-size: 10px; color: var(--c-text-sub);
  display: flex; gap: 8px; justify-content: flex-end;
}
.st.fail { color: var(--c-danger); font-weight: 600; }
</style>
