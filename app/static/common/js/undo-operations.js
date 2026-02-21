/**
 * Undo/Redo Operations
 *
 * Features:
 * - Undo delete operations
 * - Toast with undo button
 * - 3-second undo window
 * - Operation queue management
 */

(function initUndoOperations() {
  // Undo queue
  const undoQueue = [];
  const MAX_UNDO_HISTORY = 10;

  // Add operation to undo queue
  function addUndoOperation(operation) {
    undoQueue.push(operation);

    // Limit queue size
    if (undoQueue.length > MAX_UNDO_HISTORY) {
      undoQueue.shift();
    }
  }

  // Execute undo
  function executeUndo(operationId) {
    const operation = undoQueue.find((op) => op.id === operationId);
    if (!operation) {
      console.warn("[Undo] Operation not found:", operationId);
      return;
    }

    // Execute undo callback
    if (operation.undo && typeof operation.undo === "function") {
      operation.undo();
      console.log("[Undo] Operation undone:", operationId);

      // Remove from queue
      const index = undoQueue.indexOf(operation);
      if (index > -1) {
        undoQueue.splice(index, 1);
      }

      // Show success toast
      if (typeof showToast === "function") {
        showToast("操作已撤销", "success");
      }
    }
  }

  // Show undo toast
  function showUndoToast(message, operationId, timeout = 3000) {
    // Ensure container exists
    let container = document.getElementById("toast-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "toast-container";
      container.className = "toast-container";
      document.body.appendChild(container);
    }

    const toast = document.createElement("div");
    toast.className = "toast toast-undo";

    const iconDiv = document.createElement("div");
    iconDiv.className = "toast-icon";
    const iconSvg = document.createElementNS(
      "http://www.w3.org/2000/svg",
      "svg",
    );
    iconSvg.setAttribute("width", "12");
    iconSvg.setAttribute("height", "12");
    iconSvg.setAttribute("viewBox", "0 0 24 24");
    iconSvg.setAttribute("fill", "none");
    iconSvg.setAttribute("stroke", "currentColor");
    iconSvg.setAttribute("stroke-width", "3");
    iconSvg.setAttribute("stroke-linecap", "round");
    iconSvg.setAttribute("stroke-linejoin", "round");
    const polyline = document.createElementNS(
      "http://www.w3.org/2000/svg",
      "polyline",
    );
    polyline.setAttribute("points", "20 6 9 17 4 12");
    iconSvg.appendChild(polyline);
    iconDiv.appendChild(iconSvg);

    const contentDiv = document.createElement("div");
    contentDiv.className = "toast-content";
    contentDiv.textContent = message;

    const undoBtn = document.createElement("button");
    undoBtn.className = "toast-undo-btn";
    undoBtn.textContent = "撤销";
    undoBtn.setAttribute("aria-label", "Undo operation");

    const closeBtn = document.createElement("button");
    closeBtn.className = "toast-close";
    closeBtn.setAttribute("aria-label", "Close");
    const closeSvg = document.createElementNS(
      "http://www.w3.org/2000/svg",
      "svg",
    );
    closeSvg.setAttribute("width", "14");
    closeSvg.setAttribute("height", "14");
    closeSvg.setAttribute("viewBox", "0 0 24 24");
    closeSvg.setAttribute("fill", "none");
    closeSvg.setAttribute("stroke", "currentColor");
    closeSvg.setAttribute("stroke-width", "2");
    closeSvg.setAttribute("stroke-linecap", "round");
    closeSvg.setAttribute("stroke-linejoin", "round");
    const line1 = document.createElementNS(
      "http://www.w3.org/2000/svg",
      "line",
    );
    line1.setAttribute("x1", "18");
    line1.setAttribute("y1", "6");
    line1.setAttribute("x2", "6");
    line1.setAttribute("y2", "18");
    const line2 = document.createElementNS(
      "http://www.w3.org/2000/svg",
      "line",
    );
    line2.setAttribute("x1", "6");
    line2.setAttribute("y1", "6");
    line2.setAttribute("x2", "18");
    line2.setAttribute("y2", "18");
    closeSvg.appendChild(line1);
    closeSvg.appendChild(line2);
    closeBtn.appendChild(closeSvg);

    toast.appendChild(iconDiv);
    toast.appendChild(contentDiv);
    toast.appendChild(undoBtn);
    toast.appendChild(closeBtn);

    container.appendChild(toast);

    // Remove toast
    const removeToast = () => {
      toast.classList.add("out");
      toast.addEventListener("animationend", () => {
        if (toast.parentElement) {
          toast.parentElement.removeChild(toast);
        }
      });
    };

    // Undo button handler
    undoBtn.addEventListener("click", () => {
      executeUndo(operationId);
      removeToast();
    });

    // Close button handler
    closeBtn.addEventListener("click", removeToast);

    // Auto-remove after timeout
    setTimeout(removeToast, timeout);
  }

  // Expose globally
  window.undoOperations = {
    // Register an undoable operation
    register: (operation) => {
      const operationId = `undo-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      const undoOperation = {
        id: operationId,
        timestamp: Date.now(),
        ...operation,
      };

      addUndoOperation(undoOperation);

      // Show undo toast
      if (operation.message) {
        showUndoToast(
          operation.message,
          operationId,
          operation.timeout || 3000,
        );
      }

      return operationId;
    },

    // Execute undo manually
    undo: executeUndo,

    // Clear undo queue
    clear: () => {
      undoQueue.length = 0;
    },

    // Get queue size
    size: () => undoQueue.length,
  };

  console.log("Undo operations initialized");
})();
