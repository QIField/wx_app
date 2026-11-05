/* mock.js — 全部数据来自 2026-11-04 真实诊断（access_log / middle_call_log / 实测探针），仅作展示 */
window.MOCK = {
  verdict: {
    title: "登录从未“密码错误”，失败的是三条不同的链路",
    points: [
      { k: "慢", v: "16:22:57 那次登录后端实际成功（HTTP 200），但耗时 10.2s，压过前端 axios 10s 超时线，浏览器先放弃" },
      { k: "死", v: "公网 MySQL 的池化连接被网络抖动静默掐断，连接池无 pre_ping，后端拿到死连接秒回 500（实测 0.01s 返回 500）" },
      { k: "没", v: "后端进程无任何守护，最终退出，5000 端口拒绝连接——系统彻底不可用" },
    ],
  },

  timeline: [
    { time: "15:33:02", ms: 4104, code: 200, level: "warn",
      desc: "登录 4.1s。同窗口媒体下载 1.5~9.1s，公网链路开始劣化" },
    { time: "15:50:50", ms: 23049, code: 200, level: "bad",
      desc: "登录 23.0s（成功但浏览器 10s 已放弃）。窗口内中间方 API 单次 5~11.7s，资料同步 15 次 brief_info 全部超 5s" },
    { time: "15:51:19", ms: 15768, code: 200, level: "bad", desc: "重试 15.8s，仍压线" },
    { time: "15:51:57", ms: 17364, code: 200, level: "bad", desc: "重试 17.4s" },
    { time: "15:53:07", ms: 12593, code: 200, level: "bad", desc: "重试 12.6s——4 次全部“前端超时、后端成功”" },
    { time: "15:57:48", ms: 44, code: 401, level: "ok",
      desc: "探针实测 44ms（401=密码错误属正常）。公网链路恢复" },
    { time: "16:22:57", ms: 10185, code: 200, level: "bad",
      desc: "你报告“还是超时”的那次：10.185s，比 10s 超时线多 185ms" },
    { time: "16:24:xx", ms: 15, code: 500, level: "bad",
      desc: "秒回 500×3：数据库本身 9ms 正常，是池里的公网死连接在报错（无 pre_ping 不探活）" },
    { time: "现在", ms: null, code: null, level: "dead",
      desc: "backend.app 进程已退出，5000 端口拒绝连接，系统彻底不可用" },
  ],

  causes: [
    { id: "net", title: "公网依赖抖动", level: "根因",
      desc: "数据库在公网（113.46.196.69 远程测试库），中间方 API 也是公网。15:50~15:53 网络劣化：中间方单次调用 5~11.7s、远程库查询同步变慢。恢复后实测：DB 连接 0.13s、查询 9ms、登录 44ms。" },
    { id: "slow", title: "慢登录 × 前端 10s 超时", level: "放大器",
      desc: "登录路径全是数据库操作（查用户/写 last_login/审计/访问日志），公网抖动时整体被拖到 10~23s；axios 10s 一刀切，超过即报“超时”，用户重试 4 次全部浪费。" },
    { id: "dead", title: "死连接无探活", level: "放大器",
      desc: "公网 TCP 长连接会被 NAT/防火墙在空闲期静默掐断，这是常态而非偶发。SQLAlchemy 连接池未开 pool_pre_ping / pool_recycle，掐断后的连接被直接复用 → 查询抛异常 → 500。" },
    { id: "guard", title: "进程无守护", level: "恶化器",
      desc: "后端裸跑在终端里，异常退出后无人拉起，5000 端口拒绝连接，故障从“难用”升级为“不可用”，且无崩溃日志可查。" },
  ],

  fixes: [
    { id: "ping", pri: "P0", title: "连接池探活 + 定期回收", file: "backend/extensions.py",
      effect: "杜绝死连接 500；公网断连后自愈",
      diff: [
        { op: "-", text: 'db = SQLAlchemy()' },
        { op: "+", text: 'db = SQLAlchemy(engine_options={\n    "pool_pre_ping": True,    # 取连接前探活，死连接自动重建\n    "pool_recycle": 280,      # 280s 主动回收，避开 NAT 空闲掐断（一般 300s）\n})' },
      ] },
    { id: "guard", pri: "P0", title: "一键重启 + 崩溃留痕", file: "restart-dev.bat（新增）",
      effect: "进程秒级恢复；退出原因落文件可查",
      diff: [
        { op: "+", text: '@echo off\ncd /d %~dp0\n:loop\n.venv\\Scripts\\python.exe -m backend.app >> logs\\backend.log 2>&1\necho [%date% %time%] backend exited, restarting... >> logs\\backend.log\ntimeout /t 3 >nul\ngoto loop' },
      ] },
    { id: "ux", pri: "P1", title: "登录超时放宽 + 错误分类", file: "frontend/src/api.js",
      effect: "慢窗口不再假失败；报错能分清是哪种失败",
      diff: [
        { op: "-", text: 'const http = axios.create({ timeout: 10000 })' },
        { op: "+", text: 'const http = axios.create({ timeout: 10000 })\nexport const authHttp = axios.create({ timeout: 30000 }) // 登录低频，容忍公网抖动' },
        { op: "+", text: "// 错误文案区分：ECONNABORTED→“服务响应慢/超时”，\n// ERR_NETWORK→“服务未启动”，401→“账号或密码错误”" },
      ] },
    { id: "health", pri: "P1", title: "/api/health 增加 DB 探活", file: "backend/api/health.py",
      effect: "前端顶栏亮红灯，故障从“登录超时”变成“一眼看到库不通”",
      diff: [
        { op: "+", text: '@bp.get("/api/health")\ndef health():\n    db_ok = _ping_db()   # select 1，200ms 超时\n    return {"ok": True, "db": db_ok}' },
      ] },
    { id: "arch", pri: "P2", title: "公网依赖收敛（架构建议）", file: "规划项",
      effect: "从根上消除抖动面",
      diff: [
        { op: "+", text: "· 测试库本地化或内网化（当前公网库是最大抖动源）\n· get_message 2s 轮询评估降频/批量\n· 中间方调用统一超时与熔断，避免劣化期排队放大" },
      ] },
  ],
};
