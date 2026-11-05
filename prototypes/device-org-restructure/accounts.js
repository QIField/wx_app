/* 账号管理视图：列表 / 新增 / 编辑，绑定从手填 openid 改为跨组织设备选择器。 */
window.AccountsView = (function () {
  const state = { users: [], orgs: [], devices: [], loading: true, kw: '' };
  let el = {};

  const ROLE_CLS = { developer: 'role-developer', admin: 'role-admin', agent: 'role-agent' };

  async function refresh() {
    state.loading = state.users.length === 0;
    renderTable();
    try {
      const [users, orgs, devices] = await Promise.all([API.listAccounts(), API.listOrgs(), API.listDevices()]);
      state.users = users;
      state.orgs = orgs;
      state.devices = devices;
    } catch (ex) {
      toast(ex.message || '加载失败', 'danger');
    }
    state.loading = false;
    renderTable();
  }

  function filtered() {
    const kw = state.kw.trim().toLowerCase();
    if (!kw) return state.users;
    return state.users.filter((u) =>
      [u.username, u.name, u.org_name].join(' ').toLowerCase().includes(kw));
  }

  function renderTable() {
    const rows = filtered();
    el.count.textContent = `共 ${rows.length} 个账号`;
    if (state.loading) {
      el.tbody.innerHTML = [1, 2, 3]
        .map(() => `<tr>${Array.from({ length: 8 }, () => '<td><div class="skeleton" style="width:96px;height:12px"></div></td>').join('')}</tr>`)
        .join('');
      return;
    }
    if (!rows.length) {
      el.tbody.innerHTML = `<tr><td colspan="8"><div class="empty">${ICONS.link(22)}<span>没有符合条件的账号</span></div></td></tr>`;
      return;
    }
    el.tbody.innerHTML = rows
      .map((u) => {
        const chips = u.devices.slice(0, 2).map((d) =>
          `<span class="bind-chip" title="${esc(d.org_name)} · ${esc(d.name)}">${esc(d.name)}</span>`).join('');
        const more = u.devices.length > 2 ? `<span class="bind-chip more">+${u.devices.length - 2}</span>` : '';
        const bind = u.devices.length
          ? `<div class="bind-chips">${chips}${more}<span class="cell-sub" style="margin-left:2px;">共 ${u.devices.length} 台</span></div>`
          : '<span class="tag tag-gray" title="未绑定设备，登录工作台看不到任何会话">未绑定</span>';
        return `<tr>
          <td><div class="cell-main num">${esc(u.username)}</div>
              <div class="cell-sub num">创建于 ${esc(u.created_at)}</div></td>
          <td><div style="display:flex;align-items:center;gap:8px;">
                <span class="avatar sm">${esc(u.name.slice(0, 1))}</span>
                <span class="cell-main">${esc(u.name)}</span></div></td>
          <td><span class="tag ${ROLE_CLS[u.role]}">${ROLE_TEXT[u.role]}</span></td>
          <td>${u.org_name
            ? `<span class="tag tag-blue">${esc(u.org_name)}</span>`
            : '<span class="tag tag-gray" title="开发者账号跨组织">跨组织</span>'}</td>
          <td>${bind}</td>
          <td><div style="display:flex;align-items:center;gap:8px;">
                <button type="button" class="switch ${u.status === 1 ? 'on' : ''}" data-act="toggle" data-id="${u.id}"
                        title="${u.id === DB_REF.me.id ? '不能停用当前登录账号' : (u.status === 1 ? '点击停用该账号' : '点击启用该账号')}"></button>
                <span class="tag ${u.status === 1 ? 'tag-ok' : 'tag-gray'}">${u.status === 1 ? '启用' : '停用'}</span></div></td>
          <td class="num">${esc(u.last_login_at || '从未登录')}</td>
          <td><div class="ops">
                <button type="button" class="icon-btn" data-act="edit" data-id="${u.id}" title="编辑姓名、组织与设备关联">${ICONS.pencil()}</button>
                <button type="button" class="icon-btn" data-act="reset" data-id="${u.id}" title="重置为初始密码 123456">${ICONS.reset()}</button>
              </div></td>
        </tr>`;
      })
      .join('');
  }

  /* ===== 跨组织设备选择器（复用于新增/编辑弹窗） =====
     opts: { root, onChange(ids) } —— 多账号可关联同一台设备，不做互斥置灰 */
  function createPicker(opts) {
    const root = opts.root;
    root.classList.add('picker');
    root.innerHTML = `
      <button type="button" class="picker-box"><span class="picker-box-text"></span>${ICONS.search(14)}</button>
      <div class="picker-panel" hidden>
        <div class="picker-search">${ICONS.search(14)}<input type="text" placeholder="搜索设备名称 / ID"></div>
        <div class="picker-orgs"></div>
        <div class="picker-list"></div>
        <div class="picker-foot">设备可跨组织选择、多账号共用 · 解除关联不影响他人</div>
      </div>
      <div class="picker-chips"></div>`;
    const box = root.querySelector('.picker-box');
    const boxText = root.querySelector('.picker-box-text');
    const panel = root.querySelector('.picker-panel');
    const kw = root.querySelector('.picker-search input');
    const orgBar = root.querySelector('.picker-orgs');
    const list = root.querySelector('.picker-list');
    const chips = root.querySelector('.picker-chips');
    const st = { kw: '', org: '', selected: [] };

    function renderOrgs() {
      orgBar.innerHTML =
        `<button type="button" class="pchip ${st.org === '' ? 'on' : ''}" data-org="">全部组织</button>` +
        state.orgs.map((o) =>
          `<button type="button" class="pchip ${st.org === String(o.id) ? 'on' : ''}" data-org="${o.id}">${esc(o.name)}</button>`).join('');
    }

    function renderList() {
      const k = st.kw.trim().toLowerCase();
      const items = state.devices.filter((d) => {
        if (st.org && d.org_id !== Number(st.org)) return false;
        if (k && !`${d.name} ${d.openid} ${d.org_name}`.toLowerCase().includes(k)) return false;
        return true;
      });
      list.innerHTML = items.length
        ? items.map((d) => {
            const sel = st.selected.includes(d.id);
            const usedN = (d.bound_users || []).length;
            return `<button type="button" class="pitem ${sel ? 'sel' : ''}" data-id="${d.id}">
                      <span class="pi-check">${ICONS.check(12)}</span>
                      <span class="pi-main"><span class="pi-name">${esc(d.name)}</span>
                        <span class="pi-sub num">${esc(d.openid)}${usedN ? ` · ${usedN} 个账号共用` : ''}</span></span>
                      <span class="pi-side"><span class="tag tag-blue">${esc(d.org_name)}</span>
                        ${usedN ? `<span class="pi-used">已有 ${usedN} 个账号关联</span>` : ''}</span>
                    </button>`;
          }).join('')
        : '<div class="empty" style="padding:18px 0;"><span>没有符合条件的设备</span></div>';
    }

    function renderChips() {
      boxText.textContent = st.selected.length
        ? `已选 ${st.selected.length} 台设备 · 点击调整`
        : '从设备库选择（可跨组织）';
      chips.innerHTML = st.selected.map((id) => {
        const d = state.devices.find((x) => x.id === id);
        if (!d) return '';
        return `<span class="sel-chip">${esc(d.name)}<button type="button" class="chip-x" data-id="${id}" title="移除">${ICONS.x(11)}</button></span>`;
      }).join('');
    }

    function render() { renderOrgs(); renderList(); renderChips(); }

    box.addEventListener('click', () => {
      panel.hidden = !panel.hidden;
      if (!panel.hidden) { render(); kw.focus(); }
    });
    kw.addEventListener('input', debounce(() => { st.kw = kw.value; renderList(); }));
    orgBar.addEventListener('click', (e) => {
      const b = e.target.closest('.pchip');
      if (!b) return;
      st.org = b.dataset.org;
      renderOrgs(); renderList();
    });
    list.addEventListener('click', (e) => {
      const b = e.target.closest('.pitem');
      if (!b) return;
      const id = Number(b.dataset.id);
      const i = st.selected.indexOf(id);
      if (i >= 0) st.selected.splice(i, 1);
      else st.selected.push(id);
      renderList(); renderChips();
      opts.onChange([...st.selected]);
    });
    chips.addEventListener('click', (e) => {
      const b = e.target.closest('.chip-x');
      if (!b) return;
      st.selected = st.selected.filter((x) => x !== Number(b.dataset.id));
      renderList(); renderChips();
      opts.onChange([...st.selected]);
    });
    document.addEventListener('click', (e) => {
      if (!root.contains(e.target)) panel.hidden = true;
    });

    return {
      set(ids) { st.selected = [...ids]; renderChips(); if (!panel.hidden) renderList(); },
      close() { panel.hidden = true; },
      get() { return [...st.selected]; },
    };
  }

  /* ===== 新增 / 编辑弹窗 ===== */
  let addPicker, editPicker, editingUser = null;

  function orgOptions(sel, withNull) {
    return (withNull ? '<option value="">不绑组织（跨组织）</option>' : '<option value="" disabled>请选择组织</option>') +
      state.orgs.map((o) => `<option value="${o.id}" ${String(sel) === String(o.id) ? 'selected' : ''}>${esc(o.name)}</option>`).join('');
  }

  function openAdd() {
    document.getElementById('aaUsername').value = '';
    document.getElementById('aaName').value = '';
    document.getElementById('aaRole').value = 'agent';
    document.getElementById('aaOrg').innerHTML = orgOptions('', false);
    addPicker.set([]);
    showErr(el.aaErr, '');
    openModal(el.aaModal);
  }

  function openEdit(u) {
    editingUser = u;
    document.getElementById('aeUsername').value = u.username;
    document.getElementById('aeName').value = u.name;
    document.getElementById('aeRoleTag').textContent = ROLE_TEXT[u.role];
    document.getElementById('aeOrg').innerHTML = orgOptions(u.org_id, u.role === 'developer');
    editPicker.set(u.devices.map((d) => d.id));
    showErr(el.aeErr, '');
    openModal(el.aeModal);
  }

  async function saveAdd() {
    const username = document.getElementById('aaUsername').value.trim();
    const name = document.getElementById('aaName').value.trim();
    const role = document.getElementById('aaRole').value;
    const org_id = document.getElementById('aaOrg').value ? Number(document.getElementById('aaOrg').value) : null;
    if (!username || !name) { showErr(el.aaErr, '请填写登录账号与姓名'); return; }
    if (role !== 'developer' && !org_id) { showErr(el.aaErr, '请选择所属组织'); return; }
    el.aaSave.disabled = true;
    try {
      await API.createAccount({ username, name, role, org_id, device_ids: addPicker.get() });
      toast(`已新增账号 ${username}，初始密码 123456`);
      closeModal(el.aaModal);
      await refresh();
    } catch (ex) { showErr(el.aaErr, ex.message || '保存失败，请重试'); }
    el.aaSave.disabled = false;
  }

  async function saveEdit() {
    const name = document.getElementById('aeName').value.trim();
    const org_id = document.getElementById('aeOrg').value ? Number(document.getElementById('aeOrg').value) : null;
    if (!name) { showErr(el.aeErr, '请填写姓名'); return; }
    if (editingUser.role !== 'developer' && !org_id) { showErr(el.aeErr, '请选择所属组织'); return; }
    el.aeSave.disabled = true;
    try {
      await API.updateAccount(editingUser.id, { name, org_id, device_ids: editPicker.get() });
      toast(`已保存 ${editingUser.username} 的账号修改`);
      closeModal(el.aeModal);
      await refresh();
    } catch (ex) { showErr(el.aeErr, ex.message || '保存失败，请重试'); }
    el.aeSave.disabled = false;
  }

  function showErr(box, msg) {
    box.querySelector('span').textContent = msg;
    box.classList.toggle('show', !!msg);
  }

  async function onToggle(u) {
    if (u.id === DB_REF.me.id) { toast('不能停用当前登录账号', 'danger'); return; }
    const next = u.status === 1 ? 0 : 1;
    try {
      await API.toggleAccount(u.id, next);
      u.status = next;
      toast(`${next === 1 ? '已启用' : '已停用'} ${u.username}`);
      renderTable();
    } catch (ex) { toast(ex.message || '操作失败', 'danger'); }
  }

  async function onReset(u) {
    if (!window.confirm(`确认将 ${u.username}（${u.name}）的密码重置为初始密码 123456？`)) return;
    toast(`已重置 ${u.username} 的密码为 123456`);
  }

  function init() {
    el = {
      tbody: document.getElementById('accTbody'),
      count: document.getElementById('accCount'),
      aaModal: document.getElementById('accAddModal'),
      aeModal: document.getElementById('accEditModal'),
      aaErr: document.getElementById('aaErr'),
      aeErr: document.getElementById('aeErr'),
      aaSave: document.getElementById('aaSave'),
      aeSave: document.getElementById('aeSave'),
    };
    document.getElementById('accKw').addEventListener('input', debounce((e) => { state.kw = e.target.value; renderTable(); }));

    addPicker = createPicker({ root: document.getElementById('aaPicker'), onChange: () => {} });
    editPicker = createPicker({ root: document.getElementById('aePicker'), onChange: () => {} });

    document.getElementById('btnAddAcc').addEventListener('click', openAdd);
    document.getElementById('aaModalClose').addEventListener('click', () => { addPicker.close(); closeModal(el.aaModal); });
    document.getElementById('aaCancel').addEventListener('click', () => { addPicker.close(); closeModal(el.aaModal); });
    document.getElementById('aeModalClose').addEventListener('click', () => { editPicker.close(); closeModal(el.aeModal); });
    document.getElementById('aeCancel').addEventListener('click', () => { editPicker.close(); closeModal(el.aeModal); });
    document.getElementById('aaSave').addEventListener('click', saveAdd);
    document.getElementById('aeSave').addEventListener('click', saveEdit);
    el.aaModal.addEventListener('click', (e) => { if (e.target === el.aaModal) { addPicker.close(); closeModal(el.aaModal); } });
    el.aeModal.addEventListener('click', (e) => { if (e.target === el.aeModal) { editPicker.close(); closeModal(el.aeModal); } });

    el.tbody.addEventListener('click', (e) => {
      const btn = e.target.closest('button[data-act]');
      if (!btn) return;
      const u = state.users.find((x) => x.id === Number(btn.dataset.id));
      if (!u) return;
      if (btn.dataset.act === 'edit') openEdit(u);
      if (btn.dataset.act === 'toggle') onToggle(u);
      if (btn.dataset.act === 'reset') onReset(u);
    });

    refresh();
  }

  return { init, refresh };
})();
