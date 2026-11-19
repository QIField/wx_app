/* ===== useMention.js · 聊天输入区 @提及浮层 =====
 *
 * 只在群聊生效——单聊 @ 没有意义，还容易误发。
 * 名册懒加载：第一次 @ 才请求接口，之后全部本地过滤（打字不打请求）；
 * 加载期间用户又改了检索词，本轮结果作废，交给更新的那一轮。
 * 浮层开合/检索词/候选/高亮/位置状态与键盘导航、选中插入全部内聚于此，
 * 成员名册缓存放在 chat store。切换会话时自动关闭。
 */

import { nextTick, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useChatStore } from '../stores/chat'
import {
  caretAnchorX, extractMentionQuery, insertMentionAtCursor, matchMembers, textBeforeCaret,
} from '../utils/mention'

/**
 * @param {import('vue').Ref<HTMLElement|null>} composerEl contenteditable 输入框
 * @param {Object} opts
 * @param {() => void} opts.afterInsert 选中成员插入片段后的回调（刷新可发送态）
 */
export function useMention(composerEl, { afterInsert }) {
  const chat = useChatStore()

  const mentionOpen = ref(false)
  const mentionQuery = ref('')
  const mentionItems = ref([])
  const mentionTotal = ref(0)
  const mentionActive = ref(-1)
  const mentionLoading = ref(false)
  const mentionLeft = ref(4)
  const mentionWidth = ref(300)

  function closeMention() {
    mentionOpen.value = false
    mentionQuery.value = ''
    mentionItems.value = []
    mentionActive.value = -1
    mentionLoading.value = false
  }

  // 切换会话：浮层立即关闭
  watch(() => chat.currentId, closeMention)

  /** 浮层贴到 @ 所在位置：靠右时向左翻折，容器太窄时宽度自适应 */
  function placeMentionPop() {
    const wrap = composerEl.value?.parentElement
    if (!wrap) return
    const wrapW = wrap.clientWidth
    const w = Math.min(320, wrapW - 8)
    mentionWidth.value = w
    const x = caretAnchorX()
    const raw = x == null ? 8 : x - wrap.getBoundingClientRect().left - 14
    mentionLeft.value = Math.max(4, Math.min(raw, wrapW - w - 4))
  }

  /**
   * 每次输入后重算「光标前是否处于 @ 上下文」。
   * 名册懒加载：第一次 @ 才请求接口，之后全部本地过滤（打字不打请求）；
   * 加载期间用户又改了检索词，本轮结果作废，交给更新的那一轮。
   */
  async function detectMention() {
    const conv = chat.currentConv
    if (!conv || conv.chat_type !== 2) return closeMention()

    const q = extractMentionQuery(textBeforeCaret(composerEl.value))
    if (q == null) return closeMention()

    mentionQuery.value = q
    const convId = conv.id
    // undefined=没请求过；[]=请求过但名册为空（不再重复请求）
    if (!chat.membersByConv[convId]) {
      mentionLoading.value = true
      mentionOpen.value = true
      mentionItems.value = []
      mentionTotal.value = 0
      placeMentionPop()
      try {
        await chat.loadMembers(convId)
        mentionLoading.value = false
      } catch (e) {
        closeMention() // 内含 mentionLoading=false，避免浮层卡在"加载中"
        ElMessage.error(e.message)
        return
      }
      if (chat.currentId !== convId || mentionQuery.value !== q) return
    }
    mentionTotal.value = chat.currentMembers.length
    mentionItems.value = matchMembers(chat.currentMembers, q)
    mentionActive.value = mentionItems.value.length ? 0 : -1
    mentionOpen.value = true
    await nextTick()
    placeMentionPop()
  }

  function moveMentionActive(delta) {
    const n = mentionItems.value.length
    if (!n) return
    mentionActive.value = (mentionActive.value + delta + n) % n // 环绕，长列表也能从底部跳回顶部
  }

  function setMentionActive(i) {
    if (mentionOpen.value && i >= 0 && i < mentionItems.value.length) mentionActive.value = i
  }

  /** 选中成员：把「@检索词」替换成原子片段，光标落到片段之后可继续输入 */
  function chooseMention(member) {
    if (!member) return
    insertMentionAtCursor(composerEl.value, member)
    closeMention()
    afterInsert()
    composerEl.value?.focus()
  }

  return {
    mentionOpen, mentionQuery, mentionItems, mentionTotal, mentionActive,
    mentionLoading, mentionLeft, mentionWidth,
    closeMention, detectMention, moveMentionActive, setMentionActive, chooseMention,
  }
}
