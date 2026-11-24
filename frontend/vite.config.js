import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    // ManualQueryInline 等组件用了 defineComponent 内联 template 字符串，
    // 需要带运行时编译器的 Vue 版本。
    alias: { vue: 'vue/dist/vue.esm-browser.js' },
  },
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/ws':  { target: 'ws://127.0.0.1:5000', ws: true },
    },
  },
})
