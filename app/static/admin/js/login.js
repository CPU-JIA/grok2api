const apiKeyInput = document.getElementById("api-key-input");
const loginSubmit = document.getElementById("login-submit");
let loginPending = false;

function setLoginBusy(busy) {
  loginPending = !!busy;
  if (loginSubmit) {
    loginSubmit.disabled = !!busy;
    loginSubmit.classList.toggle("is-loading", !!busy);
    loginSubmit.textContent = busy ? "验证中..." : "登录";
  }
}

function togglePasswordVisibility() {
  const input = apiKeyInput;
  const btn = document.querySelector(".login-toggle-password");
  if (!input || !btn) return;

  const isPassword = input.type === "password";
  input.type = isPassword ? "text" : "password";
  btn.classList.toggle("active", isPassword);
  btn.setAttribute("aria-label", isPassword ? "隐藏密码" : "显示密码");
}

async function requestLogin(key) {
  const res = await fetch("/v1/admin/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    cache: "no-store",
    body: JSON.stringify({ key }),
  });
  return res.ok;
}

async function hasSession() {
  const res = await fetch("/v1/admin/verify", {
    method: "GET",
    credentials: "same-origin",
    cache: "no-store",
  });
  return res.ok;
}

async function login() {
  if (loginPending) return;

  const input = (apiKeyInput ? apiKeyInput.value : "").trim();
  if (!input) {
    showToast("请输入后台密码", "warning");
    apiKeyInput?.focus();
    return;
  }

  setLoginBusy(true);
  try {
    const ok = await requestLogin(input);
    if (ok) {
      window.location.href = "/admin/token";
      return;
    }
    showToast("密码错误", "error");
  } catch (e) {
    showToast("连接失败", "error");
  } finally {
    setLoginBusy(false);
  }
}

(async () => {
  setLoginBusy(true);
  try {
    const ok = await hasSession();
    if (ok) {
      window.location.href = "/admin/token";
    }
  } catch (e) {
    // ignore network check failure
  } finally {
    setLoginBusy(false);
  }
})();
