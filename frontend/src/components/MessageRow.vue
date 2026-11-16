<script setup>
/** 单条消息行：文本气泡 / 图片语音视频 / 卡片 / 微信样式系统灰条。
 *
 * 气泡内容按消息类型分发：媒体与文本留在本组件，引用块（QuoteBlock）、
 * 合并转发卡（ForwardCard）、文件/链接卡（LinkFileCard）、转账卡
 * （TransferCard）、语音（VoiceBubble）各自独立成组件。
 * 灰条三类来源：撤回通知（自己撤回的可"重新编辑"）、后端兜底系统行、
 * 残留的微信系统 XML（拍一拍等）。图片点击交给父组件做全屏预览，
 * 气泡右键上抛父层弹操作菜单（复制等，见 ChatPanel）。
 */
import { computed, ref } from 'vue'
import { canReEdit, isSystemXml, quoteInfoOf, transferInfoOf } from '../utils/message'
import { renderMessageHtml } from '../utils/mention'
import { onTextMouseDown, onTextDblClick } from '../utils/textSelection'
import { messageMediaUrlOf } from '../utils/media'
import { displayNameOf } from '../utils/format'
import { useImgBox, useImgRetry, useMediaLoad } from '../composables/useMedia'
import AnonAvatar from './AnonAvatar.vue'
import TransferCard from './TransferCard.vue'
import VoiceBubble from './VoiceBubble.vue'
import QuoteBlock from './QuoteBlock.vue'
import ForwardCard from './ForwardCard.vue'
import LinkFileCard from './LinkFileCard.vue'

const props = defineProps({
  msg: { type: Object, required: true }, // timeline 展开后的单条消息
  conv: { type: Object, default: null }, // 当前会话（头像/昵称取值用）
  selectable: { type: Boolean, default: false }, // 多选模式：行首出勾选圈，点击行切换
  picked: { type: Boolean, default: false },     // 本行是否已被勾选
})
const emit = defineEmits(['preview', 'reedit', 'mediaload', 'menu', 'toggle', 'openrecord', 'profile'])

const STATUS_LABEL = { 0: '发送中', 1: '已发送', 2: '失败' }

/* ---------- 头像三态：真实图 / 匿名图标（脱敏契约）/ 首字 ---------- */

/* 入方向是否走匿名图标：单聊会话名未解析，或群发言人真匿名（后端 sender_anon
 * 显式标记；@openim 等"有名字没头像"的成员不算匿名，走首字兜底，与 @选择器口径一致） */
function isAnon(m) {
  if (m.direction === 2) return false
  if (props.conv?.chat_type === 2) return !!m.sender_anon
  return !props.conv?.name
}
/* 匿名头像编码：群消息用发言人 alias，单聊用会话 alias */
function anonAlias(m) {
  return props.conv?.chat_type === 2 ? (m.sender_alias || '') : (props.conv?.alias || '')
}

/* 入方向头像可点：上抛打开统一备注侧栏（单聊=对方，群聊=发言人） */
function onAvatarClick() {
  if (props.msg.direction !== 2) emit('profile', props.msg)
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
  // 出方向：业务端发送显示操作人快照；手机端发的没有操作人，标「手机端」区分来源
  if (m.direction === 2) {
    return m.operator_name || `${m.sender_name || '手机'}（手机端）`
  }
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

/* 转账卡片：只展示 谁向谁转多少钱 + 手机操作提示（卡片本体见 TransferCard.vue）。
 * 转出方/收款方：入方向=客户→我；出方向=操作人→客户 */
const transfer = computed(() => transferInfoOf(props.msg))
const transferFrom = computed(() => nameOf(props.msg))
const transferTo = computed(() =>
  props.msg.direction === 2 ? displayNameOf(props.conv) || '客户' : '我'
)

/* 文本消息渲染：先过表情（内部已转义），再把 @昵称 标蓝——微信同款提醒样式 */
const contentHtml = computed(() => renderMessageHtml(props.msg.content))

/* 引用消息：新消息读 payload.quote；历史按链接入库的数据解析 XML 兜底。
 * 这里只做「有无引用」的分发判断，引用块渲染在 QuoteBlock.vue */
const quote = computed(() => quoteInfoOf(props.msg))

/* 气泡内媒体的展示地址：自己刚发的取本地 path，其余走媒体接口；
 * 图片加载失败重试时拼 cache-bust 参数强制刷新（机制见 useMedia.useImgRetry）。 */
const { withBust, onImgError } = useImgRetry()
const mediaSrc = computed(() => withBust(messageMediaUrlOf(props.msg)))

/* 图片/表情/视频撑满气泡：去掉内边距（微信样式） */
const isTight = computed(() => [2, 4, 7].includes(props.msg.msg_type))

/* 媒体加载状态：加载前 shimmer 占位块，加载完淡入；就绪后通知父层重新锚定底部 */
const { loaded, onMediaOk } = useMediaLoad(emit)

/* 图片盒子 200×200：payload 宽高优先，缺失时靠 natural 兜底（机制见 useMedia.useImgBox） */
const { box: imgBox, onLoad: onImgLoad } = useImgBox(() => props.msg.payload, 200, 200, onMediaOk)

function onReEdit() {
  emit('reedit', props.msg.content)
}

/* 气泡右键 → 上抛给 ChatPanel 统一弹菜单（菜单状态收口在父层，行组件只报坐标与目标）。
 * 选中文本不再在此快照：自定义选区引擎（textSelection.js）持有单例状态，
 * 父层用 msg.id 对比引擎归属决定复制片段或全文兜底 */
function onMenu(e) {
  emit('menu', { msg: props.msg, x: e.clientX, y: e.clientY })
}

/* 文本容器（正文/引用块）接入自定义选区引擎：多选模式下点击行为已被勾选占用，短路不拖选 */
function onTextDown(e) {
  if (props.selectable) return
  onTextMouseDown(e, props.msg.id)
}
function onTextDbl(e) {
  if (props.selectable) return
  onTextDblClick(e, props.msg.id)
}
</script>

<template>
  <!-- 系统灰条：居中一行，微信撤回样式 -->
  <div v-if="isSys" class="sysline">
    <span>{{ sysText }}</span>
    <a v-if="showReEdit" class="re-edit" href="#" @click.prevent="onReEdit">重新编辑</a>
  </div>

  <div
    v-else
    class="msg"
    :class="[{ out: msg.direction === 2, in: msg.direction !== 2, selectable }]"
    @click="selectable && emit('toggle', props.msg.id)"
  >
    <span v-if="selectable" class="pick" :class="{ on: picked }">
      <svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="#fff" stroke-width="3.4"><path d="M20 6 9 17l-5-5"/></svg>
    </span>
    <img v-if="picOf(msg)" class="avatar img" :class="{ clk: msg.direction !== 2 }" :src="picOf(msg)" alt="" referrerpolicy="no-referrer" @click="onAvatarClick" />
    <AnonAvatar v-else-if="isAnon(msg)" :alias="anonAlias(msg)" class="avatar" :class="{ clk: msg.direction !== 2 }" @click="onAvatarClick" />
    <span v-else class="avatar" :class="[msg.direction === 2 ? 'agent' : 'client', { clk: msg.direction !== 2 }]" @click="onAvatarClick">{{ avatarOf(msg) }}</span>
    <div class="body">
      <div class="name">{{ nameOf(msg) }}</div>
      <div class="bubble" :class="{ tight: isTight }" :title="msg.create_time" @contextmenu.prevent="onMenu">
        <!-- 气泡只渲染缩略图（清晰度名次 3，多已预下载走本地缓存），不再叠加大图，
             避免聊天流加载原图；点开预览才换最清档 -->
        <span v-if="msg.msg_type === 2" class="ph ph-img" :class="{ on: loaded, sized: !!imgBox }" :style="imgBox">
          <img
            class="media img"
            :data-mid="msg.id"
            :style="imgBox"
            :src="mediaSrc"
            alt="图片消息"
            title="点击查看大图"
            referrerpolicy="no-referrer"
            decoding="async"
            @load="onImgLoad"
            @error="onImgError(() => onMediaOk())"
            @click="emit('preview', mediaSrc)"
          />
        </span>
        <!-- 语音：自绘气泡（后端转码 mp3 后可真正出声；原生 audio 解不了 SILK） -->
        <VoiceBubble v-else-if="msg.msg_type === 6" :msg="msg" />
        <video v-else-if="msg.msg_type === 4" class="media video" :src="mediaSrc" controls preload="metadata" @loadeddata="emit('mediaload')"></video>
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

        <!-- 引用消息：回复正文 + 引用内容（微信样式，含引用图骨架屏） -->
        <QuoteBlock
          v-else-if="quote"
          :msg="msg"
          :quote="quote"
          :selectable="selectable"
          @preview="emit('preview', $event)"
          @mediaload="emit('mediaload')"
        />

        <!-- 转账卡片：谁向谁转多少钱 + 手机操作提示，不渲染链接（收款只在手机上操作） -->
        <TransferCard
          v-else-if="transfer"
          :amount="transfer.amount"
          :desc="transfer.desc"
          :from-name="transferFrom"
          :to-name="transferTo"
        />

        <!-- 合并转发卡片（msg_type=9）：标题 + 前两条预览 + 页脚，点开拉快照回看 -->
        <ForwardCard
          v-else-if="msg.msg_type === 9"
          :msg="msg"
          :selectable="selectable"
          @toggle="emit('toggle', $event)"
          @openrecord="emit('openrecord', $event)"
        />

        <!-- 文件卡片（下载）/ 链接卡片（新窗口打开） -->
        <LinkFileCard v-else-if="msg.msg_type === 3 || msg.msg_type === 5" :msg="msg" />

        <div v-else-if="msg.msg_type !== 1" class="content type-label">[未知类型]</div>
        <div v-else class="content" v-html="contentHtml" @mousedown="onTextDown" @dblclick="onTextDbl"></div>

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
/* 多选模式：整行可点、勾选圈在头像外侧（out 方向自动靠右） */
.msg.selectable { cursor: pointer; }
.pick {
  width: 17px; height: 17px; flex-shrink: 0; align-self: center;
  border-radius: 50%;
  border: 1.5px solid var(--c-border-strong);
  display: flex; align-items: center; justify-content: center;
  user-select: none;
  transition: all 0.12s;
}
.pick.on { background: var(--c-primary); border-color: var(--c-primary); }

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
.avatar.clk { cursor: pointer; }
.avatar.clk:hover { opacity: 0.85; }
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
.media.emoji { width: 120px; }
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
/* 盒子已按真实比例定尺寸后撤掉最小占位，否则 min-height 大于图片实际高度时
   图片下方会露出一条灰色底纹（宽图尤其明显） */
.ph.on.sized { min-width: 0; min-height: 0; }
.ph-img { min-width: 140px; min-height: 105px; }
.ph-emoji { width: 120px; min-height: 90px; }
@keyframes shimmer { to { background-position: -200% 0; } }

.fade { opacity: 0; transition: opacity 0.15s ease; }
.fade.ok { opacity: 1; }

.content { white-space: pre-wrap; word-break: break-word; line-height: 1.55; }
/* 气泡正文走 v-html，拿不到 scoped 属性，@昵称高亮必须用 :deep */
.content :deep(.msg-mention) { color: var(--c-primary); font-weight: 600; }
.type-label { color: var(--c-primary); }

.meta {
  margin-top: 3px; font-size: 10px; color: var(--c-text-sub);
  display: flex; gap: 8px; justify-content: flex-end;
}
.st.fail { color: var(--c-danger); font-weight: 600; }
</style>
