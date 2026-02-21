(function (global) {
  function normalizeApiKey(apiKey) {
    if (!apiKey) return '';
    const trimmed = String(apiKey).trim();
    return trimmed.startsWith('Bearer ') ? trimmed.slice(7).trim() : trimmed;
  }

  function openBatchStream(taskId, apiKey, handlers = {}) {
    if (!taskId) return null;

    const rawKey = normalizeApiKey(apiKey);
    const query = rawKey ? `?app_key=${encodeURIComponent(rawKey)}` : '';
    const url = `/v1/admin/batch/${taskId}/stream${query}`;
    const es = new EventSource(url);

    es.onmessage = (e) => {
      if (!e.data) return;
      let msg;
      try {
        msg = JSON.parse(e.data);
      } catch {
        return;
      }
      if (handlers.onMessage) handlers.onMessage(msg);
    };

    es.onerror = () => {
      if (handlers.onError) handlers.onError();
    };

    return es;
  }

  function closeBatchStream(es) {
    if (es) es.close();
  }

  async function cancelBatchTask(taskId, apiKey) {
    if (!taskId) return;
    try {
      const rawKey = normalizeApiKey(apiKey);
      const headers = rawKey ? { Authorization: `Bearer ${rawKey}` } : undefined;
      await fetch(`/v1/admin/batch/${taskId}/cancel`, {
        method: 'POST',
        headers,
        credentials: 'same-origin'
      });
    } catch {
      // ignore
    }
  }

  global.BatchSSE = {
    open: openBatchStream,
    close: closeBatchStream,
    cancel: cancelBatchTask
  };
})(window);
