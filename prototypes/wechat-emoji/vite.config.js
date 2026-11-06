import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// base './'：dist 可直接双击 index.html 离线打开
export default defineConfig({
  base: './',
  plugins: [vue()],
})
