const publicKeyInput = document.getElementById("public-key-input");
const loginSubmit = document.getElementById("public-login-submit");
let loginPending = false;

function setLoginBusy(busy) {
  loginPending = !!busy;
  if (loginSubmit) {
    loginSubmit.disabled = !!busy;
    loginSubmit.classList.toggle("is-loading", !!busy);
    loginSubmit.textContent = busy ? "验证中..." : "进入";
  }
}

function togglePasswordVisibility() {
  const input = publicKeyInput;
  const btn = document.querySelector(".login-toggle-password");
  if (!input || !btn) return;

  const isPassword = input.type === "password";
  input.type = isPassword ? "text" : "password";
  btn.classList.toggle("active", isPassword);
  btn.setAttribute("aria-label", isPassword ? "隐藏密码" : "显示密码");
}

async function requestPublicLogin(key) {
  const res = await fetch("/v1/public/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    cache: "no-store",
    body: JSON.stringify({ key }),
  });
  return res.ok;
}

async function hasSession() {
  const res = await fetch("/v1/public/verify", {
    method: "GET",
    credentials: "same-origin",
    cache: "no-store",
  });
  if (!res.ok) return false;
  try {
    await requestPublicLogin("");
  } catch (e) {
    // ignore
  }
  return true;
}

async function login() {
  if (loginPending) return;

  const input = (publicKeyInput ? publicKeyInput.value : "").trim();
  setLoginBusy(true);
  try {
    const ok = await requestPublicLogin(input);
    if (ok) {
      window.location.href = "/imagine";
      return;
    }
    showToast("密钥无效", "error");
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
      window.location.href = "/imagine";
    }
  } catch (e) {
    // ignore
  } finally {
    setLoginBusy(false);
  }
})();
