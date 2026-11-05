<script setup>
/** 转账卡片：只展示 谁向谁转多少钱 + 手机操作提示。
 *
 * 暖橙收款心智（锚定 --c-warn），金额大字；纯展示组件，不渲染任何链接——
 * 收款只能在手机上操作，桌面端不留 URL/域名等敏感信息（右键复制全文同样脱敏，见 utils/message）。
 * 金额解析不到时兜底展示后端摘要原文（摘要不含链接）。
 */
defineProps({
  amount: { type: String, default: '' }, // 从摘要提取的金额（千分位原样），空串走摘要兜底
  desc: { type: String, default: '' }, // 后端摘要原文，仅金额缺失时展示
  fromName: { type: String, default: '' }, // 转出方：入方向=客户，出方向=操作人
  toName: { type: String, default: '' }, // 收款方：入方向=我，出方向=客户
})
</script>

<template>
  <div class="transfer-card">
    <div class="tc-head">
      <span class="tc-icon">¥</span>
      <span class="tc-title">转账</span>
    </div>
    <div class="tc-amount num">¥{{ amount || '--' }}</div>
    <div v-if="!amount" class="tc-desc">{{ desc }}</div>
    <div class="tc-route">
      <span class="tc-party">{{ fromName }}</span>
      <svg class="tc-arrow" viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">
        <path d="M2 8h10M8 3.5 12.5 8 8 12.5" stroke="currentColor" stroke-width="1.6" fill="none" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
      <span class="tc-party">{{ toName }}</span>
    </div>
    <div class="tc-hint">
      <svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">
        <rect x="4.5" y="1.5" width="7" height="13" rx="1.5" stroke="currentColor" stroke-width="1.3" fill="none" />
        <path d="M7 12.5h2" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" />
      </svg>
      <span>请在手机上确认收款</span>
    </div>
  </div>
</template>

<style scoped>
.transfer-card {
  position: relative; overflow: hidden;
  width: 220px; padding: 12px 14px;
  border: 1px solid #f4cf9a;
  border-radius: var(--r-md);
  background: linear-gradient(135deg, #fff9ef, #fff1dc);
}
.transfer-card::after {
  content: '¥';
  position: absolute; right: 4px; top: -16px;
  font-family: var(--font-num); font-size: 64px; font-weight: 700;
  color: rgba(240, 130, 30, 0.08);
  pointer-events: none;
}
.tc-head { display: flex; align-items: center; gap: 6px; }
.tc-icon {
  width: 18px; height: 18px; border-radius: 4px; flex-shrink: 0;
  background: linear-gradient(135deg, #fa9d3b, var(--c-warn));
  color: #fff; font-size: 11px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
}
.tc-title { font-size: 12px; font-weight: 600; color: #8a5a1f; }
.tc-amount {
  margin: 6px 0 4px;
  font-size: 24px; font-weight: 700; letter-spacing: 0.5px;
  color: var(--c-warn);
}
.tc-route { display: flex; align-items: center; gap: 6px; font-size: 12px; min-width: 0; }
.tc-party { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 88px; }
.tc-arrow { flex-shrink: 0; color: #b98a4e; }
.tc-desc { font-size: 11px; color: var(--c-text-sub); line-height: 1.4; margin-bottom: 4px; }
.tc-hint {
  margin-top: 10px; padding-top: 8px;
  border-top: 1px dashed #f0d9b8;
  display: flex; align-items: center; gap: 5px;
  font-size: 11px; color: #b06a14;
}
</style>
