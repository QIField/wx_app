/* ===== app.js · 渲染 + 演示引擎（严格模式，无外部依赖） ===== */
"use strict";

/* ---------- 小工具 ---------- */
const $ = (sel) => document.querySelector(sel)
function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
}
const ICON_OK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>'

/* ---------- hero 数据 ---------- */
function renderStats() {
  $("#stats").innerHTML = M.stats.map((s) =>
    `<div class="stat"><b>${esc(s.v)}</b><i>${esc(s.k)}</i><p>${esc(s.d)}</p></div>`
  ).join("")
}

/* ---------- 根因两卡 ---------- */
const WHY = [
  {
    h: "为什么视口会跳？",
    body: `浏览器只保证 <code>scrollTop</code> 数值不变，不保证「你正看的内容」不动。
      上方图片长高 Δpx，下方全部内容整体下推 Δpx——你正看的消息瞬间位移 Δ。
      多图集中加载时连跳数次，观感即"反复跳"。`,
  },
  {
    h: "高度由谁决定？",
    body: `加载前：占位块 <code>min-height: 105px</code>（瞎猜的）。
      加载后：图片真实尺寸，由服务端文件决定。
      唯一根治方式 = 让"加载前"就知道真实尺寸 → 服务端把宽高随消息一起下发（S2）。`,
  },
]

/* ---------- 方案卡 ---------- */
function renderSolutions() {
  const priCls = { P0: "p0", "P1 · 根治": "p1", 备选: "px" }
  $("#sols").innerHTML = M.solutions.map((s) => `
    <div class="fix-card ${s.id === "s1" ? "rec" : ""}">
      <div class="fc-head">
        <span class="pri ${priCls[s.pri] || "px"}">${esc(s.pri)}</span><h3>${esc(s.title)}</h3>
      </div>
      <div class="tagline">${esc(s.tagline)}</div>
      <p class="principle">${esc(s.principle)}</p>
      ${s.diff.map((d) => `
        <div class="diff"><pre>${esc(d.code)}</pre>${d.note ? `<div class="note"># ${esc(d.note)}</div>` : ""}</div>
      `).join("")}
      <div class="pl"><h4>优劣</h4>
        <ul class="good">${s.pros.map((p) => `<li>${esc(p)}</li>`).join("")}</ul>
        <ul class="bad">${s.cons.map((p) => `<li>${esc(p)}</li>`).join("")}</ul>
      </div>
      <div class="fc-foot"><span>${esc(s.effort)}</span><span>风险：${esc(s.risk)}</span></div>
    </div>
  `).join("")
}

/* ---------- 落地清单 ---------- */
function renderChecklist() {
  const box = $("#cks")
  const paint = () => {
    const done = box.querySelectorAll(".ck.done").length
    $("#pbar").style.width = `${(done / M.checklist.length) * 100}%`
  }
  box.innerHTML = M.checklist.map((t, i) => `
    <div class="ck" data-i="${i}">
      <span class="box">${ICON_OK}</span><span>${esc(t)}</span>
    </div>
  `).join("")
  box.querySelectorAll(".ck").forEach((el) => {
    el.addEventListener("click", () => { el.classList.toggle("done"); paint() })
  })
  paint()
}

/* ---------- 演示引擎 ----------
 * 剧本：6 条消息（3 文本 + 3 图片），视窗停在底部；上方图片依次加载完成。
 * base: 占位 105 → 真实高度，突变（跳）
 * s1  : 同 base，但每次变化时 scrollTop += delta（视口补偿，不跳）
 * s2  : 占位直接 = 真实高度（模拟后端下发 w/h → aspect-ratio），无变化
 * s3  : 固定 135 高 + 裁切角标，无变化
 */
const FINAL_H = [150, 235, 185] // 三张图的真实高度
const LOAD_GAP = 900            // 加载间隔 ms
let timer = null

function scriptFor(id) {
  return [
    { kind: "text", dir: "in", name: "客户 张锐", text: "这个是绵啊！" },
    { kind: "text", dir: "out", name: "客服", text: "收到，我看一下～" },
    { kind: "img", dir: "in", name: "客户 张锐", h: FINAL_H[0] },
    { kind: "text", dir: "in", name: "客户 张锐", text: "拍给你看了" },
    { kind: "img", dir: "in", name: "客户 张锐", h: FINAL_H[1] },
    { kind: "text", dir: "out", name: "客服", text: "这个材质看着不错，我确认下库存" },
    { kind: "img", dir: "in", name: "客户 张锐", h: FINAL_H[2] },
    { kind: "text", dir: "in", name: "客户 张锐", text: "在底部这条，别走丢呀" },
  ]
}

function buildDom(script, id) {
  const phone = $("#phone")
  phone.innerHTML = ""
  return script.map((m) => {
    const el = document.createElement("div")
    el.className = `dm ${m.dir}`
    if (m.kind === "text") {
      el.innerHTML = `<div class="dm-bubble"><div class="who">${esc(m.name)}</div>${esc(m.text)}</div>`
    } else {
      let phH // 占位高度
      if (id === "s2") phH = m.h
      else if (id === "s3") phH = 135
      else phH = 105
      const crop = id === "s3" ? " crop" : ""
      const note = id === "s2" ? `<span class="ratio-note">aspect-ratio: 150 / ${m.h}</span>` : ""
      el.innerHTML = `<div class="dm-bubble" style="padding:2px">
        <div class="who" style="padding:0 8px">${esc(m.name)}</div>
        <div class="dimg${crop}" style="height:${phH}px">${note}</div>
      </div>`
    }
    phone.appendChild(el)
    return el
  })
}

function runDemo(id) {
  if (timer) { timer.forEach((t) => clearTimeout(t)); timer = null }
  let jumps = 0
  let shift = 0
  const setM = () => {
    const mj = $("#mJump"); const ms = $("#mShift")
    mj.textContent = jumps
    mj.className = jumps === 0 ? "good" : "bad"
    ms.textContent = `${shift}px`
    ms.className = shift === 0 ? "good" : "bad"
    $("#mCrop").textContent = id === "s3" ? "180×135 裁切" : "无"
    $("#mCrop").className = id === "s3" ? "bad" : "good"
    const v = $("#verdict")
    if (id === "base") v.textContent = "占位瞎猜 105px，加载后高度突变，你正看的内容被瞬间推走。"
    else if (id === "s1") v.textContent = "高度照变，但每次变化都把差值补偿回 scrollTop——视野钉在原处。"
    else if (id === "s2") v.textContent = "服务端下发宽高，占位即真实尺寸：高度从头到尾没变过。"
    else v.textContent = "统一固定盒零跳动，但竖图横图都被裁掉细节——客服场景不可接受。"
  }
  setM()

  const dom = buildDom(scriptFor(id), id)
  const phone = $("#phone")
  phone.scrollTop = phone.scrollHeight // 初始停在底部

  const imgEls = dom
    .map((el, i) => ({ el, i }))
    .filter(({ el, i }) => scriptFor(id)[i].kind === "img")

  timer = imgEls.map(({ el }, k) => setTimeout(() => {
    const box = el.querySelector(".dimg")
    const phH = parseInt(box.style.height, 10)
    const realH = id === "s3" ? 135 : FINAL_H[k]
    const delta = realH - phH
    if (delta !== 0) {
      if (id === "base") {
        jumps += 1
        shift += delta // 视口内容被推走 delta
      } else if (id === "s1") {
        jumps += 0 // 高度变了，但视口补偿 → 用户无感
        shift += 0
      }
      if (id === "base" || id === "s1") {
        box.classList.add("flash")
        setTimeout(() => box.classList.remove("flash"), 500)
      }
    }
    box.style.height = `${realH}px`
    box.classList.add("ok")
    if (id === "s1") phone.scrollTop += delta // 锚定补偿：视野不动
    setM()
  }, 1200 + k * LOAD_GAP))
}

/* ---------- 策略切换 ---------- */
function renderTabs() {
  const tabs = $("#tabs")
  tabs.innerHTML = M.strategies.map((s, i) =>
    `<button class="tab ${i === 0 ? "on" : ""}" data-id="${s.id}" title="${esc(s.desc)}">${esc(s.label)}</button>`
  ).join("")
  tabs.querySelectorAll(".tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      tabs.querySelectorAll(".tab").forEach((b) => b.classList.remove("on"))
      btn.classList.add("on")
      runDemo(btn.dataset.id)
    })
  })
  $("#rerun").addEventListener("click", () => {
    const cur = tabs.querySelector(".tab.on")
    runDemo(cur ? cur.dataset.id : "base")
  })
}

/* ---------- 启动 ---------- */
renderStats()
$("#why").innerHTML = WHY.map((w) => `<div class="card"><h3>${esc(w.h)}</h3><p>${w.body}</p></div>`).join("")
renderSolutions()
renderChecklist()
renderTabs()
runDemo("base")
