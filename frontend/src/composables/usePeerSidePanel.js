/** 右侧「客户资料」侧栏状态：点头像 / 顶部备注名展开，统一备注配置入口（ChatPanel 用）。
 *
 * 单聊：对方头像与顶部备注名同一入口（用户级，全局生效）；
 * 群聊：成员头像 = 该成员的用户级配置（全局生效），顶部群备注名 = 群级配置。
 */
import { computed, ref, watch } from 'vue'
import { useChatStore } from '../stores/chat'
import {
  fetchMemberRemarkConfig,
  fetchRemarkConfig,
  saveMemberRemarkConfig,
  saveRemarkConfig,
} from '../api'
import { displayNameOf } from '../utils/format'

export function usePeerSidePanel() {
  const chat = useChatStore()
  const side = ref(null)
  const peerRemark = ref('') // 顶部标题优先显示备注名（用户级/群级），未设置回退原名

  const peerLabel = computed(() => peerRemark.value || displayNameOf(chat.currentConv))

  function openPeerSide() {
    const c = chat.currentConv
    if (!c) return
    side.value = {
      key: `peer-${c.id}`,
      apiId: -c.id, // 会话条目走负数 id 约定（脱敏契约，不传 wxid）
      title: displayNameOf(c),
      subtitle: c.alias ? `匿名标识：${c.alias}` : '',
      alias: c.alias,
      avatar: c.avatar,
      chatType: c.chat_type,
      fetch: fetchRemarkConfig,
      save: saveRemarkConfig,
      fromGroup: false,
    }
  }

  function onRowProfile(msg) {
    const c = chat.currentConv
    if (!c || msg.direction === 2) return
    if (c.chat_type !== 2) return openPeerSide() // 单聊：与顶部入口同源
    const alias = msg.sender_alias || ''
    if (!alias) return
    side.value = {
      key: `member-${alias}`,
      apiId: -c.id,
      title: msg.sender_name || `匿名 ${alias}`,
      subtitle: `匿名标识：${alias}`,
      alias,
      avatar: msg.sender_avatar || null,
      chatType: 1,
      fetch: (id) => fetchMemberRemarkConfig(id, alias),
      save: (id, payload) => saveMemberRemarkConfig(id, alias, payload),
      fromGroup: true,
    }
  }

  function onSideSaved(cfg) {
    // 顶部标题只跟随本会话目标的配置（群成员入口不改群标题）
    if (side.value && !side.value.fromGroup) peerRemark.value = cfg?.remark_name || ''
  }

  // 切会话：备注名重置重拉；侧栏保持展开跟随当前目标（无会话则收起），不停留在旧目标
  watch(() => chat.currentId, async () => {
    peerRemark.value = ''
    if (side.value) {
      if (chat.currentConv) openPeerSide()
      else side.value = null
    }
    const c = chat.currentConv
    if (!c) return
    try {
      peerRemark.value = (await fetchRemarkConfig(-c.id))?.remark_name || ''
    } catch { /* 拉取失败回退原名显示 */ }
  })

  return { side, peerLabel, openPeerSide, onRowProfile, onSideSaved }
}
