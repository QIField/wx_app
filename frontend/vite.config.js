import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 开发服务器：前端 5173，/api 和 /ws 代理给 Flask 5000（免跨域）
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/ws': { target: 'ws://127.0.0.1:5000', ws: true },
    },
  },
})
