<script setup>
/** 快捷键速查的一键复制（内容章节自带的交互，随章节放在这里） */
import { ref } from 'vue'

const copied = ref(false)
function copyAllShortcuts() {
  const text = '快捷键速查\n' +
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
  <!-- 操作与速查章节：消息操作 / 快捷报价 / 设置 / 快捷键速查 -->
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
</template>

<style scoped src="./help-shared.css"></style>
