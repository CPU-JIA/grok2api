/**
 * Global Keyboard Shortcuts
 *
 * Supported shortcuts:
 * - Ctrl+Enter: Send message (Chat page)
 * - Ctrl+K: Open search/command palette (future)
 * - ESC: Close modal/panel
 * - Ctrl+/: Show keyboard shortcuts help
 */

(function initKeyboardShortcuts() {
  const isMac = navigator.platform.toUpperCase().indexOf("MAC") >= 0;
  const modKey = isMac ? "metaKey" : "ctrlKey";

  // Track open modals/panels
  let activeModals = [];

  // Register modal/panel
  window.registerModal = function (element) {
    if (element && !activeModals.includes(element)) {
      activeModals.push(element);
    }
  };

  // Unregister modal/panel
  window.unregisterModal = function (element) {
    activeModals = activeModals.filter((m) => m !== element);
  };

  // Global keyboard handler
  document.addEventListener("keydown", (e) => {
    // ESC: Close topmost modal/panel
    if (e.key === "Escape") {
      if (activeModals.length > 0) {
        const topModal = activeModals[activeModals.length - 1];

        // Try to find close button
        const closeBtn = topModal.querySelector(
          "[data-close], .close-btn, .modal-close",
        );
        if (closeBtn) {
          closeBtn.click();
          e.preventDefault();
          return;
        }

        // Try to hide by adding 'hidden' class
        if (!topModal.classList.contains("hidden")) {
          topModal.classList.add("hidden");
          activeModals.pop();
          e.preventDefault();
          return;
        }
      }

      // Close settings panel if open
      const settingsPanel = document.getElementById("settingsPanel");
      if (settingsPanel && !settingsPanel.classList.contains("hidden")) {
        settingsPanel.classList.add("hidden");
        e.preventDefault();
        return;
      }
    }

    // Ctrl+Enter: Send message (Chat page)
    if (e[modKey] && e.key === "Enter") {
      const sendBtn = document.getElementById("sendBtn");
      const promptInput = document.getElementById("promptInput");

      // Only trigger if we're focused on the prompt input or send button exists
      if (sendBtn && (document.activeElement === promptInput || promptInput)) {
        if (!sendBtn.disabled) {
          sendBtn.click();
          e.preventDefault();
        }
      }
    }

    // Ctrl+K: Open search/command palette (future feature)
    if (e[modKey] && e.key === "k") {
      // Placeholder for future search/command palette
      e.preventDefault();
      console.log("Search/command palette (Ctrl+K) - coming soon");
    }

    // Ctrl+/: Show keyboard shortcuts help
    if (e[modKey] && e.key === "/") {
      e.preventDefault();
      showKeyboardShortcutsHelp();
    }
  });

  // Show keyboard shortcuts help modal
  function showKeyboardShortcutsHelp() {
    const existingModal = document.getElementById("shortcuts-help-modal");
    if (existingModal) {
      existingModal.classList.remove("hidden");
      return;
    }

    const modal = document.createElement("div");
    modal.id = "shortcuts-help-modal";
    modal.className = "shortcuts-modal";
    modal.setAttribute("role", "dialog");
    modal.setAttribute("aria-labelledby", "shortcuts-title");
    modal.setAttribute("aria-modal", "true");

    const modKeyLabel = isMac ? "⌘" : "Ctrl";

    // Create modal structure using DOM methods
    const overlay = document.createElement("div");
    overlay.className = "shortcuts-overlay";
    overlay.setAttribute("data-close", "");

    const content = document.createElement("div");
    content.className = "shortcuts-content";

    const header = document.createElement("div");
    header.className = "shortcuts-header";

    const title = document.createElement("h3");
    title.id = "shortcuts-title";
    title.className = "shortcuts-title";
    title.textContent = "键盘快捷键";

    const closeBtn = document.createElement("button");
    closeBtn.className = "shortcuts-close";
    closeBtn.setAttribute("data-close", "");
    closeBtn.setAttribute("aria-label", "Close");
    closeBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <line x1="18" y1="6" x2="6" y2="18"></line>
      <line x1="6" y1="6" x2="18" y2="18"></line>
    </svg>`;

    header.appendChild(title);
    header.appendChild(closeBtn);

    const body = document.createElement("div");
    body.className = "shortcuts-body";

    // General section
    const generalSection = createShortcutsSection("通用", [
      { keys: ["ESC"], desc: "关闭模态框/面板" },
      { keys: [modKeyLabel, "/"], desc: "显示快捷键帮助" },
    ]);

    // Chat section
    const chatSection = createShortcutsSection("聊天", [
      { keys: [modKeyLabel, "Enter"], desc: "发送消息" },
    ]);

    // Coming soon section
    const comingSoonSection = createShortcutsSection("即将推出", [
      { keys: [modKeyLabel, "K"], desc: "打开搜索/命令面板" },
    ]);

    body.appendChild(generalSection);
    body.appendChild(chatSection);
    body.appendChild(comingSoonSection);

    content.appendChild(header);
    content.appendChild(body);

    modal.appendChild(overlay);
    modal.appendChild(content);

    document.body.appendChild(modal);
    registerModal(modal);

    // Close handlers
    const closeElements = modal.querySelectorAll("[data-close]");
    closeElements.forEach((el) => {
      el.addEventListener("click", () => {
        modal.classList.add("hidden");
        setTimeout(() => {
          unregisterModal(modal);
          modal.remove();
        }, 200);
      });
    });

    // Focus trap
    const focusableElements = modal.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    );
    const firstFocusable = focusableElements[0];
    const lastFocusable = focusableElements[focusableElements.length - 1];

    modal.addEventListener("keydown", (e) => {
      if (e.key === "Tab") {
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

    if (firstFocusable) {
      firstFocusable.focus();
    }
  }

  // Helper to create shortcuts section
  function createShortcutsSection(title, shortcuts) {
    const section = document.createElement("div");
    section.className = "shortcuts-section";

    const sectionTitle = document.createElement("h4");
    sectionTitle.className = "shortcuts-section-title";
    sectionTitle.textContent = title;

    const list = document.createElement("div");
    list.className = "shortcuts-list";

    shortcuts.forEach((shortcut) => {
      const item = document.createElement("div");
      item.className = "shortcut-item";

      const keys = document.createElement("span");
      keys.className = "shortcut-keys";
      shortcut.keys.forEach((key, index) => {
        const kbd = document.createElement("kbd");
        kbd.textContent = key;
        keys.appendChild(kbd);
        if (index < shortcut.keys.length - 1) {
          keys.appendChild(document.createTextNode(" + "));
        }
      });

      const desc = document.createElement("span");
      desc.className = "shortcut-desc";
      desc.textContent = shortcut.desc;

      item.appendChild(keys);
      item.appendChild(desc);
      list.appendChild(item);
    });

    section.appendChild(sectionTitle);
    section.appendChild(list);

    return section;
  }

  // Auto-register settings panel when it opens
  const settingsToggle = document.getElementById("settingsToggle");
  const settingsPanel = document.getElementById("settingsPanel");
  if (settingsToggle && settingsPanel) {
    settingsToggle.addEventListener("click", () => {
      if (!settingsPanel.classList.contains("hidden")) {
        registerModal(settingsPanel);
      } else {
        unregisterModal(settingsPanel);
      }
    });
  }

  console.log("Keyboard shortcuts initialized");
})();
