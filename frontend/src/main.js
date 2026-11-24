import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
import './style.css'
import './admin.css'
import App from './App.vue'
import { router } from './router'

// Element Plus 全局中文 locale：周标题 / 月份 / 按钮 / placeholder 统一中文
createApp(App)
  .use(createPinia())
  .use(ElementPlus, { locale: zhCn })
  .use(router)
  .mount('#app')
