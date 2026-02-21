/**
 * Form Validation Utilities
 *
 * Features:
 * - Real-time validation on blur
 * - Error message display
 * - Required field validation
 * - Email/URL format validation
 * - Custom validation rules
 */

(function initFormValidation() {
  // Validation rules
  const validators = {
    required: (value) => {
      return value.trim().length > 0 ? null : "此字段必填";
    },

    email: (value) => {
      if (!value) return null;
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      return emailRegex.test(value) ? null : "请输入有效的邮箱地址";
    },

    url: (value) => {
      if (!value) return null;
      try {
        new URL(value);
        return null;
      } catch {
        return "请输入有效的 URL";
      }
    },

    minLength: (min) => (value) => {
      if (!value) return null;
      return value.length >= min ? null : `至少需要 ${min} 个字符`;
    },

    maxLength: (max) => (value) => {
      if (!value) return null;
      return value.length <= max ? null : `最多 ${max} 个字符`;
    },

    number: (value) => {
      if (!value) return null;
      return !isNaN(value) ? null : "请输入有效的数字";
    },

    integer: (value) => {
      if (!value) return null;
      return Number.isInteger(Number(value)) ? null : "请输入整数";
    },

    min: (minValue) => (value) => {
      if (!value) return null;
      return Number(value) >= minValue ? null : `最小值为 ${minValue}`;
    },

    max: (maxValue) => (value) => {
      if (!value) return null;
      return Number(value) <= maxValue ? null : `最大值为 ${maxValue}`;
    },

    pattern: (regex, message) => (value) => {
      if (!value) return null;
      return regex.test(value) ? null : message || "格式不正确";
    },
  };

  // Show error message
  function showError(input, message) {
    // Remove existing error
    hideError(input);

    // Add error class
    input.classList.add("input-error");
    input.setAttribute("aria-invalid", "true");

    // Create error message element
    const errorEl = document.createElement("div");
    errorEl.className = "field-error";
    errorEl.setAttribute("role", "alert");
    errorEl.textContent = message;

    // Insert after input
    input.parentNode.insertBefore(errorEl, input.nextSibling);

    // Link error to input for accessibility
    const errorId = `error-${input.id || Math.random().toString(36).substr(2, 9)}`;
    errorEl.id = errorId;
    input.setAttribute("aria-describedby", errorId);
  }

  // Hide error message
  function hideError(input) {
    input.classList.remove("input-error");
    input.removeAttribute("aria-invalid");
    input.removeAttribute("aria-describedby");

    // Remove error message
    const errorEl = input.parentNode.querySelector(".field-error");
    if (errorEl) {
      errorEl.remove();
    }
  }

  // Validate input
  function validateInput(input) {
    const rules = input.getAttribute("data-validate");
    if (!rules) return true;

    const value = input.value;
    const ruleList = rules.split("|");

    for (const rule of ruleList) {
      let validator;
      let error;

      // Parse rule with parameters
      if (rule.includes(":")) {
        const [ruleName, params] = rule.split(":");
        const paramList = params.split(",");

        if (ruleName === "minLength") {
          validator = validators.minLength(Number(paramList[0]));
        } else if (ruleName === "maxLength") {
          validator = validators.maxLength(Number(paramList[0]));
        } else if (ruleName === "min") {
          validator = validators.min(Number(paramList[0]));
        } else if (ruleName === "max") {
          validator = validators.max(Number(paramList[0]));
        } else if (ruleName === "pattern") {
          validator = validators.pattern(
            new RegExp(paramList[0]),
            paramList[1],
          );
        }
      } else {
        validator = validators[rule];
      }

      if (validator) {
        error = validator(value);
        if (error) {
          showError(input, error);
          return false;
        }
      }
    }

    hideError(input);
    return true;
  }

  // Validate form
  function validateForm(form) {
    const inputs = form.querySelectorAll("[data-validate]");
    let isValid = true;

    inputs.forEach((input) => {
      if (!validateInput(input)) {
        isValid = false;
      }
    });

    return isValid;
  }

  // Auto-attach validation to inputs
  function attachValidation() {
    const inputs = document.querySelectorAll("[data-validate]");

    inputs.forEach((input) => {
      // Validate on blur
      input.addEventListener("blur", () => {
        validateInput(input);
      });

      // Clear error on input
      input.addEventListener("input", () => {
        if (input.classList.contains("input-error")) {
          hideError(input);
        }
      });
    });

    // Validate forms on submit
    const forms = document.querySelectorAll("form[data-validate-form]");
    forms.forEach((form) => {
      form.addEventListener("submit", (e) => {
        if (!validateForm(form)) {
          e.preventDefault();
          e.stopPropagation();

          // Focus first error
          const firstError = form.querySelector(".input-error");
          if (firstError) {
            firstError.focus();
          }
        }
      });
    });
  }

  // Expose validation functions globally
  window.formValidation = {
    validate: validateInput,
    validateForm: validateForm,
    showError: showError,
    hideError: hideError,
    validators: validators,
  };

  // Auto-attach on DOM ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", attachValidation);
  } else {
    attachValidation();
  }

  console.log("Form validation initialized");
})();
