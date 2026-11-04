/* api.js — 接口壳：签名即未来真实 API，目前内部返回 mock。
   后端接入时仅需把 TODO 处替换为 axios 调用，返回结构保持一致。 */

const API = (() => {
  const delay = (ms) => new Promise((r) => setTimeout(r, ms));

  /**
   * 好友列表
   * TODO: replace with GET /api/friends?keyword=
   * resp: { code: 0, data: Friend[] }
   */
  async function fetchFriends() {
    await delay(450); // 模拟网络延迟，让加载骨架可见
    return DB.friends;
  }

  /**
   * 群聊列表
   * TODO: replace with GET /api/groups?keyword=
   * resp: { code: 0, data: Group[] }
   */
  async function fetchGroups() {
    await delay(450);
    return DB.groups;
  }

  return { fetchFriends, fetchGroups };
})();
