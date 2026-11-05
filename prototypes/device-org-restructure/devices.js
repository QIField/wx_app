/* 设备管理视图：统计 / 筛选 / 列表 / 新增 / 编辑 / 删除。 */
window.DevicesView = (function () {
  const state = { devices: [], orgs: [], loading: true, org: '', online: '', kw: '' };
  let el = {};

  const ONLINE_TEXT = { 1: '在线', 0: '离线', '-1': '未知' };
  const ONLINE_CLS = { 1: 'on', 0: 'off', '-1': 'unknown' };

  async function refresh() {
    state.loading = state.devices.length === 0;
    renderTable();
    try {
      const [devices, orgs] = await Promise.all([API.listDevices(), API.listOrgs()]);
      state.devices = devices;
      state.orgs = orgs;
    } catch (ex) {
      toast(ex.message || '加载失败', 'danger');
    }
    state.loading = false;
    renderStats();
    renderOrgOptions();
    renderTable();
  }

  function filtered() {
    const kw = state.kw.trim().toLowerCase();
    return state.devices.filter((d) => {
      if (state.org && d.org_id !== Number(state.org)) return false;
      if (state.online && String(d.online) !== state.online) return false;
      if (kw) {
        const hay = [d.openid, d.name, d.org_name, ...(d.bound_users || []).map((u) => `${u.name} ${u.username}`)].join(' ').toLowerCase();
        if (!hay.includes(kw)) return false;
      }
      return true;
    });
  }

  function renderStats() {
    const ds = state.devices;
    const set = (id, v) => { document.getElementById(id).textContent = v; };
    set('statTotal', ds.length);
    set('statOn', ds.filter((d) => d.online === 1).length);
    set('statOff', ds.filter((d) => d.online === 0).length);
    set('statFree', ds.filter((d) => !(d.bound_users || []).length).length);
  }

  function renderOrgOptions() {
    el.orgFilter.innerHTML =
      '<option value="">全部组织</option>' +
      state.orgs.map((o) => `<option value="${o.id}">${esc(o.name)}</option>`).join('');
    el.orgFilter.value = state.org;
    el.fOrg.innerHTML =
      '<option value="" disabled>请选择组织</option>' +
      state.orgs.map((o) => `<option value="${o.id}">${esc(o.name)}</option>`).join('');
  }

  function renderTable() {
    const rows = filtered();
    el.count.textContent = `共 ${rows.length} 台`;
    if (state.loading) {
      el.tbody.innerHTML = [1, 2, 3, 4]
        .map(() => `<tr>${Array.from({ length: 7 }, () => '<td><div class="skeleton" style="width:96px;height:12px"></div></td>').join('')}</tr>`)
        .join('');
      return;
    }
    if (!rows.length) {
      el.tbody.innerHTML = `<tr><td colspan="7"><div class="empty">${ICONS.smartphone(22)}<span>没有符合条件的设备</span></div></td></tr>`;
      return;
    }
    el.tbody.innerHTML = rows
      .map((d) => {
        const users = d.bound_users || [];
        let bound;
        if (!users.length) {
          bound = '<span class="tag tag-gray" title="尚未被任何账号关联">未关联</span>';
        } else {
          const chips = users.slice(0, 2).map((u) =>
            `<span class="bind-user" title="已关联">${esc(u.name)}</span>`).join('');
          const more = users.length > 2 ? `<span class="bind-user more">+${users.length - 2}</span>` : '';
          bound = `<div class="bind-chips">${chips}${more}</div><div class="cell-sub">共 ${users.length} 个账号关联</div>`;
        }
        const cross = users.some((u) => u.org_id !== d.org_id)
          ? '<span class="tag tag-warn" title="存在与设备归属不同组织的关联账号">跨组织</span>' : '';
        return `<tr>
          <td><div class="cell-main num">${esc(d.openid)}</div>
              <div class="cell-sub num">ID #${d.id} · ${esc(d.created_at)}</div></td>
          <td><div class="cell-main">${esc(d.name)}</div></td>
          <td><span class="tag tag-blue">${esc(d.org_name)}</span></td>
          <td><span class="online ${ONLINE_CLS[d.online]}"></span><span class="ol-text">${ONLINE_TEXT[d.online]}</span></td>
          <td>${bound}${cross}</td>
          <td class="num">${esc(d.created_at)}</td>
          <td><div class="ops">
            <button type="button" class="icon-btn" data-act="edit" data-id="${d.id}" title="编辑设备名称与所属组织">${ICONS.pencil()}</button>
            <button type="button" class="icon-btn" data-act="del" data-id="${d.id}" title="删除设备（被关联时不可删除）">${ICONS.trash()}</button>
          </div></td>
        </tr>`;
      })
      .join('');
  }

  /* ===== 新增 / 编辑弹窗（同一弹窗：editingId 为空即新增） ===== */
  let editingId = null;

  function openModal(d) {
    editingId = d ? d.id : null;
    document.getElementById('devModalTitle').textContent = d ? '编辑设备' : '新增设备';
    el.fOpenid.value = d ? d.openid : '';
    el.fOpenid.disabled = !!d;
    el.fName.value = d ? d.name : '';
    el.fOrg.value = d ? String(d.org_id) : '';
    el.fErr.classList.remove('show');
    openModal_(el.modal);
  }

  const openModal_ = (m) => m.classList.add('show');

  async function save() {
    const p = { openid: el.fOpenid.value.trim(), name: el.fName.value.trim(), org_id: el.fOrg.value ? Number(el.fOrg.value) : null };
    if (!p.openid && !editingId) { showErr('请填写设备 ID'); return; }
    if (!p.name) { showErr('请填写设备名称'); return; }
    if (!p.org_id) { showErr('请选择所属组织'); return; }
    el.fSave.disabled = true;
    try {
      if (editingId) {
        await API.updateDevice(editingId, { name: p.name, org_id: p.org_id });
        toast(`已保存设备「${p.name}」`);
      } else {
        await API.createDevice(p);
        toast(`已新增设备「${p.name}」，可到账号管理中关联`);
      }
      closeModal(el.modal);
      await refresh();
    } catch (ex) {
      showErr(ex.message || '保存失败，请重试');
    }
    el.fSave.disabled = false;
  }

  function showErr(msg) {
    el.fErr.querySelector('span').textContent = msg;
    el.fErr.classList.add('show');
  }

  async function remove(d) {
    if ((d.bound_users || []).length) {
      toast(`「${d.name}」仍被 ${d.bound_users.length} 个账号关联，请先解除关联`, 'danger');
      return;
    }
    if (!window.confirm(`确认删除设备「${d.name}」（${d.openid}）？\n删除后不可恢复。`)) return;
    try {
      await API.deleteDevice(d.id);
      toast(`已删除设备「${d.name}」`);
      await refresh();
    } catch (ex) {
      toast(ex.message || '删除失败', 'danger');
    }
  }

  function init() {
    el = {
      modal: document.getElementById('deviceModal'),
      tbody: document.getElementById('devTbody'),
      count: document.getElementById('devCount'),
      orgFilter: document.getElementById('devOrgFilter'),
      fOpenid: document.getElementById('devFOpenid'),
      fName: document.getElementById('devFName'),
      fOrg: document.getElementById('devFOrg'),
      fErr: document.getElementById('devFErr'),
      fSave: document.getElementById('devFSave'),
    };
    document.getElementById('btnAddDevice').addEventListener('click', () => openModal(null));
    document.getElementById('devModalClose').addEventListener('click', () => closeModal(el.modal));
    document.getElementById('devModalCancel').addEventListener('click', () => closeModal(el.modal));
    el.fSave.addEventListener('click', save);
    el.modal.addEventListener('click', (e) => { if (e.target === el.modal) closeModal(el.modal); });

    el.orgFilter.addEventListener('change', () => { state.org = el.orgFilter.value; renderTable(); });
    document.getElementById('devOnlineFilter').addEventListener('change', (e) => { state.online = e.target.value; renderTable(); });
    document.getElementById('devKw').addEventListener('input', debounce((e) => { state.kw = e.target.value; renderTable(); }));

    el.tbody.addEventListener('click', (e) => {
      const btn = e.target.closest('button[data-act]');
      if (!btn) return;
      const d = state.devices.find((x) => x.id === Number(btn.dataset.id));
      if (!d) return;
      if (btn.dataset.act === 'edit') openModal(d);
      if (btn.dataset.act === 'del') remove(d);
    });

    refresh();
  }

  return { init, refresh };
})();
