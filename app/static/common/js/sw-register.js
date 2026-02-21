/**
 * Service Worker Registration
 *
 * Features:
 * - Register service worker
 * - Handle updates
 * - Show offline indicator
 */

(function initServiceWorker() {
  // Check if service workers are supported
  if (!("serviceWorker" in navigator)) {
    console.log("[SW] Service workers not supported");
    return;
  }

  // Register service worker
  function registerServiceWorker() {
    navigator.serviceWorker
      .register("/static/sw.js", { scope: "/" })
      .then((registration) => {
        console.log("[SW] Registered successfully:", registration.scope);

        // Check for updates
        registration.addEventListener("updatefound", () => {
          const newWorker = registration.installing;
          console.log("[SW] Update found");

          newWorker.addEventListener("statechange", () => {
            if (
              newWorker.state === "installed" &&
              navigator.serviceWorker.controller
            ) {
              // New service worker available
              showUpdateNotification(newWorker);
            }
          });
        });
      })
      .catch((error) => {
        console.error("[SW] Registration failed:", error);
      });
  }

  // Show update notification
  function showUpdateNotification(worker) {
    if (typeof showToast === "function") {
      const message = "新版本可用，点击刷新";
      showToast(message, "success");

      // Auto-reload after 5 seconds
      setTimeout(() => {
        worker.postMessage({ type: "SKIP_WAITING" });
        window.location.reload();
      }, 5000);
    }
  }

  // Show offline indicator
  function updateOnlineStatus() {
    const isOnline = navigator.onLine;

    if (!isOnline) {
      if (typeof showToast === "function") {
        showToast("您已离线，部分功能可能不可用", "error");
      }
    }
  }

  // Listen for online/offline events
  window.addEventListener("online", () => {
    if (typeof showToast === "function") {
      showToast("已恢复网络连接", "success");
    }
  });

  window.addEventListener("offline", updateOnlineStatus);

  // Register on load
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", registerServiceWorker);
  } else {
    registerServiceWorker();
  }

  // Check initial online status
  updateOnlineStatus();

  console.log("[SW] Service worker registration initialized");
})();
