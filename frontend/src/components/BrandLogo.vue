<script setup>
/**
 * 品牌图标：原创「十字枢纽」标 —— 一笔贯穿、一笔在其上方断开、
 * 交点处一颗枢纽圆点（寓意客服连接的交汇点），深蓝渐变底 + 光晕。
 * 参考 X 造型但为描边断线+枢纽点构图，与推特实心字形明显区分。
 */
defineProps({
  size: { type: Number, default: 26 },
})
</script>

<template>
  <span class="brand-logo" :style="{ width: size + 'px', height: size + 'px' }" aria-hidden="true">
    <svg viewBox="0 0 48 48" fill="none" :width="Math.round(size * 0.64)" :height="Math.round(size * 0.64)">
      <defs>
        <linearGradient id="si-x-stroke" x1="8" y1="8" x2="40" y2="40" gradientUnits="userSpaceOnUse">
          <stop offset="0" stop-color="#8ab6ff" />
          <stop offset="1" stop-color="#3a78ff" />
        </linearGradient>
      </defs>
      <!-- 底笔：左上 → 右下，完整贯穿 -->
      <path d="M12 12 L36 36" stroke="url(#si-x-stroke)" stroke-width="4.6" stroke-linecap="round" />
      <!-- 面笔：右上 → 左下，在交点处断开（形成穿插立体感） -->
      <path d="M36 12 L27.8 20.2 M20.2 27.8 L12 36" stroke="url(#si-x-stroke)" stroke-width="4.6" stroke-linecap="round" />
      <!-- 交点枢纽 -->
      <circle cx="24" cy="24" r="3.3" fill="url(#si-x-stroke)" />
    </svg>
  </span>
</template>

<style scoped>
.brand-logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border-radius: 24%;
  background: linear-gradient(150deg, #1e3f8a 0%, #12265a 100%);
  border: 1px solid rgba(146, 176, 255, 0.3);
  color: #fff;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.12),
    0 2px 14px rgba(29, 93, 228, 0.38);
}
</style>
