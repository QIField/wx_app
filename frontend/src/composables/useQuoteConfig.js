/** 快捷报价配置加载共享逻辑（自动报价 / 设置视图共用）。
 *
 * GET /quote/config 回填两个全局开关字段：aiOn（ai_enabled，缺省 true）、
 * mode（quote_mode，缺省 preview）；price_map / parts_blacklist 等扩展字段
 * 由调用方经 onLoaded 回调自行回填。失败时向上抛错，容错语义由调用方决定
 * （自动报价静默保持默认值可重试，设置视图 toast 后仍可交互）。
 */
import { ref } from 'vue'
import { fetchQuoteConfig } from '../api'

export function useQuoteConfig() {
  const aiOn = ref(true)
  const mode = ref('preview')

  /** 拉取配置并回填公共字段；onLoaded(cfg) 供调用方回填扩展字段。 */
  async function load(onLoaded) {
    const cfg = await fetchQuoteConfig()
    aiOn.value = cfg.ai_enabled !== false
    mode.value = cfg.quote_mode || 'preview'
    if (onLoaded) onLoaded(cfg)
    return cfg
  }

  return { aiOn, mode, load }
}
