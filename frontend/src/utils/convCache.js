/* ===== convCache.js · 会话消息快照缓存（内存级 LRU） =====
 *
 * 打开过的会话把最近一页消息留在内存：再次点开先渲染快照即时显示
 * （无骨架屏），随后由调用方后台静默刷新纠正。仅前端内存，关页即清。
 *
 * - key 带 openid 前缀：多设备切换互不串窗；
 * - Map 写入前先删再放，天然按"最近使用"排序，超限淘汰最早一条。
 */

const CACHE_LIMIT = 20
const cache = new Map()

function cacheKey(openid, id) {
  return `${openid || ''}:${id}`
}

export function convCacheGet(openid, id) {
  return cache.get(cacheKey(openid, id)) || null
}

export function convCachePut(openid, id, messages, hasMore) {
  const key = cacheKey(openid, id)
  cache.delete(key) // 先删再放：命中顺序刷新，Map 即 LRU
  cache.set(key, { messages, hasMore })
  if (cache.size > CACHE_LIMIT) {
    cache.delete(cache.keys().next().value)
  }
}
