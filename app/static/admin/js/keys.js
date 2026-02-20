(() => {
let apiKey = '';
let keyItems = [];
let listLoading = false;
const selectedKeys = new Set();
const byId = (id) => document.getElementById(id);

function setBusy(btn, busy) {
  if (!btn) return;
  btn.disabled = !!busy;
  btn.classList.toggle('is-busy', !!busy);
  btn.setAttribute('aria-busy', busy ? 'true' : 'false');
}

function setButtonsDisabled(ids, disabled) {
  ids.forEach((id) => {
    const btn = byId(id);
    if (btn) btn.disabled = !!disabled;
  });
}

function showModal(id) {
  const modal = byId(id);
  if (!modal) return;
  modal.classList.remove('hidden');
  requestAnimationFrame(() => modal.classList.add('is-open'));
}

function closeModal(id) {
  const modal = byId(id);
  if (!modal) return;
  modal.classList.remove('is-open');
  setTimeout(() => modal.classList.add('hidden'), 180);
}

function bindModalClose() {
  document.querySelectorAll('[data-close]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const target = btn.getAttribute('data-close');
      if (target) closeModal(target);
    });
  });
  document.querySelectorAll('.modal-overlay').forEach((overlay) => {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        closeModal(overlay.id);
      }
    });
  });
}

function formatTime(ts) {
  if (!ts) return '-';
  const ms = ts > 1e12 ? ts : ts * 1000;
  const dt = new Date(ms);
  return dt.toLocaleString('zh-CN', { hour12: false });
}

function updateStats(stats) {
  if (!stats) return;
  if (byId('key-stat-total')) byId('key-stat-total').textContent = stats.total ?? 0;
  if (byId('key-stat-active')) byId('key-stat-active').textContent = stats.active ?? 0;
  if (byId('key-stat-disabled')) byId('key-stat-disabled').textContent = stats.disabled ?? 0;
}

function updateSelectionBar() {
  const bar = byId('keys-selection');
  const countEl = byId('keys-selected-count');
  const statSelected = byId('key-stat-selected');
  const count = selectedKeys.size;

  if (countEl) countEl.textContent = String(count);
  if (statSelected) statSelected.textContent = String(count);
  if (!bar) return;

  if (count > 0) {
    bar.classList.remove('hidden');
  } else {
    bar.classList.add('hidden');
  }
}

function syncSelectAllState() {
  const selectAll = byId('keys-select-all');
  if (!selectAll) return;
  const total = keyItems.length;
  const selected = selectedKeys.size;
  selectAll.checked = total > 0 && selected === total;
  selectAll.indeterminate = selected > 0 && selected < total;
}

function toggleSelect(key, checked) {
  if (checked) {
    selectedKeys.add(key);
  } else {
    selectedKeys.delete(key);
  }
  updateSelectionBar();
  syncSelectAllState();
}

function toggleSelectAll(checked) {
  selectedKeys.clear();
  if (checked) {
    keyItems.forEach((item) => {
      if (item && item.key) selectedKeys.add(item.key);
    });
  }
  renderKeys();
}

async function copyKey(value, btn) {
  if (!value) return;
  try {
    await navigator.clipboard.writeText(value);
    if (btn) {
      btn.textContent = '已复制';
      setTimeout(() => {
        btn.textContent = '复制';
      }, 1200);
    }
    if (typeof showToast === 'function') showToast('Key 已复制', 'success');
  } catch (e) {
    window.prompt('复制 Key', value);
  }
}


function createKeyIconButton({ title, className = '', icon }) {
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = `key-action-icon ${className}`.trim();
  btn.title = title;
  btn.setAttribute('aria-label', title);
  btn.innerHTML = icon;
  return btn;
}

function renderKeys() {
  const tbody = byId('keys-table-body');
  const empty = byId('keys-empty');
  if (!tbody) return;
  tbody.replaceChildren();

  if (!keyItems.length) {
    if (empty) empty.classList.remove('hidden');
    syncSelectAllState();
    updateSelectionBar();
    return;
  }
  if (empty) empty.classList.add('hidden');

  const fragment = document.createDocumentFragment();
  keyItems.forEach((item) => {
    const tr = document.createElement('tr');
    if (selectedKeys.has(item.key)) {
      tr.classList.add('row-selected');
    }

    const tdCheck = document.createElement('td');
    tdCheck.className = 'text-center';
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.className = 'checkbox';
    checkbox.checked = selectedKeys.has(item.key);
    checkbox.addEventListener('change', () => toggleSelect(item.key, checkbox.checked));
    tdCheck.appendChild(checkbox);

    const tdName = document.createElement('td');
    tdName.className = 'text-left';
    tdName.textContent = item.name || '未命名';

    const tdKey = document.createElement('td');
    tdKey.className = 'text-left';
    const keyWrap = document.createElement('div');
    keyWrap.className = 'key-cell';
    const keyText = document.createElement('span');
    keyText.className = 'key-mask';
    keyText.title = item.key || '';
    keyText.textContent = item.masked_key || item.key;
    const copyBtn = document.createElement('button');
    copyBtn.className = 'key-copy';
    copyBtn.textContent = '复制';
    copyBtn.addEventListener('click', () => copyKey(item.key, copyBtn));
    keyWrap.appendChild(keyText);
    keyWrap.appendChild(copyBtn);
    tdKey.appendChild(keyWrap);

    const tdTime = document.createElement('td');
    tdTime.className = 'text-left text-xs text-gray-500';
    tdTime.textContent = formatTime(item.created_at);

    const tdStatus = document.createElement('td');
    tdStatus.className = 'text-center';
    const badge = document.createElement('span');
    badge.className = item.is_active ? 'badge badge-green' : 'badge badge-red';
    badge.textContent = item.is_active ? '启用' : '禁用';
    tdStatus.appendChild(badge);

    const tdActions = document.createElement('td');
    tdActions.className = 'text-center';
    const actionWrap = document.createElement('div');
    actionWrap.className = 'key-actions';

    const editBtn = createKeyIconButton({
      title: '编辑 Key',
      icon: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>'
    });
    editBtn.addEventListener('click', () => openEditModal(item));

    const toggleBtn = createKeyIconButton({
      title: item.is_active ? '禁用 Key' : '启用 Key',
      className: item.is_active ? 'is-warning' : 'is-success',
      icon: item.is_active
        ? '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M8 12h8"/></svg>'
        : '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="m9 12 2 2 4-4"/></svg>'
    });
    toggleBtn.addEventListener('click', (event) => toggleKeyStatus(item, event.currentTarget));

    const delBtn = createKeyIconButton({
      title: '删除 Key',
      className: 'is-danger',
      icon: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/></svg>'
    });
    delBtn.addEventListener('click', (event) => deleteKeys([item.key], event.currentTarget));

    actionWrap.appendChild(editBtn);
    actionWrap.appendChild(toggleBtn);
    actionWrap.appendChild(delBtn);
    tdActions.appendChild(actionWrap);

    tr.appendChild(tdCheck);
    tr.appendChild(tdName);
    tr.appendChild(tdKey);
    tr.appendChild(tdTime);
    tr.appendChild(tdStatus);
    tr.appendChild(tdActions);
    fragment.appendChild(tr);
  });

  tbody.appendChild(fragment);
  syncSelectAllState();
  updateSelectionBar();
}

async function loadKeys({ silent = false } = {}) {
  if (listLoading) return;
  listLoading = true;

  const refreshBtn = byId('key-refresh-btn');
  if (!silent) setBusy(refreshBtn, true);
  setButtonsDisabled(['key-create-btn', 'key-batch-btn', 'keys-delete-selected'], true);

  try {
    const res = await fetch('/v1/admin/keys', {
      headers: buildAuthHeaders(apiKey)
    });
    if (res.status === 401) {
      logout();
      return;
    }
    const data = await res.json();
    keyItems = Array.isArray(data.keys) ? data.keys : [];
    const exists = new Set(keyItems.map((item) => item.key));
    Array.from(selectedKeys).forEach((key) => {
      if (!exists.has(key)) selectedKeys.delete(key);
    });
    updateStats(data.stats);
    renderKeys();
  } catch (e) {
    if (typeof showToast === 'function') showToast('加载 Key 失败', 'error');
  } finally {
    listLoading = false;
    if (!silent) setBusy(refreshBtn, false);
    setButtonsDisabled(['key-create-btn', 'key-batch-btn', 'keys-delete-selected'], false);
  }
}

async function createKey() {
  const nameInput = byId('key-create-name');
  const confirmBtn = byId('key-create-confirm');
  const name = nameInput ? nameInput.value.trim() : '';
  if (confirmBtn?.disabled) return;

  setBusy(confirmBtn, true);
  try {
    const res = await fetch('/v1/admin/keys', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...buildAuthHeaders(apiKey)
      },
      body: JSON.stringify({ name, count: 1 })
    });
    if (res.status === 401) {
      logout();
      return;
    }
    if (!res.ok) throw new Error('创建失败');
    closeModal('key-create-modal');
    if (nameInput) nameInput.value = '';
    await loadKeys({ silent: true });
    if (typeof showToast === 'function') showToast('Key 创建成功', 'success');
  } catch (e) {
    if (typeof showToast === 'function') showToast('创建失败', 'error');
  } finally {
    setBusy(confirmBtn, false);
  }
}

async function batchCreateKeys() {
  const nameInput = byId('key-batch-name');
  const countInput = byId('key-batch-count');
  const confirmBtn = byId('key-batch-confirm');
  const name = nameInput ? nameInput.value.trim() : '';
  const count = countInput ? parseInt(countInput.value, 10) : 1;
  if (confirmBtn?.disabled) return;

  setBusy(confirmBtn, true);
  try {
    const res = await fetch('/v1/admin/keys', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...buildAuthHeaders(apiKey)
      },
      body: JSON.stringify({ name, count: Number.isFinite(count) ? count : 1 })
    });
    if (res.status === 401) {
      logout();
      return;
    }
    if (!res.ok) throw new Error('创建失败');
    closeModal('key-batch-modal');
    if (countInput) countInput.value = '5';
    if (typeof showToast === 'function') showToast('批量创建成功', 'success');
    await loadKeys({ silent: true });
  } catch (e) {
    if (typeof showToast === 'function') showToast('批量创建失败', 'error');
  } finally {
    setBusy(confirmBtn, false);
  }
}

function openEditModal(item) {
  if (!item) return;
  if (byId('key-edit-value')) byId('key-edit-value').value = item.key || '';
  if (byId('key-edit-display')) byId('key-edit-display').value = item.key || '';
  if (byId('key-edit-name')) byId('key-edit-name').value = item.name || '';
  if (byId('key-edit-status')) byId('key-edit-status').value = item.is_active ? 'true' : 'false';
  showModal('key-edit-modal');
}

async function saveEditKey() {
  const key = byId('key-edit-value')?.value || '';
  const name = byId('key-edit-name')?.value || '';
  const status = byId('key-edit-status')?.value === 'true';
  const confirmBtn = byId('key-edit-confirm');
  if (!key || confirmBtn?.disabled) return;

  setBusy(confirmBtn, true);
  try {
    const res = await fetch('/v1/admin/keys', {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...buildAuthHeaders(apiKey)
      },
      body: JSON.stringify({ key, name, is_active: status })
    });
    if (res.status === 401) {
      logout();
      return;
    }
    if (!res.ok) throw new Error('保存失败');
    closeModal('key-edit-modal');
    await loadKeys({ silent: true });
    if (typeof showToast === 'function') showToast('更新成功', 'success');
  } catch (e) {
    if (typeof showToast === 'function') showToast('更新失败', 'error');
  } finally {
    setBusy(confirmBtn, false);
  }
}

async function toggleKeyStatus(item, triggerBtn) {
  if (!item || !item.key) return;
  setBusy(triggerBtn, true);
  try {
    const res = await fetch('/v1/admin/keys', {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...buildAuthHeaders(apiKey)
      },
      body: JSON.stringify({ key: item.key, is_active: !item.is_active })
    });
    if (res.status === 401) {
      logout();
      return;
    }
    if (!res.ok) throw new Error('更新失败');
    await loadKeys({ silent: true });
  } catch (e) {
    if (typeof showToast === 'function') showToast('更新失败', 'error');
  } finally {
    setBusy(triggerBtn, false);
  }
}

async function deleteKeys(keys, triggerBtn = null) {
  if (!keys || keys.length === 0) return;
  const ok = window.confirm(`确定要删除选中的 ${keys.length} 个 Key 吗？`);
  if (!ok) return;

  setBusy(triggerBtn, true);
  const batchDeleteBtn = byId('keys-delete-selected');
  if (triggerBtn !== batchDeleteBtn) setBusy(batchDeleteBtn, true);

  try {
    const res = await fetch('/v1/admin/keys', {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        ...buildAuthHeaders(apiKey)
      },
      body: JSON.stringify({ keys })
    });
    if (res.status === 401) {
      logout();
      return;
    }
    if (!res.ok) throw new Error('删除失败');

    keys.forEach((key) => selectedKeys.delete(key));
    await loadKeys({ silent: true });
    if (typeof showToast === 'function') showToast('删除成功', 'success');
  } catch (e) {
    if (typeof showToast === 'function') showToast('删除失败', 'error');
  } finally {
    setBusy(triggerBtn, false);
    if (triggerBtn !== batchDeleteBtn) setBusy(batchDeleteBtn, false);
  }
}

function bindEvents() {
  const refreshBtn = byId('key-refresh-btn');
  const createBtn = byId('key-create-btn');
  const batchBtn = byId('key-batch-btn');
  const createConfirm = byId('key-create-confirm');
  const batchConfirm = byId('key-batch-confirm');
  const editConfirm = byId('key-edit-confirm');
  const selectAll = byId('keys-select-all');
  const deleteSelectedBtn = byId('keys-delete-selected');

  if (refreshBtn) refreshBtn.addEventListener('click', () => loadKeys());
  if (createBtn) createBtn.addEventListener('click', () => showModal('key-create-modal'));
  if (batchBtn) batchBtn.addEventListener('click', () => showModal('key-batch-modal'));
  if (createConfirm) createConfirm.addEventListener('click', createKey);
  if (batchConfirm) batchConfirm.addEventListener('click', batchCreateKeys);
  if (editConfirm) editConfirm.addEventListener('click', saveEditKey);

  if (selectAll) {
    selectAll.addEventListener('change', () => toggleSelectAll(selectAll.checked));
  }
  if (deleteSelectedBtn) {
    deleteSelectedBtn.addEventListener('click', (event) => deleteKeys(Array.from(selectedKeys), event.currentTarget));
  }
}

async function init() {
  apiKey = await ensureAdminKey();
  if (apiKey === null) return false;
  bindModalClose();
  bindEvents();
  await loadKeys();
  return true;
}

let keysInitStarted = false;
async function initKeysPage() {
  if (keysInitStarted) return;
  keysInitStarted = true;
  try {
    const ok = await init();
    if (ok === false) {
      keysInitStarted = false;
    }
  } catch (e) {
    keysInitStarted = false;
    throw e;
  }
}

if (window.__registerAdminPage) {
  window.__registerAdminPage('keys', initKeysPage);
} else if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initKeysPage);
} else {
  initKeysPage();
}
})();
