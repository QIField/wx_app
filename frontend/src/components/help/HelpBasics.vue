<template>
  <!-- 基础使用章节：快速开始 / 会话管理 / 通讯录 / 聊天功能 -->
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
</template>

<style scoped src="./help-shared.css"></style>
