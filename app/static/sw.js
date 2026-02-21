/**
 * Service Worker for Offline Support
 *
 * Features:
 * - Cache static assets
 * - Offline fallback
 * - Cache-first strategy for static resources
 * - Network-first strategy for API calls
 */

const CACHE_NAME = "grok2api-v1";
const STATIC_CACHE = "grok2api-static-v1";
const DYNAMIC_CACHE = "grok2api-dynamic-v1";

// Static assets to cache on install
const STATIC_ASSETS = [
  "/",
  "/static/common/css/common.css",
  "/static/common/css/toast.css",
  "/static/common/css/keyboard-shortcuts.css",
  "/static/common/css/skeleton.css",
  "/static/common/css/lazy-loading.css",
  "/static/common/css/error-boundary.css",
  "/static/common/css/mobile-cards.css",
  "/static/common/css/form-validation.css",
  "/static/common/js/toast.js",
  "/static/common/js/keyboard-shortcuts.js",
  "/static/common/js/dark-mode.js",
  "/static/common/js/form-validation.js",
  "/static/common/js/lazy-loading.js",
  "/static/common/js/error-boundary.js",
  "/static/common/js/header.js",
  "/static/common/js/footer.js",
  "/static/common/img/favicon/favicon.ico",
];

// Install event - cache static assets
self.addEventListener("install", (event) => {
  console.log("[SW] Installing...");

  event.waitUntil(
    caches
      .open(STATIC_CACHE)
      .then((cache) => {
        console.log("[SW] Caching static assets");
        return cache.addAll(STATIC_ASSETS);
      })
      .then(() => {
        console.log("[SW] Installed successfully");
        return self.skipWaiting();
      })
      .catch((error) => {
        console.error("[SW] Installation failed:", error);
      }),
  );
});

// Activate event - clean up old caches
self.addEventListener("activate", (event) => {
  console.log("[SW] Activating...");

  event.waitUntil(
    caches
      .keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames
            .filter((name) => {
              return name !== STATIC_CACHE && name !== DYNAMIC_CACHE;
            })
            .map((name) => {
              console.log("[SW] Deleting old cache:", name);
              return caches.delete(name);
            }),
        );
      })
      .then(() => {
        console.log("[SW] Activated successfully");
        return self.clients.claim();
      }),
  );
});

// Fetch event - serve from cache or network
self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests
  if (request.method !== "GET") {
    return;
  }

  // Skip chrome-extension and other non-http(s) requests
  if (!url.protocol.startsWith("http")) {
    return;
  }

  // API requests - Network first, cache fallback
  if (url.pathname.startsWith("/v1/") || url.pathname.startsWith("/api/")) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          // Clone response for caching
          const responseClone = response.clone();

          // Cache successful responses
          if (response.status === 200) {
            caches.open(DYNAMIC_CACHE).then((cache) => {
              cache.put(request, responseClone);
            });
          }

          return response;
        })
        .catch(() => {
          // Network failed, try cache
          return caches.match(request).then((cachedResponse) => {
            if (cachedResponse) {
              return cachedResponse;
            }

            // Return offline fallback
            return new Response(
              JSON.stringify({
                error: "offline",
                message: "You are offline. Please check your connection.",
              }),
              {
                status: 503,
                headers: { "Content-Type": "application/json" },
              },
            );
          });
        }),
    );
    return;
  }

  // Static assets - Cache first, network fallback
  event.respondWith(
    caches.match(request).then((cachedResponse) => {
      if (cachedResponse) {
        // Return cached version
        return cachedResponse;
      }

      // Not in cache, fetch from network
      return fetch(request)
        .then((response) => {
          // Don't cache non-successful responses
          if (
            !response ||
            response.status !== 200 ||
            response.type === "error"
          ) {
            return response;
          }

          // Clone response for caching
          const responseClone = response.clone();

          // Cache static assets
          if (
            url.pathname.startsWith("/static/") ||
            url.pathname.endsWith(".css") ||
            url.pathname.endsWith(".js") ||
            url.pathname.endsWith(".png") ||
            url.pathname.endsWith(".jpg") ||
            url.pathname.endsWith(".svg") ||
            url.pathname.endsWith(".ico")
          ) {
            caches.open(STATIC_CACHE).then((cache) => {
              cache.put(request, responseClone);
            });
          } else {
            // Cache dynamic content
            caches.open(DYNAMIC_CACHE).then((cache) => {
              cache.put(request, responseClone);
            });
          }

          return response;
        })
        .catch(() => {
          // Network failed, return offline page
          return caches.match("/offline.html").then((offlinePage) => {
            if (offlinePage) {
              return offlinePage;
            }

            // Fallback offline response
            return new Response(
              "<html><body><h1>Offline</h1><p>You are currently offline.</p></body></html>",
              {
                status: 503,
                headers: { "Content-Type": "text/html" },
              },
            );
          });
        });
    }),
  );
});

// Message event - handle messages from clients
self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }

  if (event.data && event.data.type === "CLEAR_CACHE") {
    event.waitUntil(
      caches.keys().then((cacheNames) => {
        return Promise.all(cacheNames.map((name) => caches.delete(name)));
      }),
    );
  }
});
