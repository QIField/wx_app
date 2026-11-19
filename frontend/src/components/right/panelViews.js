/** 拓展栏视图注册表 —— 头部导航与壳体切换的唯一接入点。
 *
 * 新增拓展页 = 本文件顶部 import 组件 + 底部 registerPanelView 一行，
 * PanelHead / InfoPanel 零改动。字段契约：
 *   key      唯一键（选中态路由值）
 *   label    菜单文案
 *   icon     24×24 viewBox 的 SVG 内部标记字符串（线性 stroke 风格，色随 currentColor）
 *   order    越小越靠前（缺省 999）
 *   badge    true | () => boolean —— 新功能红点；函数型供动态数据接入
 *   disabled true —— 置灰待后端支持（不可激活、键盘导航跳过、tooltip 提示）
 *   comp     视图组件
 */
import AutoFeedView from './AutoFeedView.vue'
import ManualView from './ManualView.vue'
import AnalysisView from './AnalysisView.vue'
import SettingsView from './SettingsView.vue'

/** 头部品牌行元信息 */
export const PANEL_META = { title: '快捷报价', version: 'v1.1' }

const PANEL_VIEWS = []

export function registerPanelView(def) {
  if (!def?.key || !def.comp) {
    throw new Error(`registerPanelView「${def?.key || '(无名)'}」缺少 key 或 comp`)
  }
  if (PANEL_VIEWS.some((v) => v.key === def.key)) {
    throw new Error(`registerPanelView key 重复：${def.key}`)
  }
  PANEL_VIEWS.push({ order: 999, ...def })
  PANEL_VIEWS.sort((a, b) => a.order - b.order)
}

export { PANEL_VIEWS }

/* ---------- 内置视图：图标统一 24×24 stroke 线性风格 ---------- */
const ICON_BOLT = '<path d="M13 2 4.5 13.5H11L9.8 22 19 10h-6.5L13 2z"/>'
const ICON_SEARCH = '<circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5 20.5 20.5"/>'
const ICON_CHART = '<path d="M4 19.5h16"/><path d="M7.5 15.5v-4.5M12 15.5v-9M16.5 15.5v-6.5"/>'
const ICON_SLIDERS =
  '<path d="M4 7h7.6M16.4 7H20M4 17h5.6M12.4 17H20"/><circle cx="14" cy="7" r="2.4"/><circle cx="10" cy="17" r="2.4"/>'

registerPanelView({ key: 'auto', label: '自动报价', icon: ICON_BOLT, order: 10, comp: AutoFeedView })
registerPanelView({ key: 'manual', label: '手动报价', icon: ICON_SEARCH, order: 20, comp: ManualView })
registerPanelView({ key: 'analysis', label: '报价分析', icon: ICON_CHART, order: 30, comp: AnalysisView })
registerPanelView({ key: 'settings', label: '设置', icon: ICON_SLIDERS, order: 40, comp: SettingsView })
