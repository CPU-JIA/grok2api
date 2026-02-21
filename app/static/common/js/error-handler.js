/**
 * Unified Error Handler - 统一错误处理系统
 *
 * Provides consistent error handling, logging, and user feedback
 * across the application.
 */

class ErrorHandler {
  constructor() {
    this.errorLog = [];
    this.maxLogSize = 100;
    this.setupGlobalHandlers();
  }

  /**
   * Setup global error handlers
   */
  setupGlobalHandlers() {
    // Handle uncaught errors
    window.addEventListener("error", (event) => {
      this.handleError(event.error || new Error(event.message), {
        type: "uncaught",
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
      });
    });

    // Handle unhandled promise rejections
    window.addEventListener("unhandledrejection", (event) => {
      this.handleError(event.reason, {
        type: "unhandled_rejection",
        promise: event.promise,
      });
    });
  }

  /**
   * Handle error with logging and user feedback
   * @param {Error|string} error - Error object or message
   * @param {Object} context - Additional context
   * @param {boolean} showToast - Whether to show toast notification
   */
  handleError(error, context = {}, showToast = true) {
    const errorInfo = this.normalizeError(error, context);
    this.logError(errorInfo);

    if (showToast && typeof showToast === "function") {
      showToast(errorInfo.userMessage, "error", 5000);
    }

    // Log to console in development
    if (this.isDevelopment()) {
      console.error("[ErrorHandler]", errorInfo);
    }

    return errorInfo;
  }

  /**
   * Normalize error to consistent format
   * @param {Error|string} error - Error object or message
   * @param {Object} context - Additional context
   * @returns {Object} Normalized error info
   */
  normalizeError(error, context = {}) {
    const timestamp = new Date().toISOString();
    const errorInfo = {
      timestamp,
      type: context.type || "error",
      message: "",
      userMessage: "",
      stack: null,
      context,
    };

    if (error instanceof Error) {
      errorInfo.message = error.message;
      errorInfo.stack = error.stack;
      errorInfo.name = error.name;
    } else if (typeof error === "string") {
      errorInfo.message = error;
    } else if (error && typeof error === "object") {
      errorInfo.message = error.message || JSON.stringify(error);
      errorInfo.stack = error.stack;
    } else {
      errorInfo.message = String(error);
    }

    // Generate user-friendly message
    errorInfo.userMessage = this.getUserMessage(errorInfo);

    return errorInfo;
  }

  /**
   * Generate user-friendly error message
   * @param {Object} errorInfo - Error information
   * @returns {string} User-friendly message
   */
  getUserMessage(errorInfo) {
    const { message, type, context } = errorInfo;

    // Network errors
    if (message.includes("fetch") || message.includes("network")) {
      return "网络连接失败，请检查网络后重试";
    }

    // Timeout errors
    if (message.includes("timeout")) {
      return "请求超时，请稍后重试";
    }

    // Authentication errors
    if (context.status === 401 || message.includes("unauthorized")) {
      return "认证失败，请重新登录";
    }

    // Permission errors
    if (context.status === 403 || message.includes("forbidden")) {
      return "权限不足，无法执行此操作";
    }

    // Not found errors
    if (context.status === 404) {
      return "请求的资源不存在";
    }

    // Server errors
    if (context.status >= 500) {
      return "服务器错误，请稍后重试";
    }

    // Rate limit errors
    if (context.status === 429) {
      return "请求过于频繁，请稍后重试";
    }

    // Default message
    return message || "操作失败，请重试";
  }

  /**
   * Log error to internal log
   * @param {Object} errorInfo - Error information
   */
  logError(errorInfo) {
    this.errorLog.unshift(errorInfo);

    // Keep log size under limit
    if (this.errorLog.length > this.maxLogSize) {
      this.errorLog = this.errorLog.slice(0, this.maxLogSize);
    }
  }

  /**
   * Get error log
   * @returns {Array} Error log entries
   */
  getErrorLog() {
    return [...this.errorLog];
  }

  /**
   * Clear error log
   */
  clearErrorLog() {
    this.errorLog = [];
  }

  /**
   * Check if in development mode
   * @returns {boolean}
   */
  isDevelopment() {
    return (
      window.location.hostname === "localhost" ||
      window.location.hostname === "127.0.0.1"
    );
  }

  /**
   * Handle API response errors
   * @param {Response} response - Fetch response
   * @returns {Promise<Object>} Error info
   */
  async handleApiError(response) {
    let errorData = null;

    try {
      const contentType = response.headers.get("content-type");
      if (contentType && contentType.includes("application/json")) {
        errorData = await response.json();
      } else {
        errorData = { message: await response.text() };
      }
    } catch (e) {
      errorData = { message: response.statusText };
    }

    const error = new Error(
      errorData.message || errorData.error || `HTTP ${response.status}`,
    );
    error.status = response.status;
    error.data = errorData;

    return this.handleError(error, {
      type: "api_error",
      status: response.status,
      url: response.url,
      data: errorData,
    });
  }

  /**
   * Wrap async function with error handling
   * @param {Function} fn - Async function to wrap
   * @param {Object} options - Options
   * @returns {Function} Wrapped function
   */
  wrapAsync(fn, options = {}) {
    const { showToast = true, context = {} } = options;

    return async (...args) => {
      try {
        return await fn(...args);
      } catch (error) {
        this.handleError(error, context, showToast);
        throw error;
      }
    };
  }

  /**
   * Safe fetch with error handling
   * @param {string} url - URL to fetch
   * @param {Object} options - Fetch options
   * @returns {Promise<Response>} Response
   */
  async safeFetch(url, options = {}) {
    try {
      const response = await fetch(url, options);

      if (!response.ok) {
        await this.handleApiError(response);
        throw new Error(`HTTP ${response.status}`);
      }

      return response;
    } catch (error) {
      if (error.name === "AbortError") {
        throw error; // Don't handle abort errors
      }

      this.handleError(error, {
        type: "fetch_error",
        url,
        method: options.method || "GET",
      });

      throw error;
    }
  }

  /**
   * Retry function with exponential backoff
   * @param {Function} fn - Function to retry
   * @param {Object} options - Retry options
   * @returns {Promise<any>} Result
   */
  async retry(fn, options = {}) {
    const {
      maxRetries = 3,
      initialDelay = 1000,
      maxDelay = 10000,
      backoffFactor = 2,
      onRetry = null,
    } = options;

    let lastError;
    let delay = initialDelay;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        return await fn();
      } catch (error) {
        lastError = error;

        if (attempt < maxRetries) {
          if (onRetry) {
            onRetry(attempt + 1, maxRetries, error);
          }

          await new Promise((resolve) => setTimeout(resolve, delay));
          delay = Math.min(delay * backoffFactor, maxDelay);
        }
      }
    }

    this.handleError(lastError, {
      type: "retry_exhausted",
      maxRetries,
    });

    throw lastError;
  }
}

// Create global instance
const errorHandler = new ErrorHandler();

// Export for use in other modules
if (typeof window !== "undefined") {
  window.errorHandler = errorHandler;
}
