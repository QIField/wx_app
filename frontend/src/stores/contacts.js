/** 通讯录状态（Pinia）：好友/群列表、搜索词、选中项。备注配置由统一编辑器直连 API。 */
import { defineStore } from 'pinia'
import { fetchContacts } from '../api'
import { matchName, displayNameOf } from '../utils/format'
import { useChatStore } from './chat'

/** 通讯录条目搜索命中：展示名（含「匿名 编码」）/ 首字母子串 + 逐字拼音（字边界对齐）。 */
const hitContact = (c, kw) => matchName([displayNameOf(c), c.initials], c.pinyin_toks, kw)

export const useContactsStore = defineStore('contacts', {
  state: () => ({
    tab: 'friends',  // friends | groups
    keyword: '',
    friends: [],
    groups: [],
    loading: false,
    selected: null,  // { type: 'friend' | 'group', id }
  }),

  getters: {
    currentList: (s) => (s.tab === 'friends' ? s.friends : s.groups),

    filteredList(s) {
      // wxid 已不在前端数据里，匹配走 hitContact（展示名/首字母/拼音 token）
      return s.currentList.filter((c) => hitContact(c, s.keyword))
    },

    selectedContact(s) {
      if (!s.selected) return null
      const list = s.selected.type === 'friend' ? s.friends : s.groups
      return list.find((c) => c.id === s.selected.id) || null
    },

    /** 当前 tab 无结果而另一 tab 有结果时，提示切换（数量）。 */
    crossHintCount(s) {
      if (!s.keyword.trim()) return 0
      const other = s.tab === 'friends' ? s.groups : s.friends
      return other.filter((c) => hitContact(c, s.keyword)).length
    },
  },

  actions: {
    /** 拉取好友+群列表（按当前选中的聊天账号；打开通讯录/切换账号时都刷新）。 */
    async load() {
      this.loading = true
      try {
        const openid = useChatStore().activeOpenid || undefined
        const [friends, groups] = await Promise.all([
          fetchContacts('friends', undefined, openid),
          fetchContacts('groups', undefined, openid),
        ])
        this.friends = friends.list
        this.groups = groups.list
      } finally {
        this.loading = false
      }
    },

    setTab(tab) {
      this.tab = tab
      this.selected = null
    },

    setKeyword(kw) {
      this.keyword = kw
    },

    select(type, id) {
      this.selected = { type, id }
    },

    /** 备注/昵称变更后就地刷新：通讯录搜索结果、联系人详情头部、会话列表名字
     *  全部走 displayNameOf(item) → 统一改 item.name 即全局响应。
     *  newName 为空表示"没设置备注"——调用方决定回退策略（通常保持原值不动）。 */
    patchNameById(id, newName) {
      if (!newName) return
      const inFriend = this.friends.find((c) => c.id === id)
      if (inFriend) { inFriend.name = newName; return }
      const inGroup = this.groups.find((c) => c.id === id)
      if (inGroup) inGroup.name = newName
    },
  },
})
