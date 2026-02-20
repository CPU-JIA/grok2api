const publicKeyInput = document.getElementById('public-key-input');
const loginSubmit = document.getElementById('public-login-submit');
let loginPending = false;

function setLoginBusy(busy) {
  loginPending = !!busy;
  if (loginSubmit) {
    loginSubmit.disabled = !!busy;
    loginSubmit.textContent = busy ? '校验中...' : '进入';
  }
}

async function requestPublicLogin(key) {
  const headers = key ? { 'Authorization': `Bearer ${key}` } : {};
  const res = await fetch('/v1/public/verify', {
    method: 'GET',
    headers,
    cache: 'no-store'
  });
  return res.ok;
}

async function login() {
  if (loginPending) return;

  const input = (publicKeyInput ? publicKeyInput.value : '').trim();
  setLoginBusy(true);
  try {
    const ok = await requestPublicLogin(input);
    if (ok) {
      await storePublicKey(input);
      window.location.href = '/imagine';
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
  setLoginBusy(true);
  try {
    const stored = await getStoredPublicKey();
    if (stored) {
      const ok = await requestPublicLogin(stored);
      if (ok) {
        window.location.href = '/imagine';
        return;
      }
      clearStoredPublicKey();
    }

    const ok = await requestPublicLogin('');
    if (ok) {
      window.location.href = '/imagine';
    }
  } catch (e) {
    // ignore
  } finally {
    setLoginBusy(false);
  }
})();