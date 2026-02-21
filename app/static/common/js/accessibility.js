/**
 * ARIA Accessibility Enhancements
 *
 * Features:
 * - Auto-add ARIA labels to interactive elements
 * - Focus management
 * - Keyboard navigation
 * - Screen reader announcements
 */

(function initAccessibility() {
  // Add ARIA labels to buttons without labels
  function addAriaLabels() {
    // Buttons without aria-label or aria-labelledby
    const buttons = document.querySelectorAll(
      "button:not([aria-label]):not([aria-labelledby])",
    );

    buttons.forEach((button) => {
      // Skip if button has visible text
      if (button.textContent.trim()) {
        return;
      }

      // Try to infer label from context
      let label = "";

      // Check for icon + title
      if (button.title) {
        label = button.title;
      }
      // Check for parent label
      else if (button.closest("label")) {
        label = button.closest("label").textContent.trim();
      }
      // Check for nearby text
      else if (button.previousElementSibling?.textContent) {
        label = button.previousElementSibling.textContent.trim();
      }
      // Check for class names
      else if (button.className) {
        const classNames = button.className.split(" ");
        const meaningfulClass = classNames.find(
          (c) =>
            c.includes("delete") ||
            c.includes("edit") ||
            c.includes("save") ||
            c.includes("cancel") ||
            c.includes("close") ||
            c.includes("submit"),
        );
        if (meaningfulClass) {
          label = meaningfulClass.replace(/[-_]/g, " ");
        }
      }

      if (label) {
        button.setAttribute("aria-label", label);
      }
    });

    // Add role="button" to clickable elements
    const clickables = document.querySelectorAll(
      "[onclick]:not(button):not(a):not([role])",
    );
    clickables.forEach((el) => {
      el.setAttribute("role", "button");
      el.setAttribute("tabindex", "0");
    });

    // Add aria-live to dynamic content areas
    const dynamicAreas = document.querySelectorAll(
      ".chat-log, .toast-container, #statusText",
    );
    dynamicAreas.forEach((area) => {
      if (!area.hasAttribute("aria-live")) {
        area.setAttribute("aria-live", "polite");
      }
    });

    // Add role="alert" to error messages
    const errors = document.querySelectorAll(
      ".error, .field-error, .toast-error",
    );
    errors.forEach((error) => {
      if (!error.hasAttribute("role")) {
        error.setAttribute("role", "alert");
      }
    });

    // Add aria-describedby to inputs with help text
    const inputs = document.querySelectorAll("input, textarea, select");
    inputs.forEach((input) => {
      const helpText = input.parentElement?.querySelector(
        ".help-text, .field-help, .login-help",
      );
      if (helpText && !input.hasAttribute("aria-describedby")) {
        const helpId =
          helpText.id || `help-${Math.random().toString(36).substr(2, 9)}`;
        helpText.id = helpId;
        input.setAttribute("aria-describedby", helpId);
      }
    });

    // Add aria-expanded to toggles
    const toggles = document.querySelectorAll(
      "[data-toggle], .dropdown-toggle, .accordion-toggle",
    );
    toggles.forEach((toggle) => {
      if (!toggle.hasAttribute("aria-expanded")) {
        toggle.setAttribute("aria-expanded", "false");
      }
    });
  }

  // Focus management
  function manageFocus() {
    // Skip to main content link
    const skipLink = document.createElement("a");
    skipLink.href = "#main-content";
    skipLink.className = "skip-link";
    skipLink.textContent = "跳转到主内容";
    skipLink.setAttribute("aria-label", "Skip to main content");

    skipLink.addEventListener("click", (e) => {
      e.preventDefault();
      const main =
        document.getElementById("main-content") ||
        document.querySelector("main");
      if (main) {
        main.setAttribute("tabindex", "-1");
        main.focus();
      }
    });

    document.body.insertBefore(skipLink, document.body.firstChild);

    // Focus trap for modals
    document.addEventListener("keydown", (e) => {
      // Check if we're in a modal
      const modal = document.querySelector(
        '[role="dialog"][aria-modal="true"]:not(.hidden)',
      );
      if (!modal) return;

      if (e.key === "Tab") {
        const focusableElements = modal.querySelectorAll(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
        );
        const firstFocusable = focusableElements[0];
        const lastFocusable = focusableElements[focusableElements.length - 1];

        if (e.shiftKey) {
          if (document.activeElement === firstFocusable) {
            lastFocusable.focus();
            e.preventDefault();
          }
        } else {
          if (document.activeElement === lastFocusable) {
            firstFocusable.focus();
            e.preventDefault();
          }
        }
      }
    });
  }

  // Keyboard navigation for custom components
  function enhanceKeyboardNav() {
    // Make clickable divs keyboard accessible
    document.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        const target = e.target;
        if (
          target.hasAttribute("role") &&
          target.getAttribute("role") === "button"
        ) {
          target.click();
          e.preventDefault();
        }
      }
    });

    // Arrow key navigation for lists
    const lists = document.querySelectorAll('[role="listbox"], [role="menu"]');
    lists.forEach((list) => {
      list.addEventListener("keydown", (e) => {
        const items = Array.from(
          list.querySelectorAll('[role="option"], [role="menuitem"]'),
        );
        const currentIndex = items.indexOf(document.activeElement);

        if (e.key === "ArrowDown") {
          e.preventDefault();
          const nextIndex = (currentIndex + 1) % items.length;
          items[nextIndex]?.focus();
        } else if (e.key === "ArrowUp") {
          e.preventDefault();
          const prevIndex = (currentIndex - 1 + items.length) % items.length;
          items[prevIndex]?.focus();
        } else if (e.key === "Home") {
          e.preventDefault();
          items[0]?.focus();
        } else if (e.key === "End") {
          e.preventDefault();
          items[items.length - 1]?.focus();
        }
      });
    });
  }

  // Screen reader announcements
  function createAnnouncer() {
    const announcer = document.createElement("div");
    announcer.id = "sr-announcer";
    announcer.className = "sr-only";
    announcer.setAttribute("role", "status");
    announcer.setAttribute("aria-live", "polite");
    announcer.setAttribute("aria-atomic", "true");
    document.body.appendChild(announcer);

    // Expose announce function
    window.announceToScreenReader = (message, priority = "polite") => {
      announcer.setAttribute("aria-live", priority);
      announcer.textContent = message;

      // Clear after announcement
      setTimeout(() => {
        announcer.textContent = "";
      }, 1000);
    };
  }

  // Initialize
  function init() {
    addAriaLabels();
    manageFocus();
    enhanceKeyboardNav();
    createAnnouncer();

    // Re-run on dynamic content changes
    const observer = new MutationObserver(() => {
      addAriaLabels();
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true,
    });
  }

  // Auto-init
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  console.log("Accessibility enhancements initialized");
})();
