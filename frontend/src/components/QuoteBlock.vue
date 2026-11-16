<script setup>
/** 引用块：回复正文 + 引用内容（微信样式）。
 *
 * 被引用的是图片且对上了原消息：不加灰底框，骨架屏占位直接渲染缩略图；
 * 其余情况走灰色引用块文字。正文/引用文本接入自定义选区引擎（多选模式短路）。
 */
import { computed, ref } from 'vue'
import { renderEmojiHtml } from '../utils/emoji'
import { mediaUrlOf } from '../utils/media'
import { useImgBox, useImgRetry, useMediaLoad } from '../composables/useMedia'
import { onTextMouseDown, onTextDblClick } from '../utils/textSelection'

const props = defineProps({
  msg: { type: Object, required: true }, // 选区归属按消息 id 区分
  quote: { type: Object, default: null }, // 引用信息（父层已解析：payload.quote / XML 兜底）
  selectable: { type: Boolean, default: false }, // 多选模式下点击短路，不拖选
})
const emit = defineEmits(['preview', 'mediaload'])

/* 引用块文本同样走表情渲染（被引用的原消息常含表情码） */
const quoteHtml = computed(() =>
  renderEmojiHtml((props.quote?.name ? `${props.quote.name}：` : '') + (props.quote?.text || '[原消息]'))
)

/* 引用块内的被引用图片：后端解析出原图片消息 id（media_id）才有，
 * 找不到原消息时回退 [图片] 标签。缩略图与预览共用这一个地址。 */
const quoteImg = computed(() => {
  const id = props.quote?.media_id
  return id ? mediaUrlOf({ id }) : null
})

const { loaded, onMediaOk } = useMediaLoad(emit)
const { withBust, onImgError } = useImgRetry()
const quoteSrc = computed(() => withBust(quoteImg.value || ''))

/* 引用图 180×120 上限的尺寸预占位（机制见 useMedia.useImgBox） */
const { box: qBox, onLoad: onQuoteLoad } = useImgBox(() => props.quote, 180, 120, onMediaOk)

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
  <div class="content" @mousedown="onTextDown" @dblclick="onTextDbl">{{ quote.reply || '[引用]' }}</div>
  <template v-if="quoteImg">
    <span v-if="quote.name" class="q-text bare">{{ quote.name }}：</span>
    <span class="ph q-ph" :class="{ on: loaded, sized: !!qBox }" :style="qBox">
      <img
        class="q-img fade"
        :class="{ ok: loaded }"
        :style="qBox"
        :src="quoteSrc"
        alt="引用图片"
        title="点击查看大图"
        referrerpolicy="no-referrer"
        decoding="async"
        @load="onQuoteLoad"
        @error="onImgError(() => onMediaOk())"
        @click.stop="emit('preview', quoteSrc)"
      />
    </span>
  </template>
  <div v-else class="quote-box">
    <span class="q-text" v-html="quoteHtml" @mousedown="onTextDown" @dblclick="onTextDbl"></span>
  </div>
</template>

<style scoped>
.content { white-space: pre-wrap; word-break: break-word; line-height: 1.55; }

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
/* 骨架屏占位底纹（与 MessageRow .ph 同款，子组件内独立成套） */
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
.ph.on.sized { min-width: 0; min-height: 0; }
@keyframes shimmer { to { background-position: -200% 0; } }
</style>
