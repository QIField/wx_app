/** 通讯录状态（Pinia）：好友/群列表、搜索词、选中项、联系人档案（备注/标签）。 */
import { defineStore } from 'pinia'
import { fetchContacts, fetchContactProfile, saveContactProfile } from '../api'
import { matchKeyword, displayNameOf } from '../utils/format'
import { useChatStore } from './chat'

export const useContactsStore = defineStore('contacts', {
  state: () => ({
    tab: 'friends',  // friends | groups
    keyword: '',
    friends: [],
    groups: [],
    loading: false,
    selected: null,  // { type: 'friend' | 'group', id }
    profile: null,   // 选中联系人的档案 {remark, tags}
  }),

  getters: {
    currentList: (s) => (s.tab === 'friends' ? s.friends : s.groups),

    filteredList(s) {
      // 搜索只匹配展示名（含「匿名 编码」）与备注；wxid 已不在前端数据里
      return s.currentList.filter((c) => matchKeyword([displayNameOf(c)], s.keyword))
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
      return other.filter((c) => matchKeyword([displayNameOf(c)], s.keyword)).length
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
      this.profile = null
    },

    /** 拉取选中联系人的档案（备注/标签；按通讯录行 id，不传 wxid）。 */
    async loadProfile(contactId) {
      this.profile = await fetchContactProfile(contactId)
    },

    /** 保存备注/标签（upsert，按通讯录行 id），成功后本地同步。 */
    async saveProfile(contactId, payload) {
      this.profile = await saveContactProfile(contactId, payload)
    },
  },
})
