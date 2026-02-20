(() => {
let apiKey = '';
let sessionItems = [];
let sessionsLoading = false;
const byId = (id) => document.getElementById(id);

function setBusy(btn, busy) {
  if (!btn) return;
  btn.disabled = !!busy;
  btn.classList.toggle('is-busy', !!busy);
  btn.setAttribute('aria-busy', busy ? 'true' : 'false');
}

function setToolbarDisabled(disabled) {
  const refreshBtn = byId('sessions-refresh-btn');
  const clearBtn = byId('sessions-clear-btn');
  if (refreshBtn && !refreshBtn.classList.contains('is-busy')) refreshBtn.disabled = !!disabled;
  if (clearBtn && !clearBtn.classList.contains('is-busy')) clearBtn.disabled = !!disabled;
}

function formatTime(ts) {
  if (!ts) return '-';
  const ms = ts > 1e12 ? ts : ts * 1000;
  const dt = new Date(ms);
  return dt.toLocaleString('zh-CN', { hour12: false });
}

function formatTtl(seconds) {
  const sec = Number(seconds || 0);
  if (sec <= 0) return '已过期';
  const hours = Math.floor(sec / 3600);
  const mins = Math.floor((sec % 3600) / 60);
  if (hours > 0) return `${hours}h ${mins}m`;
  return `${mins}m`;
}

function updateStats(stats) {
  if (!stats) return;
  if (byId('session-stat-total')) byId('session-stat-total').textContent = stats.total_conversations ?? 0;
  if (byId('session-stat-tokens')) byId('session-stat-tokens').textContent = stats.tokens_with_conversations ?? 0;
  const avg = stats.avg_messages_per_conversation ?? 0;
  if (byId('session-stat-avg')) byId('session-stat-avg').textContent = avg.toFixed ? avg.toFixed(1) : avg;
  const ttlHours = stats.ttl_seconds ? Math.round(stats.ttl_seconds / 3600) : 0;
  if (byId('session-stat-ttl')) byId('session-stat-ttl').textContent = ttlHours;
}

function createIdCell(value) {
  const wrap = document.createElement('div');
  wrap.className = 'session-id-cell';

  const idSpan = document.createElement('span');
  idSpan.className = 'session-id';
  idSpan.textContent = value || '-';
  idSpan.title = value || '';
  wrap.appendChild(idSpan);

  if (value) {
    const copyBtn = document.createElement('button');
    copyBtn.className = 'session-copy';
    copyBtn.textContent = '复制';
    copyBtn.addEventListener('click', async (event) => {
      const btn = event.currentTarget;
      setBusy(btn, true);
      try {
        await navigator.clipboard.writeText(value);
        btn.textContent = '已复制';
        setTimeout(() => {
          btn.textContent = '复制';
          setBusy(btn, false);
        }, 900);
      } catch (e) {
        setBusy(btn, false);
        window.prompt('复制会话 ID', value);
      }
    });
    wrap.appendChild(copyBtn);
  }

  return wrap;
}

function createHashBadge(status) {
  const badge = document.createElement('span');
  badge.className = 'hash-badge';
  const normalized = status || 'none';
  badge.classList.add(normalized);

  if (normalized === 'matched') {
    badge.textContent = '已匹配';
  } else if (normalized === 'stale') {
    badge.textContent = '已失效';
  } else {
    badge.textContent = '无记录';
  }

  return badge;
}

function createTtlBadge(ttlRemain) {
  const badge = document.createElement('span');
  badge.className = 'ttl-badge';
  const ttl = Number(ttlRemain || 0);

  if (ttl <= 0) {
    badge.classList.add('expired');
  } else if (ttl < 900) {
    badge.classList.add('low');
  } else if (ttl < 3600) {
    badge.classList.add('warn');
  }

  badge.textContent = formatTtl(ttl);
  return badge;
}

function createSessionActionButton({ title, className = '', icon }) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = `session-action-icon ${className}`.trim();
  button.title = title;
  button.setAttribute('aria-label', title);
  button.innerHTML = icon;
  return button;
}

function renderSessions() {
  const tbody = byId('sessions-table-body');
  const empty = byId('sessions-empty');
  if (!tbody) return;

  tbody.replaceChildren();
  if (!sessionItems.length) {
    if (empty) empty.classList.remove('hidden');
    return;
  }
  if (empty) empty.classList.add('hidden');

  const fragment = document.createDocumentFragment();
  sessionItems.forEach((item) => {
    const tr = document.createElement('tr');

    const tdId = document.createElement('td');
    tdId.className = 'text-left';
    tdId.appendChild(createIdCell(item.conversation_id || ''));

    const tdGrok = document.createElement('td');
    tdGrok.className = 'text-left';
    tdGrok.appendChild(createIdCell(item.grok_conversation_id || ''));

    const tdHash = document.createElement('td');
    tdHash.className = 'text-center';
    tdHash.appendChild(createHashBadge(item.hash_status));

    const tdToken = document.createElement('td');
    tdToken.className = 'text-left';
    const tokenSpan = document.createElement('span');
    tokenSpan.className = 'session-token';
    tokenSpan.textContent = item.token || '-';
    tokenSpan.title = item.token || '';
    tdToken.appendChild(tokenSpan);

    const tdMsg = document.createElement('td');
    tdMsg.className = 'text-center';
    tdMsg.textContent = String(item.message_count ?? 0);

    const tdActive = document.createElement('td');
    tdActive.className = 'text-left text-xs text-gray-500';
    tdActive.textContent = formatTime(item.last_active);

    const tdTtl = document.createElement('td');
    tdTtl.className = 'text-center';
    tdTtl.appendChild(createTtlBadge(item.ttl_remaining));

    const tdActions = document.createElement('td');
    tdActions.className = 'text-center';
    const delBtn = createSessionActionButton({
      title: '删除会话',
      className: 'is-danger',
      icon: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/></svg>'
    });
    delBtn.addEventListener('click', (event) => deleteSession(item.conversation_id, event.currentTarget));
    tdActions.appendChild(delBtn);

    tr.appendChild(tdId);
    tr.appendChild(tdGrok);
    tr.appendChild(tdHash);
    tr.appendChild(tdToken);
    tr.appendChild(tdMsg);
    tr.appendChild(tdActive);
    tr.appendChild(tdTtl);
    tr.appendChild(tdActions);
    fragment.appendChild(tr);
  });

  tbody.appendChild(fragment);
}

async function loadSessions({ silent = false } = {}) {
  if (sessionsLoading) return;
  sessionsLoading = true;

  const refreshBtn = byId('sessions-refresh-btn');
  if (!silent) setBusy(refreshBtn, true);
  setToolbarDisabled(true);

  try {
    const res = await fetch('/v1/admin/sessions', {
      headers: buildAuthHeaders(apiKey)
    });
    if (res.status === 401) {
      logout();
      return;
    }
    const data = await res.json();
    sessionItems = Array.isArray(data.conversations) ? data.conversations : [];
    updateStats(data.stats);
    renderSessions();
  } catch (e) {
    if (typeof showToast === 'function') showToast('加载会话失败', 'error');
  } finally {
    sessionsLoading = false;
    if (!silent) setBusy(refreshBtn, false);
    setToolbarDisabled(false);
  }
}

async function deleteSession(id, triggerBtn = null) {
  if (!id) return;
  const ok = window.confirm('确定要删除该会话吗？');
  if (!ok) return;

  setBusy(triggerBtn, true);
  setToolbarDisabled(true);

  try {
    const res = await fetch('/v1/admin/sessions', {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        ...buildAuthHeaders(apiKey)
      },
      body: JSON.stringify({ conversation_id: id })
    });
    if (res.status === 401) {
      logout();
      return;
    }
    if (!res.ok) throw new Error('删除失败');
    await loadSessions({ silent: true });
    if (typeof showToast === 'function') showToast('删除成功', 'success');
  } catch (e) {
    if (typeof showToast === 'function') showToast('删除失败', 'error');
  } finally {
    setBusy(triggerBtn, false);
    setToolbarDisabled(false);
  }
}

async function clearSessions() {
  const clearBtn = byId('sessions-clear-btn');
  if (clearBtn?.disabled) return;

  const ok = window.confirm('确定要清空所有会话吗？');
  if (!ok) return;

  setBusy(clearBtn, true);
  setToolbarDisabled(true);

  try {
    const res = await fetch('/v1/admin/sessions/clear', {
      method: 'POST',
      headers: buildAuthHeaders(apiKey)
    });
    if (res.status === 401) {
      logout();
      return;
    }
    if (!res.ok) throw new Error('清空失败');
    await loadSessions({ silent: true });
    if (typeof showToast === 'function') showToast('已清空', 'success');
  } catch (e) {
    if (typeof showToast === 'function') showToast('清空失败', 'error');
  } finally {
    setBusy(clearBtn, false);
    setToolbarDisabled(false);
  }
}

function bindEvents() {
  const refreshBtn = byId('sessions-refresh-btn');
  const clearBtn = byId('sessions-clear-btn');
  if (refreshBtn) refreshBtn.addEventListener('click', () => loadSessions());
  if (clearBtn) clearBtn.addEventListener('click', clearSessions);
}

async function init() {
  apiKey = await ensureAdminKey();
  if (apiKey === null) return false;
  bindEvents();
  await loadSessions();
  return true;
}

let sessionsInitStarted = false;
async function initSessionsPage() {
  if (sessionsInitStarted) return;
  sessionsInitStarted = true;
  try {
    const ok = await init();
    if (ok === false) {
      sessionsInitStarted = false;
    }
  } catch (e) {
    sessionsInitStarted = false;
    throw e;
  }
}

if (window.__registerAdminPage) {
  window.__registerAdminPage('sessions', initSessionsPage);
} else if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initSessionsPage);
} else {
  initSessionsPage();
}
})();
