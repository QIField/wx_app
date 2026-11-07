/* ===== 方案页交互：状态集中在这里，数据统一来自 mock.js ===== */

const state = {
  filter: "all",
  demoView: "live",
  devices: DEMO_DEVICES.map((d) => ({ ...d })),
  checks: new Set(),
};

const $ = (sel, root = document) => root.querySelector(sel);

/* ---------- Toast ---------- */
let toastTimer = null;
function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.add("is-on");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("is-on"), 2600);
}

/* ---------- 02 字段字典 ---------- */
function renderFields() {
  const grid = $("#fieldGrid");
  grid.innerHTML = "";
  FIELDS.forEach((f, i) => {
    const card = document.createElement("article");
    card.className = "field reveal";
    card.style.animationDelay = `${0.04 * i}s`;
    card.innerHTML = `
      <div class="field-top">
        <span class="field-name">${f.name}</span>
        <span class="field-type">${f.type}</span>
      </div>
      <div class="field-sum">${f.sum}</div>
      <div class="field-more">
        <div class="field-more-inner">
          ${f.rows.map(([k, v]) => `<div class="field-row"><span class="k">${k}</span><span class="v">${v}</span></div>`).join("")}
        </div>
      </div>`;
    card.addEventListener("click", () => card.classList.toggle("is-open"));
    grid.appendChild(card);
  });
}

/* ---------- 03 表清单 ---------- */
function renderChips() {
  const bar = $("#tableChips");
  const counts = { all: TABLES.length };
  TABLES.forEach((t) => { counts[t.group] = (counts[t.group] || 0) + 1; });

  const items = [{ key: "all", label: "全部" }, ...Object.entries(GROUPS).map(([k, v]) => ({ key: k, label: v.label }))];
  bar.innerHTML = items.map((it) => `
    <button class="chip ${state.filter === it.key ? "is-on" : ""}" data-filter="${it.key}">
      ${it.label}<span class="count">${counts[it.key] || 0}</span>
    </button>`).join("");

  bar.querySelectorAll(".chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.filter = btn.dataset.filter;
      renderChips();
      renderTable();
    });
  });
}

function renderTable() {
  const body = $("#tableBody");
  body.innerHTML = TABLES.map((t) => {
    const g = GROUPS[t.group];
    const hidden = state.filter !== "all" && t.group !== state.filter ? " class=\"is-filtered\"" : "";
    return `<tr${hidden}>
      <td class="tname">${t.name}</td>
      <td><span class="tag ${g.cls}" title="${g.note}">${g.label}</span></td>
      <td>${t.current}</td>
      <td>${t.target}</td>
      <td>${t.action}</td>
      <td><span class="muted">${t.risk}</span></td>
    </tr>`;
  }).join("");
}

/* ---------- 04 恢复演示 ---------- */
function nowStr() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

function renderDemo() {
  const body = $("#demoBody");
  const view = state.demoView;
  const rows = state.devices.filter((d) => (view === "live" ? !d.deletedAt : d.deletedAt));

  body.innerHTML = rows.map((d) => {
    const alive = !d.deletedAt;
    const canDelete = alive && d.linked === 0;
    const action = alive
      ? `<button class="btn-mini danger" data-del="${d.id}" ${canDelete ? "" : "disabled"} title="${canDelete ? "软删除该设备" : "仍被账号关联，需先解除"}">删除</button>`
      : `<button class="btn-mini" data-restore="${d.id}">恢复</button>`;
    return `<tr>
      <td class="tname">${d.id}</td>
      <td>${d.name}<span class="muted" style="display:block">${d.openid}</span></td>
      <td>${d.org}</td>
      <td>${d.linked}</td>
      <td><span class="state ${alive ? "live" : "dead"}"><span class="bullet"></span>${alive ? "正常" : "已删除"}</span>
          <span class="muted" style="display:block">${alive ? "deleted_at = NULL" : d.deletedAt}</span></td>
      <td>${action}</td>
    </tr>`;
  }).join("");

  const liveCount = state.devices.filter((d) => !d.deletedAt).length;
  const trashCount = state.devices.length - liveCount;
  $("#demoFoot").textContent = `在用 ${liveCount} 台 · 回收站 ${trashCount} 台 · 删除只写 deleted_at，数据库里行仍在`;

  body.querySelectorAll("[data-del]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const dev = state.devices.find((d) => d.id === Number(btn.dataset.del));
      if (!dev) return;
      if (dev.linked > 0) {
        toast(`「${dev.name}」仍被 ${dev.linked} 个账号关联，请先解除关联（对应后端 409）`);
        return;
      }
      dev.deletedAt = nowStr();
      renderDemo();
      toast(`已软删除「${dev.name}」：deleted_at 写入，可随时恢复`);
    });
  });

  body.querySelectorAll("[data-restore]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const dev = state.devices.find((d) => d.id === Number(btn.dataset.restore));
      if (!dev) return;
      dev.deletedAt = null;
      renderDemo();
      toast(`已恢复「${dev.name}」：deleted_at 置 NULL，原 id 与关联保持不变`);
    });
  });

  if (rows.length === 0) {
    body.innerHTML = `<tr><td colspan="6" style="padding:26px;text-align:center;color:#5c6a65">当前视图没有数据，切换上方视图查看</td></tr>`;
  }
}

function bindDemoSwitch() {
  $("#demoSwitch").querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.demoView = btn.dataset.view;
      $("#demoSwitch").querySelectorAll("button").forEach((b) => b.classList.toggle("is-on", b === btn));
      renderDemo();
    });
  });
}

/* ---------- 05 实施步骤 ---------- */
const COPY_ICON = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect width="14" height="14" x="8" y="8" rx="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>`;

function renderSteps() {
  const list = $("#stepList");
  list.innerHTML = "";
  STEPS.forEach((s) => {
    const wrap = document.createElement("div");
    wrap.className = "step";
    wrap.innerHTML = `
      <div class="step-no">${s.no}</div>
      <div class="step-body">
        <h3>${s.title}</h3>
        <p>${s.detail}</p>
        <div class="code"><button class="copy" title="复制代码">${COPY_ICON}</button><span class="code-text"></span></div>
      </div>`;
    wrap.querySelector(".code-text").textContent = s.code;
    const btn = wrap.querySelector(".copy");
    btn.addEventListener("click", () => copyText(s.code, btn));
    list.appendChild(wrap);
  });
}

function copyText(text, btn) {
  const done = () => { btn.innerHTML = "已复制"; setTimeout(() => { btn.innerHTML = COPY_ICON; }, 1500); };
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(done, () => fallbackCopy(text, done));
  } else {
    fallbackCopy(text, done);
  }
}
function fallbackCopy(text, done) {
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.style.position = "fixed";
  ta.style.opacity = "0";
  document.body.appendChild(ta);
  ta.select();
  try { document.execCommand("copy"); done(); } catch { toast("复制失败，请手动选择代码"); }
  ta.remove();
}

/* ---------- 06 验收清单 ---------- */
function renderChecks() {
  const list = $("#checkList");
  list.innerHTML = CHECKS.map((c, i) => `
    <label class="check ${state.checks.has(i) ? "is-done" : ""}" data-check="${i}">
      <span class="box">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M20 6 9 17l-5-5"/></svg>
      </span>
      <span>${c}</span>
    </label>`).join("");

  list.querySelectorAll(".check").forEach((row) => {
    row.addEventListener("click", (e) => {
      e.preventDefault();
      const i = Number(row.dataset.check);
      state.checks.has(i) ? state.checks.delete(i) : state.checks.add(i);
      renderChecks();
    });
  });
  updateProgress();
}

function updateProgress() {
  const total = CHECKS.length;
  const n = state.checks.size;
  $("#checkCount").textContent = `${n} / ${total}`;
  $("#checkBar").style.width = `${(n / total) * 100}%`;
}

/* ---------- 索引高亮 ---------- */
function bindScrollSpy() {
  const links = Array.from($("#railNav").querySelectorAll("a"));
  const secs = links.map((a) => document.querySelector(a.getAttribute("href")).closest("section"));
  const apply = (id) => links.forEach((a) => a.classList.toggle("is-active", a.getAttribute("href") === `#${id}`));
  const io = new IntersectionObserver((entries) => {
    const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
    if (visible) apply(visible.target.id);
  }, { rootMargin: "-20% 0px -65% 0px", threshold: [0, .2, .5, 1] });
  secs.forEach((s) => s && io.observe(s));
  apply("sec-rule");
}

/* ---------- 启动 ---------- */
renderFields();
renderChips();
renderTable();
bindDemoSwitch();
renderDemo();
renderSteps();
renderChecks();
bindScrollSpy();
