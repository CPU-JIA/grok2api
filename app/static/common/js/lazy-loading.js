/**
 * Lazy Loading for Images
 *
 * Features:
 * - Intersection Observer API
 * - Loading placeholder
 * - Fade-in animation
 * - Error handling
 * - Retry mechanism
 */

(function initLazyLoading() {
  // Configuration
  const config = {
    rootMargin: "50px", // Start loading 50px before entering viewport
    threshold: 0.01,
    loadingClass: "lazy-loading",
    loadedClass: "lazy-loaded",
    errorClass: "lazy-error",
  };

  // Create observer
  let observer;

  function createObserver() {
    if (!("IntersectionObserver" in window)) {
      // Fallback: load all images immediately
      loadAllImages();
      return;
    }

    observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            loadImage(entry.target);
            observer.unobserve(entry.target);
          }
        });
      },
      {
        rootMargin: config.rootMargin,
        threshold: config.threshold,
      },
    );
  }

  // Load image
  function loadImage(img) {
    const src = img.dataset.src;
    if (!src) return;

    // Add loading class
    img.classList.add(config.loadingClass);

    // Create new image to preload
    const tempImg = new Image();

    tempImg.onload = () => {
      // Set actual src
      img.src = src;
      img.removeAttribute("data-src");

      // Remove loading, add loaded
      img.classList.remove(config.loadingClass);
      img.classList.add(config.loadedClass);

      // Trigger custom event
      img.dispatchEvent(new CustomEvent("lazyloaded", { bubbles: true }));
    };

    tempImg.onerror = () => {
      // Handle error
      img.classList.remove(config.loadingClass);
      img.classList.add(config.errorClass);

      // Set fallback or retry
      const retryCount = parseInt(img.dataset.retryCount || "0");
      if (retryCount < 3) {
        // Retry after delay
        img.dataset.retryCount = (retryCount + 1).toString();
        setTimeout(
          () => {
            img.classList.remove(config.errorClass);
            loadImage(img);
          },
          1000 * (retryCount + 1),
        );
      } else {
        // Show error placeholder
        img.alt = img.alt || "Failed to load image";
        img.dispatchEvent(new CustomEvent("lazyerror", { bubbles: true }));
      }
    };

    // Start loading
    tempImg.src = src;
  }

  // Load all images (fallback)
  function loadAllImages() {
    const images = document.querySelectorAll("img[data-src]");
    images.forEach((img) => {
      img.src = img.dataset.src;
      img.removeAttribute("data-src");
    });
  }

  // Observe images
  function observeImages() {
    if (!observer) return;

    const images = document.querySelectorAll("img[data-src]");
    images.forEach((img) => {
      // Add loading placeholder if not set
      if (!img.src || img.src === window.location.href) {
        img.src =
          'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300"%3E%3Crect fill="%23f5f5f5" width="400" height="300"/%3E%3Ctext fill="%23999" x="50%25" y="50%25" dominant-baseline="middle" text-anchor="middle" font-family="sans-serif" font-size="18"%3ELoading...%3C/text%3E%3C/svg%3E';
      }

      observer.observe(img);
    });
  }

  // Initialize
  function init() {
    createObserver();
    observeImages();
  }

  // Re-observe new images (for dynamic content)
  function refresh() {
    observeImages();
  }

  // Expose globally
  window.lazyLoading = {
    init: init,
    refresh: refresh,
    observe: (img) => {
      if (observer && img.dataset.src) {
        observer.observe(img);
      }
    },
  };

  // Auto-init on DOM ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // Watch for dynamically added images
  if ("MutationObserver" in window) {
    const mutationObserver = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        mutation.addedNodes.forEach((node) => {
          if (node.nodeType === 1) {
            // Element node
            // Check if node itself is an image
            if (node.tagName === "IMG" && node.dataset.src) {
              if (observer) {
                observer.observe(node);
              }
            }
            // Check for images in added subtree
            const images = node.querySelectorAll?.("img[data-src]");
            if (images) {
              images.forEach((img) => {
                if (observer) {
                  observer.observe(img);
                }
              });
            }
          }
        });
      });
    });

    mutationObserver.observe(document.body, {
      childList: true,
      subtree: true,
    });
  }

  console.log("Lazy loading initialized");
})();
