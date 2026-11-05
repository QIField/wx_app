/* app.js — 渲染与交互（vanilla，无依赖） */
(function () {
  "use strict";
  var M = window.MOCK;

  /* ---------- 图标（Lucide 内联，按语义选用） ---------- */
  var I = {
    check: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
    x: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
    clock: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
    zap: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>',
    chev: '<svg class="fix-chev" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>',
    arrow: '<svg class="cc-arrow" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>',
    shield: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/></svg>',
    circle: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/></svg>',
  };

  var $ = function (sel) { return document.querySelector(sel); };
  var el = function (tag, cls, html) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (html != null) n.innerHTML = html;
    return n;
  };

  /* ---------- 01 结论卡 ---------- */
  M.verdict.points.forEach(function (p) {
    var c = el("div", "v-card");
    c.appendChild(el("span", "k", p.k));
    c.appendChild(el("p", "", p.v));
    $("#verdict").appendChild(c);
  });

  /* ---------- 02 时间线 ---------- */
  M.timeline.forEach(function (t) {
    var item = el("div", "tl-item " + t.level);
    var ms = t.ms == null ? "进程退出" : (t.ms / 1000).toFixed(t.ms < 1000 ? 2 : 1) + "s";
    item.innerHTML =
      '<div class="tl-row"><span class="tl-time">' + t.time + "</span>" +
      '<span class="tl-ms">' + ms + "</span>" +
      (t.code == null ? "" : '<span class="tl-code">HTTP ' + t.code + "</span>") +
      '<span class="tl-code">' + (t.level === "dead" ? "CONNECTION_REFUSED" : "") + "</span></div>" +
      '<div class="tl-desc">' + t.desc + "</div>";
    item.addEventListener("click", function () { item.classList.toggle("open"); });
    $("#timelineList").appendChild(item);
  });

  /* ---------- 03 根因链 ---------- */
  M.causes.forEach(function (c, i) {
    var card = el("div", "cc-card" + (c.level === "根因" ? " root" : ""));
    card.innerHTML = '<div class="cc-lv">' + c.level + " · " + (i + 1) + "</div><h3>" + c.title + "</h3><p>" + c.desc + "</p>";
    if (i < M.causes.length - 1) card.innerHTML += I.arrow;
    $("#causeChain").appendChild(card);
  });

  /* ---------- 04 方案卡 ---------- */
  M.fixes.forEach(function (f) {
    var card = el("div", "fix-card");
    var head = el("div", "fix-head");
    head.innerHTML = '<span class="tag ' + f.pri.toLowerCase() + '">' + f.pri + "</span><h3>" + f.title + '</h3><span class="fix-file">' + f.file + "</span>" + I.chev;
    var body = el("div", "fix-body");
    var eff = el("div", "fix-effect", I.zap + "<span>" + f.effect + "</span>");
    var diff = el("div", "diff");
    f.diff.forEach(function (d) {
      var op = d.op === "+" ? "+" : d.op === "-" ? "-" : " ";
      var cls = d.op === "+" ? "add" : d.op === "-" ? "del" : "ctx";
      d.text.split("\n").forEach(function (line) {
        var safe = line.replace(/&/g, "&amp;").replace(/</g, "&lt;");
        diff.appendChild(el("div", "diff-line " + cls, '<span class="op">' + op + "</span><span>" + safe + "</span>"));
      });
    });
    body.appendChild(eff); body.appendChild(diff);
    head.addEventListener("click", function () { card.classList.toggle("open"); });
    card.appendChild(head); card.appendChild(body);
    $("#fixList").appendChild(card);
  });

  /* ---------- 05 修复前后模拟 ---------- */
  var mode = "before";
  var jitter = true;
  var running = false;
  var stepsBox = $("#simSteps"), resultBox = $("#simResult"), note = $("#simNote"), panel = $("#simPanel");

  function plan() {
    // 返回 {steps:[{label, ms, kind}], result:{kind, msg}}；kind: ok|hang|err|rebuild
    if (mode === "before") {
      if (jitter) return {
        steps: [
          { label: "浏览器 → Vite 代理", ms: "0.05s" },
          { label: "后端收到请求", ms: "0.01s" },
          { label: "查询远程 MySQL（公网抖动）", ms: "10.2s", kind: "hang" },
        ],
        result: { kind: "fail", msg: "10.0s 前端超时 · axios ECONNABORTED —— 后端 10.2s 才返回 200，浏览器早已放弃。你重试 4 次都是这个循环。" },
      };
      return {
        steps: [
          { label: "浏览器 → Vite 代理", ms: "0.04s" },
          { label: "后端收到请求", ms: "0.01s" },
          { label: "查询远程 MySQL", ms: "0.09s" },
        ],
        result: { kind: "ok", msg: "0.9s 登录成功 · HTTP 200（网络正常时，修复前后差别不大——问题只在抖动窗口暴露）" },
      };
    }
    if (jitter) return {
      steps: [
        { label: "浏览器 → Vite 代理", ms: "0.05s" },
        { label: "后端收到请求", ms: "0.01s" },
        { label: "pool_pre_ping 探活", ms: "0.2s" },
        { label: "死连接 → 自动重建", ms: "0.6s", kind: "rebuild" },
        { label: "查询远程 MySQL（抖动中）", ms: "0.9s" },
      ],
      result: { kind: "ok", msg: "1.2s 登录成功 · HTTP 200 —— 抖动期自愈，用户无感；也不会再出现死连接 500。" },
    };
    return {
      steps: [
        { label: "浏览器 → Vite 代理", ms: "0.04s" },
        { label: "后端收到请求", ms: "0.01s" },
        { label: "pool_pre_ping 探活", ms: "0.05s" },
        { label: "查询远程 MySQL", ms: "0.09s" },
      ],
      result: { kind: "ok", msg: "0.6s 登录成功 · HTTP 200" },
    };
  }

  function renderSteps(plan0) {
    stepsBox.innerHTML = "";
    plan0.steps.forEach(function (s) {
      var ic = s.kind === "hang" || s.kind === "rebuild" ? I.clock : I.circle;
      var row = el("div", "s-step", '<span class="st-ic">' + ic + "</span><span>" + s.label + '</span><span class="st-ms">' + (s.ms || "") + "</span>");
      row.dataset.kind = s.kind || "";
      stepsBox.appendChild(row);
    });
  }

  function setMode(m) {
    mode = m;
    document.querySelectorAll("#segMode button").forEach(function (b) {
      b.classList.toggle("on", b.dataset.mode === m);
      b.classList.toggle("bad-mode", b.dataset.mode === "before" && m === "before");
    });
    panel.classList.toggle("bad-mode", m === "before");
    note.textContent = m === "before"
      ? (jitter ? "当前：修复前 + 抖动开启。点“模拟登录”重放 16:22:57 那次请求。" : "当前：修复前，网络正常（此时无差别，问题只在抖动窗口暴露）。")
      : (jitter ? "当前：修复后 + 抖动开启。pool_pre_ping 会先探活再重建连接。" : "当前：修复后，网络正常。");
  }

  document.querySelectorAll("#segMode button").forEach(function (b) {
    b.addEventListener("click", function () { if (!running) setMode(b.dataset.mode); });
  });
  var sw = $("#swJitter");
  function toggleJitter() {
    if (running) return;
    jitter = !jitter;
    sw.classList.toggle("on", jitter);
    sw.setAttribute("aria-checked", jitter);
    setMode(mode);
  }
  sw.addEventListener("click", toggleJitter);
  sw.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggleJitter(); } });

  var runBtn = $("#btnRun");
  var clock = I.clock;
  runBtn.addEventListener("click", function () {
    if (running) return;
    running = true;
    runBtn.disabled = true;
    resultBox.className = "sim-result";
    var plan0 = plan();
    renderSteps(plan0);
    var rows = stepsBox.querySelectorAll(".s-step");
    var i = 0;
    (function next() {
      if (i >= rows.length) {
        var r = plan0.result;
        resultBox.innerHTML = (r.kind === "ok" ? I.shield : I.x) + "<span>" + r.msg + "</span>";
        resultBox.className = "sim-result show " + r.kind;
        running = false;
        runBtn.disabled = false;
        return;
      }
      var row = rows[i], kind = row.dataset.kind;
      row.classList.add("run");
      if (kind === "hang") {
        // 计时器演示 10s 阈值（2.5× 加速），到点即“前端放弃”
        var t0 = performance.now(), msEl = row.querySelector(".st-ms");
        var timer = setInterval(function () {
          var p = (performance.now() - t0) / 400; // 4s 走完 10s
          msEl.textContent = Math.min(p * 10, 10.2).toFixed(1) + "s";
          if (p >= 1) {
            clearInterval(timer);
            row.classList.remove("run"); row.classList.add("err");
            row.querySelector(".st-ic").innerHTML = I.x;
            msEl.textContent = "已放弃";
            i++; next();
          }
        }, 60);
        return;
      }
      var dur = kind === "rebuild" ? 700 : 420;
      setTimeout(function () {
        row.classList.remove("run"); row.classList.add("done");
        row.querySelector(".st-ic").innerHTML = I.check;
        i++; next();
      }, dur);
    })();
  });

  /* ---------- 06 落地清单 ---------- */
  var todos = [
    { t: "连接池加 pool_pre_ping + pool_recycle=280（extensions.py）", who: "P0 · 5min" },
    { t: "新增 restart-dev.bat 循环守护，崩溃日志落 logs/backend.log", who: "P0 · 10min" },
    { t: "登录接口改用 30s 超时的独立实例，错误文案按类型区分", who: "P1 · 20min" },
    { t: "/api/health 加 DB 探活，前端顶栏红灯提示", who: "P1 · 30min" },
    { t: "规划：测试库本地化/内网化，评估 2s 轮询降频", who: "P2 · 排期" },
  ];
  var done = 0;
  todos.forEach(function (t) {
    var l = el("label", "chk");
    l.innerHTML = '<input type="checkbox"><span>' + t.t + '</span><span class="who">' + t.who + "</span>";
    l.querySelector("input").addEventListener("change", function (e) {
      done += e.target.checked ? 1 : -1;
      $("#chkCount").textContent = done + " / " + todos.length;
      $("#chkBar").style.width = (done / todos.length * 100) + "%";
    });
    $("#checkList").appendChild(l);
  });

  setMode("before");
})();
