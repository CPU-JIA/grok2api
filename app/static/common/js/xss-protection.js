/**
 * XSS Protection Utilities
 *
 * Provides safe HTML sanitization and DOM manipulation functions
 * to prevent XSS attacks across the application.
 */

/**
 * Escape HTML special characters to prevent XSS
 * @param {string} text - Text to escape
 * @returns {string} Escaped text safe for HTML insertion
 */
function escapeHtml(text) {
  if (text == null) return "";
  const div = document.createElement("div");
  div.textContent = String(text);
  return div.innerHTML;
}

/**
 * Safely set text content (never interprets as HTML)
 * @param {HTMLElement} element - Target element
 * @param {string} text - Text content to set
 */
function safeSetText(element, text) {
  if (!element) return;
  element.textContent = String(text || "");
}

/**
 * Create a safe DOM element with text content
 * @param {string} tagName - Element tag name
 * @param {string} text - Text content
 * @param {string} className - Optional CSS class
 * @returns {HTMLElement} Created element
 */
function createSafeElement(tagName, text, className) {
  const element = document.createElement(tagName);
  if (text) element.textContent = String(text);
  if (className) element.className = className;
  return element;
}

/**
 * Safely append text to an element
 * @param {HTMLElement} parent - Parent element
 * @param {string} text - Text to append
 */
function safeAppendText(parent, text) {
  if (!parent) return;
  const textNode = document.createTextNode(String(text || ""));
  parent.appendChild(textNode);
}

/**
 * Validate and sanitize URL to prevent javascript: protocol
 * @param {string} url - URL to validate
 * @returns {string} Safe URL or empty string if invalid
 */
function sanitizeUrl(url) {
  if (!url) return "";
  const urlStr = String(url).trim();

  // Block dangerous protocols
  if (/^(javascript|data|vbscript):/i.test(urlStr)) {
    console.warn("Blocked dangerous URL protocol:", urlStr);
    return "";
  }

  return urlStr;
}

/**
 * Safely set element attribute
 * @param {HTMLElement} element - Target element
 * @param {string} name - Attribute name
 * @param {string} value - Attribute value
 */
function safeSetAttribute(element, name, value) {
  if (!element || !name) return;

  // Block event handler attributes
  if (/^on/i.test(name)) {
    console.warn("Blocked event handler attribute:", name);
    return;
  }

  // Sanitize URL attributes
  if (["href", "src", "action", "formaction"].includes(name.toLowerCase())) {
    value = sanitizeUrl(value);
  }

  if (value !== "") {
    element.setAttribute(name, String(value));
  }
}

/**
 * Clear element content safely
 * @param {HTMLElement} element - Element to clear
 */
function safeClearElement(element) {
  if (!element) return;
  while (element.firstChild) {
    element.removeChild(element.firstChild);
  }
}

// Export functions for use in other modules
if (typeof window !== "undefined") {
  window.XSSProtection = {
    escapeHtml,
    safeSetText,
    createSafeElement,
    safeAppendText,
    sanitizeUrl,
    safeSetAttribute,
    safeClearElement,
  };
}
