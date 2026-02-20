const apiKeyInput = document.getElementById('api-key-input');
const loginSubmit = document.getElementById('login-submit');
let loginPending = false;

function setLoginBusy(busy) {
  loginPending = !!busy;
  if (loginSubmit) {
    loginSubmit.disabled = !!busy;
    loginSubmit.textContent = busy ? '验证中...' : '继续';
  }
}

async function requestLogin(key) {
  const res = await fetch('/v1/admin/verify', {
    method: 'GET',
    headers: { 'Authorization': `Bearer ${key}` },
    cache: 'no-store'
  });
  return res.ok;
}

async function login() {
  if (loginPending) return;

  const input = (apiKeyInput ? apiKeyInput.value : '').trim();
  if (!input) {
    showToast('请输入后台密码', 'warning');
    apiKeyInput?.focus();
    return;
  }

  setLoginBusy(true);
  try {
    const ok = await requestLogin(input);
    if (ok) {
      await storeAppKey(input);
      window.location.href = '/admin/token';
      return;
    }
    showToast('密钥无效', 'error');
  } catch (e) {
    showToast('连接失败', 'error');
  } finally {
    setLoginBusy(false);
  }
}

(async () => {
  const existingKey = await getStoredAppKey();
  if (!existingKey) return;

  setLoginBusy(true);
  try {
    const ok = await requestLogin(existingKey);
    if (ok) {
      window.location.href = '/admin/token';
      return;
    }
    clearStoredAppKey();
  } catch (e) {
    // ignore network check failure
  } finally {
    setLoginBusy(false);
  }
})();