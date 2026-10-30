/** 通讯录状态（Pinia）：好友/群列表、搜索词、选中项。搜索为本地过滤（即时高亮）。 */
import { defineStore } from 'pinia'
import { fetchContacts } from '../api'

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
      const q = s.keyword.trim().toLowerCase()
      if (!q) return s.currentList
      return s.currentList.filter((c) =>
        [c.name, c.wxid].some((x) => x && x.toLowerCase().includes(q)))
    },

    selectedContact(s) {
      if (!s.selected) return null
      const list = s.selected.type === 'friend' ? s.friends : s.groups
      return list.find((c) => c.id === s.selected.id) || null
    },

    /** 当前 tab 无结果而另一 tab 有结果时，提示切换（数量）。 */
    crossHintCount(s) {
      const q = s.keyword.trim().toLowerCase()
      if (!q) return 0
      const other = s.tab === 'friends' ? s.groups : s.friends
      return other.filter((c) =>
        [c.name, c.wxid].some((x) => x && x.toLowerCase().includes(q))).length
    },
  },

  actions: {
    /** 拉取好友+群列表（每次打开通讯录都刷新，保证资料同步后是最新的）。 */
    async load() {
      this.loading = true
      try {
        const [friends, groups] = await Promise.all([
          fetchContacts('friends'),
          fetchContacts('groups'),
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
  },
})
