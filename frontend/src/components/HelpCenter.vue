<script setup>
/** 帮助中心：左目录 + 右内容，点击目录项平滑滚动，滚动时自动高亮当前章节。
 *  内容整合了消息工作台的全部使用说明、功能介绍与快捷键速查。 */
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

const CONTENT_SCROLL_ID = 'help-content-scroll'

const chapters = ref([
  { id: 'overview', title: '快速开始', icon: 'home' },
  { id: 'conversation', title: '会话管理', icon: 'chat' },
  { id: 'contacts', title: '通讯录', icon: 'users' },
  { id: 'chat', title: '聊天功能', icon: 'message' },
  { id: 'message-actions', title: '消息操作', icon: 'mouse' },
  { id: 'quick-quote', title: '快捷报价', icon: 'zap' },
  { id: 'settings', title: '设置', icon: 'bell' },
  { id: 'shortcuts', title: '快捷键速查', icon: 'keyboard' },
])

const activeChapter = ref('overview')
const contentEl = ref(null)

/** 目录项点击 → 平滑滚动到对应章节 */
function jumpTo(id) {
  activeChapter.value = id
  nextTick(() => {
    const target = contentEl.value?.querySelector(`[data-chapter="${id}"]`)
    const wrap = contentEl.value
    if (target && wrap) {
      wrap.scrollTo({
        top: target.offsetTop - 12,
        behavior: 'smooth',
      })
    }
  })
}

/** 滚动监听：各章节顶缘进入可视区时高亮对应目录项 */
let scrollRaf = null
function onContentScroll() {
  if (scrollRaf) return
  scrollRaf = requestAnimationFrame(() => {
    scrollRaf = null
    const wrap = contentEl.value
    if (!wrap) return
    const wrapTop = wrap.scrollTop + 20
    let current = chapters.value[0].id
    for (const c of chapters.value) {
      const el = wrap.querySelector(`[data-chapter="${c.id}"]`)
      if (el && el.offsetTop <= wrapTop) current = c.id
    }
    if (current !== activeChapter.value) activeChapter.value = current
  })
}

onMounted(() => contentEl.value?.addEventListener('scroll', onContentScroll, { passive: true }))
onBeforeUnmount(() => {
  contentEl.value?.removeEventListener('scroll', onContentScroll)
  if (scrollRaf) cancelAnimationFrame(scrollRaf)
})

/* 复制按钮的视觉反馈 */
const copied = ref(false)
function copyAllShortcuts() {
  const text = chapters.value.find(c => c.id === 'shortcuts')?.title + '\n' +
    'Enter — 发送消息\n' +
    'Shift + Enter — 换行\n' +
    'Esc — 关闭浮层/退出提及\n' +
    '/ — 通讯录面板聚焦搜索\n' +
    '↑ ↓ — 提及浮层选择\n' +
    'Enter / Tab — 确认提及选择\n' +
    'Backspace — 删除整条 @ 提及\n' +
    '右键消息 — 复制/转发/多选/撤回\n' +
    '拖拽输入框顶边 — 调整高度\n' +
    '粘贴图片 — 直接发送\n' +
    '点击"会话"图标 — 定位下一条未读\n' +
    '会话右键 — 置顶/标已读/免打扰'
  navigator.clipboard?.writeText(text)
  copied.value = true
  setTimeout(() => copied.value = false, 1800)
}
</script>

<template>
  <div class="help-center">
    <!-- 左侧目录 -->
    <aside class="toc">
      <div class="toc-head">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/></svg>
        <span>帮助中心</span>
      </div>
      <nav class="toc-nav">
        <button
          v-for="c in chapters" :key="c.id"
          class="toc-item" :class="{ on: activeChapter === c.id }"
          @click="jumpTo(c.id)"
        >
          <span class="toc-dot"></span>
          <span class="toc-label">{{ c.title }}</span>
        </button>
      </nav>
      <div class="toc-foot">
        <span class="ver">SI 客服系统 · 帮助文档</span>
      </div>
    </aside>

    <!-- 右侧内容 -->
    <main ref="contentEl" class="content" :id="CONTENT_SCROLL_ID">
      <!-- 快速开始 -->
      <section data-chapter="overview" class="chapter">
        <h2 class="ch-title">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
          快速开始
        </h2>
        <div class="card">
          <p>欢迎使用 <b>SI 客服系统</b> 消息工作台。系统采用三栏布局，左侧是微信式图标导航栏，中间是会话/通讯录与聊天窗口，右侧是快捷报价拓展栏。</p>
          <div class="layout-diagram">
            <div class="rail"><div class="dot"></div><div class="dot"></div><div class="dot"></div><div class="dot"></div></div>
            <div class="list"></div>
            <div class="chat"></div>
            <div class="quote"></div>
            <div class="labels">
              <span>图标导航栏</span><span>列表</span><span>聊天窗口</span><span>快捷报价</span>
            </div>
          </div>
          <ul class="feature-list">
            <li><b>会话 / 通讯录切换</b> — 点击左栏前两个图标按钮即可在两种视图间切换</li>
            <li><b>帮助中心</b> — 当前页面，从左栏设置按钮上方的问号图标进入</li>
            <li><b>设置</b> — 左栏底部齿轮图标，可设置消息提示音</li>
            <li><b>账号切换</b> — 顶栏左侧显示当前绑定的聊天账号，点击可切换</li>
          </ul>
        </div>
      </section>

      <!-- 会话管理 -->
      <section data-chapter="conversation" class="chapter">
        <h2 class="ch-title">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/></svg>
          会话管理
        </h2>
        <div class="card">
          <h3>搜索会话</h3>
          <p>列表顶部搜索框支持按<b>显示名</b>、<b>匿名标识</b>、<b>首字母</b>、<b>拼音逐字</b>检索。搜索结果中命中关键词会以主色高亮。</p>
        </div>
        <div class="card">
          <h3>未读消息定位</h3>
          <p>点击左栏顶部的"会话"图标按钮，系统会自动定位到下一条有未读消息的会话并打开聊天窗口。末尾后自动循环回绕，直到全部未读都被处理。</p>
          <div class="tip-box">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>
            顶部红点徽章显示当前所有会话的未读总数，点击时会随定位自动清除
          </div>
        </div>
        <div class="card">
          <h3>会话右键菜单</h3>
          <table class="kv-table">
            <thead><tr><th>操作</th><th>说明</th></tr></thead>
            <tbody>
              <tr><td>置顶 / 取消置顶</td><td>置顶的会话会显示在列表顶部，背景加深，不显示"置顶"文字</td></tr>
              <tr><td>标为已读 / 未读</td><td>手动控制会话的未读状态</td></tr>
              <tr><td>消息免打扰</td><td>开启后新消息不推送铃声提醒，未读数字退化为纯红点</td></tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- 通讯录 -->
      <section data-chapter="contacts" class="chapter">
        <h2 class="ch-title">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
          通讯录
        </h2>
        <div class="card">
          <h3>好友与群聊</h3>
          <p>通讯录分为 <b>好友</b> 和 <b>群聊</b> 两个标签页。好友按字母 A–Z 自动分组，滚动时字母标题会吸顶显示，方便快速定位。</p>
        </div>
        <div class="card">
          <h3>搜索与跨 Tab 提示</h3>
          <p>在搜索框输入关键词时，如果另一个标签页中有匹配结果，系统会在当前页上方提示"在 X 中找到 N 条结果，点击切换"，一键跳转过去查看。</p>
          <div class="tip-box">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2 4.5 13.5H11L9.8 22 19 10h-6.5L13 2z"/></svg>
            快捷键：按 <kbd>/</kbd> 可快速聚焦搜索框（仅通讯录面板打开时生效）
          </div>
        </div>
      </section>

      <!-- 聊天功能 -->
      <section data-chapter="chat" class="chapter">
        <h2 class="ch-title">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
          聊天功能
        </h2>
        <div class="card">
          <h3>发送消息</h3>
          <ul class="feature-list">
            <li><kbd>Enter</kbd> — 发送当前输入框内容</li>
            <li><kbd>Shift</kbd> + <kbd>Enter</kbd> — 插入换行符</li>
            <li>输入框顶部可 <b>拖拽</b> 调整高度（72px ~ 300px）</li>
          </ul>
        </div>
        <div class="card">
          <h3>表情</h3>
          <p>点击输入框左侧的 <b>😀</b> 图标打开表情面板，选择表情后会直接插入到光标位置。</p>
        </div>
        <div class="card">
          <h3>@ 提及群成员</h3>
          <p>在群聊中输入 <kbd>@</kbd> 可唤起成员选择浮层。选择方式：</p>
          <table class="kv-table">
            <thead><tr><th>操作</th><th>说明</th></tr></thead>
            <tbody>
              <tr><td><kbd>↑</kbd> / <kbd>↓</kbd></td><td>在成员列表中上下选择</td></tr>
              <tr><td><kbd>Enter</kbd> / <kbd>Tab</kbd></td><td>确认选择当前高亮成员</td></tr>
              <tr><td><kbd>Backspace</kbd></td><td>紧贴 @ 片段时整块删除</td></tr>
              <tr><td><kbd>Esc</kbd></td><td>关闭 @ 浮层</td></tr>
            </tbody>
          </table>
        </div>
        <div class="card">
          <h3>发送文件与图片</h3>
          <ul class="feature-list">
            <li>点击输入框左侧的 <b>📎</b> 图标，打开系统文件选择器发送任意类型文件</li>
            <li>在输入框中 <b>直接粘贴图片</b>（截图、系统截图、网页复制图均可），系统会自动识别并发送</li>
          </ul>
        </div>
        <div class="card">
          <h3>图片全屏预览</h3>
          <p>点击聊天窗口中的任意图片可进入全屏预览模式，当前会话的所有图片会自动加载为可左右切换的列表，支持 <kbd>←</kbd> <kbd>→</kbd> 方向键快速翻页。</p>
        </div>
        <div class="card">
          <h3>备注与资料侧栏</h3>
          <p>点击聊天窗口顶部的对方备注名，或在消息列表中点击头像，可打开右侧资料侧栏，设置统一备注（全局生效）。按 <kbd>Esc</kbd> 或点击收起按钮可关闭。</p>
        </div>
      </section>

      <!-- 消息操作 -->
      <section data-chapter="message-actions" class="chapter">
        <h2 class="ch-title">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="3" width="12" height="18" rx="2"/><line x1="12" y1="18" x2="12" y2="18"/></svg>
          消息操作
        </h2>
        <div class="card">
          <h3>右键菜单</h3>
          <p>在任意消息上 <b>单击右键</b> 会弹出操作菜单，菜单项随消息类型和状态动态变化：</p>
          <table class="kv-table">
            <thead><tr><th>菜单项</th><th>说明</th></tr></thead>
            <tbody>
              <tr><td>复制 / 复制图片</td><td>文本消息复制文字内容；图片消息复制到剪贴板</td></tr>
              <tr><td>转发</td><td>将当前消息转发到其他会话</td></tr>
              <tr><td>多选</td><td>进入多选模式，勾选多条消息后合并转发</td></tr>
              <tr><td>撤回</td><td>自己发送且 2 分钟内的消息可撤回（灰色提示条替代原文）</td></tr>
            </tbody>
          </table>
        </div>
        <div class="card">
          <h3>多选与合并转发</h3>
          <p>通过右键菜单进入多选模式后，消息气泡左侧会出现勾选框，逐条点击勾选后，点击底部"转发"按钮选择目标会话即可一次性合并下发。切换会话或切换账号会自动退出多选模式。</p>
        </div>
        <div class="card">
          <h3>重新编辑撤回消息</h3>
          <p>撤回自己发送的消息后，气泡会变成灰色提示条。点击提示条上的"重新编辑"链接，原文会自动回填到输入框并聚焦，修改后重新发送即可。</p>
        </div>
        <div class="card">
          <h3>加载历史消息</h3>
          <p>聊天窗口滚动到 <b>顶部</b> 时会自动加载更早的历史消息，加载时会保留当前视野位置，不会因新增旧消息而跳走。</p>
        </div>
      </section>

      <!-- 快捷报价 -->
      <section data-chapter="quick-quote" class="chapter">
        <h2 class="ch-title">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2 4.5 13.5H11L9.8 22 19 10h-6.5L13 2z"/></svg>
          快捷报价
        </h2>
        <p class="section-intro">右侧拓展栏集成了完整的报价处理工作台，包含以下功能模块：</p>

        <div class="card">
          <h3>自动报价</h3>
          <ul class="feature-list">
            <li><b>AI 智能识别开关</b> — 关闭后进入普通模式，不自动分析新消息</li>
            <li><b>仅侧边预览</b> — 识别到询价后只在拓展栏展示报价卡片，不自动回复客户</li>
            <li><b>识别成功自动发送</b> — AI 识别后直接回复到会话中，适合稳定场景</li>
            <li><b>新消息触发流</b> — 实时展示所有正在处理的询价，15 秒自动刷新，支持暂停</li>
          </ul>
        </div>

        <div class="card">
          <h3>手动报价</h3>
          <p>提供四种子功能：</p>
          <table class="kv-table">
            <thead><tr><th>子功能</th><th>说明</th></tr></thead>
            <tbody>
              <tr><td>查询报价</td><td>输入 OE 号 / VIN / 配件名称，后端链式编排（识别 → 译码 → CRM → 爆炸图）返回结果</td></tr>
              <tr><td>AI 对话</td><td>与 AI 进行多轮对话查询配件信息</td></tr>
              <tr><td>第三方比价</td><td>聚合多个渠道的报价进行比价分析</td></tr>
              <tr><td>采购历史</td><td>查看过往的采购与报价记录</td></tr>
            </tbody>
          </table>
          <div class="tip-box">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
            VIN 查询时可在下方"配件名"输入框填写配件信息，帮助后端更精准地译码
          </div>
        </div>

        <div class="card">
          <h3>报价分析</h3>
          <p>展示报价处理的日/月 KPI 趋势数据，帮助运营人员洞察业务情况。</p>
        </div>

        <div class="card">
          <h3>报价设置</h3>
          <table class="kv-table">
            <thead><tr><th>设置项</th><th>说明</th></tr></thead>
            <tbody>
              <tr><td>AI 智能识别</td><td>全局开关，控制是否自动分析新消息中的询价意图</td></tr>
              <tr><td>自动报价模式</td><td>切换"仅侧边预览"与"识别成功自动发送"</td></tr>
              <tr><td>配件黑名单</td><td>命中黑名单的配件不报价、不自动发送，最多 20 个</td></tr>
              <tr><td>客户等级价格系数</td><td>VIP-A / VIP-B / 普通客户分别设置报价系数（报价 = 我方价 × 系数）</td></tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- 设置 -->
      <section data-chapter="settings" class="chapter">
        <h2 class="ch-title">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>
          设置
        </h2>
        <div class="card">
          <h3>消息提示音</h3>
          <p>点击左栏底部的齿轮图标打开设置弹窗，可在系统内置铃声与自定义铃声之间切换。</p>
          <ul class="feature-list">
            <li>点击 <b>播放/停止</b> 按钮可试听铃声效果</li>
            <li>选择即生效，新消息按所选铃声提醒</li>
            <li>支持 <b>自定义铃声</b> 上传与删除</li>
            <li>点击"恢复默认"可一键还原出厂铃声</li>
          </ul>
        </div>
      </section>

      <!-- 快捷键速查 -->
      <section data-chapter="shortcuts" class="chapter">
        <h2 class="ch-title">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M6 8h.01M10 8h.01M14 8h.01M18 8h.01M8 12h.01M12 12h.01M16 12h.01M7 16h10"/></svg>
          快捷键速查
          <button class="copy-btn" @click="copyAllShortcuts">
            <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
            {{ copied ? '已复制' : '复制全部' }}
          </button>
        </h2>
        <div class="card">
          <div class="shortcut-grid">
            <div class="shortcut-row"><kbd>Enter</kbd><span>发送消息</span></div>
            <div class="shortcut-row"><kbd>Shift</kbd> + <kbd>Enter</kbd><span>插入换行</span></div>
            <div class="shortcut-row"><kbd>Esc</kbd><span>关闭 @ 浮层 / 退出提及编辑 / 关闭资料侧栏</span></div>
            <div class="shortcut-row"><kbd>/</kbd><span>通讯录面板聚焦搜索框</span></div>
            <div class="shortcut-row"><kbd>↑</kbd> <kbd>↓</kbd><span>@ 提及浮层选择成员</span></div>
            <div class="shortcut-row"><kbd>Enter</kbd> / <kbd>Tab</kbd><span>确认 @ 提及选择</span></div>
            <div class="shortcut-row"><kbd>Backspace</kbd><span>紧贴 @ 片段时整块删除</span></div>
            <div class="shortcut-row"><kbd>右键</kbd> 消息<span>复制 / 转发 / 多选 / 撤回</span></div>
            <div class="shortcut-row"><kbd>拖拽</kbd> 输入框顶边<span>调整输入框高度</span></div>
            <div class="shortcut-row"><kbd>粘贴</kbd> 图片<span>直接发送（系统截图、网页复制图）</span></div>
            <div class="shortcut-row">点击 <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px"><path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/></svg> 会话图标<span>定位下一条未读消息</span></div>
            <div class="shortcut-row">会话 <kbd>右键</kbd><span>置顶 / 标已读 / 消息免打扰</span></div>
          </div>
        </div>
      </section>

      <div class="content-foot">SI 客服系统 · 帮助文档 &nbsp;·&nbsp; 如需反馈请联系系统管理员</div>
    </main>
  </div>
</template>

<style scoped>
.help-center {
  display: flex;
  height: 100%;
  background: var(--c-bg);
  overflow: hidden;
}

/* ===== 左侧目录 ===== */
.toc {
  width: 200px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--c-panel);
  border-right: 1px solid var(--c-border);
  overflow: hidden;
}
.toc-head {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 14px 14px 10px;
  font-weight: 700;
  font-size: 13px;
  color: var(--c-primary);
  border-bottom: 1px solid var(--c-border);
}
.toc-nav {
  flex: 1;
  overflow-y: auto;
  padding: 8px 8px;
}
.toc-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 7px 10px;
  border: none;
  border-radius: var(--r-md);
  background: none;
  color: var(--c-text-sub);
  font-size: 12px;
  font-family: inherit;
  text-align: left;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.toc-item:hover {
  background: var(--c-primary-soft);
  color: var(--c-primary);
}
.toc-item.on {
  background: var(--c-primary-soft);
  color: var(--c-primary-deep);
  font-weight: 600;
}
.toc-dot {
  width: 6px;
  height: 6px;
  flex-shrink: 0;
  border-radius: 50%;
  background: var(--c-border-strong);
  transition: background 0.15s, transform 0.15s;
}
.toc-item.on .toc-dot {
  background: var(--c-primary);
  transform: scale(1.5);
}
.toc-foot {
  padding: 10px 14px;
  border-top: 1px solid var(--c-border);
  font-size: 10px;
  color: var(--c-border-strong);
}

/* ===== 右侧内容 ===== */
.content {
  flex: 1;
  overflow-y: auto;
  padding: 24px 40px 40px;
  scroll-behavior: smooth;
}

.chapter { margin-bottom: 36px; }
.chapter:last-child { margin-bottom: 0; }

.ch-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 17px;
  font-weight: 700;
  color: var(--c-text);
  margin: 0 0 16px;
  padding-bottom: 10px;
  border-bottom: 2px solid var(--c-primary-soft);
}
.ch-title svg {
  color: var(--c-primary);
}

.copy-btn {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  font-size: 11px;
  font-weight: 400;
  border: 1px solid var(--c-border-strong);
  border-radius: var(--r-md);
  background: var(--c-panel);
  color: var(--c-text-sub);
  cursor: pointer;
  transition: all 0.15s;
}
.copy-btn:hover {
  border-color: var(--c-primary);
  color: var(--c-primary);
  background: var(--c-primary-soft);
}

.section-intro {
  margin: -8px 0 14px;
  font-size: 12px;
  color: var(--c-text-sub);
  line-height: 1.7;
}

.card {
  background: var(--c-panel);
  border: 1px solid var(--c-border);
  border-radius: var(--r-lg);
  padding: 16px 18px;
  margin-bottom: 14px;
  box-shadow: 0 1px 3px rgba(23, 35, 58, 0.04);
}
.card:last-child { margin-bottom: 0; }
.card h3 {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text);
}
.card p {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.75;
  color: var(--c-text-sub);
}
.card p + h3,
.card ul + h3,
.card .tip-box + h3,
.card .kv-table + h3 {
  margin-top: 16px;
}

.feature-list {
  margin: 8px 0 0;
  padding-left: 18px;
  font-size: 12.5px;
  line-height: 1.9;
  color: var(--c-text-sub);
}
.feature-list li b {
  color: var(--c-text);
  font-weight: 600;
}

/* 布局示意图 */
.layout-diagram {
  display: grid;
  grid-template-columns: 32px 80px 1fr 80px;
  gap: 4px;
  margin: 12px 0 14px;
  position: relative;
}
.layout-diagram .rail {
  height: 90px;
  background: var(--c-primary);
  border-radius: var(--r-sm);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 6px;
}
.layout-diagram .rail .dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.7);
}
.layout-diagram .list {
  height: 90px;
  background: var(--c-border);
  border-radius: var(--r-sm);
}
.layout-diagram .chat {
  height: 90px;
  background: var(--c-primary-soft);
  border-radius: var(--r-sm);
}
.layout-diagram .quote {
  height: 90px;
  background: #fdebea;
  border-radius: var(--r-sm);
}
.layout-diagram .labels {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: 32px 80px 1fr 80px;
  gap: 4px;
  margin-top: 4px;
}
.layout-diagram .labels span {
  text-align: center;
  font-size: 9px;
  color: var(--c-text-sub);
}

/* 提示框 */
.tip-box {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-top: 10px;
  padding: 10px 12px;
  background: var(--c-warn-soft);
  border: 1px solid #fbe7cc;
  border-radius: var(--r-md);
  font-size: 11.5px;
  color: #a86a1a;
  line-height: 1.6;
}
.tip-box svg {
  flex-shrink: 0;
  margin-top: 1px;
  color: var(--c-warn);
}

/* 键值表格 */
.kv-table {
  width: 100%;
  margin-top: 6px;
  border-collapse: collapse;
  font-size: 12px;
}
.kv-table th {
  text-align: left;
  padding: 7px 10px;
  font-weight: 600;
  font-size: 11px;
  color: var(--c-text-sub);
  background: var(--c-bg);
  border-bottom: 1px solid var(--c-border);
}
.kv-table td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--c-border);
  color: var(--c-text-sub);
  line-height: 1.65;
}
.kv-table tbody tr:last-child td {
  border-bottom: none;
}
.kv-table td:first-child {
  font-weight: 600;
  color: var(--c-text);
  white-space: nowrap;
}

/* 快捷键网格 */
.shortcut-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px 24px;
}
.shortcut-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: var(--r-sm);
  font-size: 12px;
  color: var(--c-text-sub);
  transition: background 0.12s;
}
.shortcut-row:hover {
  background: var(--c-primary-soft);
  color: var(--c-text);
}
.shortcut-row kbd {
  flex-shrink: 0;
  min-width: 22px;
  height: 20px;
  padding: 0 6px;
  font-size: 11px;
  font-family: var(--font-num);
  font-weight: 600;
  color: var(--c-primary-deep);
  background: var(--c-primary-soft);
  border: 1px solid var(--c-border-strong);
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 1px 0 rgba(23, 35, 58, 0.08);
}

.content-foot {
  margin-top: 40px;
  padding-top: 20px;
  border-top: 1px solid var(--c-border);
  text-align: center;
  font-size: 11px;
  color: var(--c-border-strong);
}

/* 响应式：窄屏收起目录 */
@media (max-width: 900px) {
  .toc { width: 150px; }
  .content { padding: 20px 24px 30px; }
  .shortcut-grid { grid-template-columns: 1fr; }
}
</style>
