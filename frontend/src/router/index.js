/** 前端路由配置 —— 只配一个独立详情页路由，其余全走 App.vue 原有 view ref 逻辑。
 *
 * 为什么不用 vue-router 全局接管？因为工作台有 login/workbench/admin 三态切换（非 SPA 路由），
 * 强行全路由化反而改面太大。这里只做"从拓展栏开新标签"这一件事：
 *   QuoteCard.onOpenDetail → window.open('/#/quote-detail/:id', '_blank')
 *   新开的标签加载同一个 index.html → App.vue 识别 hash → 渲染独立全屏 QuoteDetailPage
 */
import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  {
    path: '/quote-detail/:id',
    name: 'quote-detail',
    // 懒加载：只有新开详情页标签时才加载，工作台不受影响
    component: () => import('../pages/QuoteDetailPage.vue'),
    props: (route) => ({ inquiryId: Number(route.params.id) || 0 }),
  },
]

export const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

/** 当前 hash 是否是详情页路由（App.vue 用来决定渲染哪个顶层） */
export function isDetailRoute() {
  return location.hash.startsWith('#/quote-detail/')
}

/** 从 hash 里提取询价 id（App.vue 在初始挂载时用） */
export function getDetailInquiryId() {
  const m = location.hash.match(/#\/quote-detail\/(\d+)/)
  return m ? Number(m[1]) : 0
}
