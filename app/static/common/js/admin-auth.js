let cachedAdminAuth = null;
let cachedPublicAuth = null;

function buildAuthHeaders(apiKey) {
  return apiKey ? { Authorization: apiKey } : {};
}

async function verifyKey(url, key) {
  const headers = buildAuthHeaders(key ? `Bearer ${key}` : '');
  const res = await fetch(url, {
    method: 'GET',
    headers,
    credentials: 'same-origin',
    cache: 'no-store'
  });
  return res.ok;
}

function resetCachedAuth() {
  cachedAdminAuth = null;
  cachedPublicAuth = null;
}

// Compatibility stubs: keys are no longer persisted in localStorage.
async function getStoredAppKey() { return ''; }
async function getStoredPublicKey() { return ''; }
async function storeAppKey() { return; }
async function storePublicKey() { return; }
function clearStoredAppKey() { cachedAdminAuth = null; }
function clearStoredPublicKey() { cachedPublicAuth = null; }

function isAdminContext() {
  return Boolean(window.__adminSpa__) || window.location.pathname.startsWith('/admin');
}

async function ensureAdminKey() {
  if (cachedAdminAuth !== null) return cachedAdminAuth;

  try {
    const ok = await verifyKey('/v1/admin/verify', '');
    if (ok) {
      cachedAdminAuth = '';
      return cachedAdminAuth;
    }
  } catch (e) {
    // ignore and redirect below
  }

  cachedAdminAuth = null;
  window.location.href = '/admin/login';
  return null;
}

async function ensurePublicKey() {
  if (cachedPublicAuth !== null) return cachedPublicAuth;

  try {
    const ok = await verifyKey('/v1/public/verify', '');
    if (ok) {
      try {
        await fetch('/v1/public/session', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify({ key: '' })
        });
      } catch (e) {
        // ignore
      }
      cachedPublicAuth = '';
      return cachedPublicAuth;
    }
  } catch (e) {
    // ignore and redirect below
  }

  cachedPublicAuth = null;
  const admin = isAdminContext();
  window.location.href = admin ? '/admin/login' : '/login';
  return null;
}

async function logout() {
  try {
    await fetch('/v1/admin/session', {
      method: 'DELETE',
      credentials: 'same-origin'
    });
  } catch (e) {
    // ignore
  }
  resetCachedAuth();
  window.location.href = '/admin/login';
}

async function publicLogout() {
  try {
    await fetch('/v1/public/session', {
      method: 'DELETE',
      credentials: 'same-origin'
    });
  } catch (e) {
    // ignore
  }
  cachedPublicAuth = null;
  window.location.href = '/login';
}

async function fetchStorageType() {
  const apiKey = await ensureAdminKey();
  if (apiKey === null) return null;
  try {
    const res = await fetch('/v1/admin/storage', {
      headers: buildAuthHeaders(apiKey),
      credentials: 'same-origin'
    });
    if (!res.ok) return null;
    const data = await res.json();
    return (data && data.type) ? String(data.type) : null;
  } catch (e) {
    return null;
  }
}

function formatStorageLabel(type) {
  if (!type) return '-';
  const normalized = type.toLowerCase();
  const map = {
    local: 'local',
    mysql: 'mysql',
    pgsql: 'pgsql',
    postgres: 'pgsql',
    postgresql: 'pgsql',
    redis: 'redis'
  };
  return map[normalized] || '-';
}

async function updateStorageModeButton() {
  const btn = document.getElementById('storage-mode-btn');
  if (!btn) return;
  btn.textContent = '...';
  btn.title = '存储模式';
  btn.classList.remove('storage-ready');
  const storageType = await fetchStorageType();
  const label = formatStorageLabel(storageType);
  btn.textContent = label === '-' ? label : label.toUpperCase();
  btn.title = '存储模式';
  if (label !== '-') {
    btn.classList.add('storage-ready');
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', updateStorageModeButton);
} else {
  updateStorageModeButton();
}
