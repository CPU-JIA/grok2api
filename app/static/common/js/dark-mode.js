/**
 * Dark Mode Theme Switcher
 *
 * Features:
 * - Toggle between light and dark themes
 * - Persist preference in localStorage
 * - Sync with system theme preference
 * - Smooth transitions
 */

(function initDarkMode() {
  const STORAGE_KEY = "grok2api_theme";
  const THEME_ATTR = "data-theme";

  // Get initial theme
  function getInitialTheme() {
    // Check localStorage first
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "dark" || stored === "light") {
      return stored;
    }

    // Check system preference
    if (
      window.matchMedia &&
      window.matchMedia("(prefers-color-scheme: dark)").matches
    ) {
      return "dark";
    }

    return "light";
  }

  // Apply theme
  function applyTheme(theme) {
    document.documentElement.setAttribute(THEME_ATTR, theme);
    localStorage.setItem(STORAGE_KEY, theme);

    // Update toggle button if exists
    updateToggleButton(theme);
  }

  // Create SVG icon elements
  function createSunIcon() {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("width", "16");
    svg.setAttribute("height", "16");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "2");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("stroke-linejoin", "round");

    const elements = [
      { tag: "circle", attrs: { cx: "12", cy: "12", r: "5" } },
      { tag: "line", attrs: { x1: "12", y1: "1", x2: "12", y2: "3" } },
      { tag: "line", attrs: { x1: "12", y1: "21", x2: "12", y2: "23" } },
      {
        tag: "line",
        attrs: { x1: "4.22", y1: "4.22", x2: "5.64", y2: "5.64" },
      },
      {
        tag: "line",
        attrs: { x1: "18.36", y1: "18.36", x2: "19.78", y2: "19.78" },
      },
      { tag: "line", attrs: { x1: "1", y1: "12", x2: "3", y2: "12" } },
      { tag: "line", attrs: { x1: "21", y1: "12", x2: "23", y2: "12" } },
      {
        tag: "line",
        attrs: { x1: "4.22", y1: "19.78", x2: "5.64", y2: "18.36" },
      },
      {
        tag: "line",
        attrs: { x1: "18.36", y1: "5.64", x2: "19.78", y2: "4.22" },
      },
    ];

    elements.forEach(({ tag, attrs }) => {
      const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
      Object.entries(attrs).forEach(([key, value]) =>
        el.setAttribute(key, value),
      );
      svg.appendChild(el);
    });

    return svg;
  }

  function createMoonIcon() {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("width", "16");
    svg.setAttribute("height", "16");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "2");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("stroke-linejoin", "round");

    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", "M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z");
    svg.appendChild(path);

    return svg;
  }

  // Update toggle button state
  function updateToggleButton(theme) {
    const toggleBtn = document.getElementById("theme-toggle");
    if (!toggleBtn) return;

    const isDark = theme === "dark";
    toggleBtn.setAttribute(
      "aria-label",
      isDark ? "Switch to light mode" : "Switch to dark mode",
    );
    toggleBtn.setAttribute(
      "title",
      isDark ? "Switch to light mode" : "Switch to dark mode",
    );

    // Update icon
    const icon = toggleBtn.querySelector(".theme-icon");
    if (icon) {
      icon.innerHTML = "";
      icon.appendChild(isDark ? createSunIcon() : createMoonIcon());
    }
  }

  // Toggle theme
  function toggleTheme() {
    const current =
      document.documentElement.getAttribute(THEME_ATTR) || "light";
    const next = current === "dark" ? "light" : "dark";
    applyTheme(next);
  }

  // Initialize theme
  const initialTheme = getInitialTheme();
  applyTheme(initialTheme);

  // Listen for system theme changes
  if (window.matchMedia) {
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    mediaQuery.addEventListener("change", (e) => {
      // Only auto-switch if user hasn't manually set a preference
      const stored = localStorage.getItem(STORAGE_KEY);
      if (!stored) {
        applyTheme(e.matches ? "dark" : "light");
      }
    });
  }

  // Expose toggle function globally
  window.toggleTheme = toggleTheme;

  // Auto-attach to toggle button if exists
  function attachToggleButton() {
    const toggleBtn = document.getElementById("theme-toggle");
    if (toggleBtn) {
      toggleBtn.addEventListener("click", toggleTheme);
      updateToggleButton(initialTheme);
    }
  }

  // Try to attach immediately or wait for DOM
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", attachToggleButton);
  } else {
    attachToggleButton();
  }

  console.log("Dark mode initialized:", initialTheme);
})();
