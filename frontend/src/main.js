import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
import './style.css'
import './admin.css'
import './styles/daterange-popper-cover.css'
import App from './App.vue'

// Element Plus 全局中文 locale：周标题 / 月份 / 按钮 / placeholder 统一中文
createApp(App)
  .use(createPinia())
  .use(ElementPlus, { locale: zhCn })
  .mount('#app')
