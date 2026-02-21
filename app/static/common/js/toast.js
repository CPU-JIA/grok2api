function showToast(message, type = "success", duration = 3000) {
  // Ensure container exists
  let container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    container.className = "toast-container";
    document.body.appendChild(container);
  }

  const toast = document.createElement("div");
  toast.className = "toast";

  const isSuccess = type === "success";
  const isWarning = type === "warning";
  const isInfo = type === "info";

  if (isSuccess) toast.classList.add("toast-success");
  else if (isWarning) toast.classList.add("toast-warning");
  else if (isInfo) toast.classList.add("toast-info");
  else toast.classList.add("toast-error");

  const iconSvg = isSuccess
    ? `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>`
    : isWarning || isInfo
      ? `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>`
      : `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>`;

  // Create toast elements safely
  const iconDiv = document.createElement("div");
  iconDiv.className = "toast-icon";
  iconDiv.innerHTML = iconSvg;

  const contentDiv = document.createElement("div");
  contentDiv.className = "toast-content";
  contentDiv.textContent = message;

  const closeBtn = document.createElement("button");
  closeBtn.className = "toast-close";
  closeBtn.setAttribute("aria-label", "Close");
  closeBtn.setAttribute("title", "Close");
  closeBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <line x1="18" y1="6" x2="6" y2="18"></line>
    <line x1="6" y1="6" x2="18" y2="18"></line>
  </svg>`;

  toast.appendChild(iconDiv);
  toast.appendChild(contentDiv);
  toast.appendChild(closeBtn);

  container.appendChild(toast);

  // Trigger animation
  requestAnimationFrame(() => {
    toast.classList.add("show");
  });

  // Close button handler
  const removeToast = () => {
    toast.classList.remove("show");
    toast.classList.add("out");
    setTimeout(() => {
      if (toast.parentElement) {
        toast.parentElement.removeChild(toast);
      }
    }, 300);
  };

  closeBtn.addEventListener("click", removeToast);

  // Auto-remove after specified duration
  if (duration > 0) {
    setTimeout(removeToast, duration);
  }
}

(function showRateLimitNoticeOnce() {
  const noticeKey = "grok2api_rate_limits_notice_v1";
  const noticeText =
    "GROK官方服务 rate-limits 更新后暂时无法准确计算 Token 剩余，等待官方接口优化后持续修复";
  const path = window.location.pathname || "";

  if (!path.startsWith("/admin") || path.startsWith("/admin/login")) {
    return;
  }

  try {
    if (localStorage.getItem(noticeKey)) {
      return;
    }
    localStorage.setItem(noticeKey, "1");
  } catch (e) {
    // If storage is blocked, just skip the one-time guard.
  }

  const show = () => {
    if (typeof showToast === "function") {
      showToast(noticeText, "error", 5000);
    }
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", show);
  } else {
    show();
  }
})();
