/** 快捷报价配置共享状态（自动报价 / 设置视图共用）。
 *
 * GET /quote/config 回填 aiOn / mode；price_map / parts_blacklist 等扩展字段
 * 由调用方经 onLoaded 回调自行回填。失败时向上抛错，容错语义由调用方决定。
 *
 * 设备维度（2026-11-25）：ai_enabled / quote_mode 按设备独立。
 * 调用方传 openid 参数，后端 merged_config 回 device 行，缺失时回 global 行兜底。
 *
 * 注意：aiOn / mode 是模块级 ref（单例），AutoFeedView 和 SettingsView 读的是同一份——
 * 一个组件保存后另一个组件 GET 最新值刷新，不会再互相用旧值覆盖。
 */
import { ref } from 'vue'
import { fetchQuoteConfig } from '../api'

// 模块级单例：两个共享调用方各用各的 useQuoteConfig()，但底层 ref 同一份
const aiOn = ref(true)
const mode = ref('preview')

export function useQuoteConfig() {
  /** 拉取配置并回填公共字段；onLoaded(cfg) 供调用方回填扩展字段。
   *  openid: 当前查看/保存的设备，不传 → 后端默认绑定列表第一个。
   */
  async function load(onLoaded, openid) {
    const cfg = await fetchQuoteConfig(openid)
    aiOn.value = cfg.ai_enabled !== false
    mode.value = cfg.quote_mode || 'preview'
    if (onLoaded) onLoaded(cfg)
    return cfg
  }

  return { aiOn, mode, load }
}
