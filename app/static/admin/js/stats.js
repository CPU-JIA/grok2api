(() => {
  let apiKey = "";
  let hourlyChart = null;
  let dailyChart = null;
  let modelsChart = null;
  let activeTab = "request";
  let statsPending = false;
  let logsPending = false;
  let refreshPending = false;
  let logsLoaded = false;
  let logsRaw = [];
  let logsTotal = 0;
  let logsFilter = "all";
  let logsCurrentPage = 1;
  let logsPageSize = 50;
  let modelItems = [];
  let activeModelIndex = 0;

  const byId = (id) => document.getElementById(id);
  const MODEL_COLORS = [
    "#3b82f6",
    "#22c55e",
    "#f97316",
    "#8b5cf6",
    "#ec4899",
    "#06b6d4",
    "#eab308",
    "#ef4444",
    "#14b8a6",
    "#6366f1",
  ];

  function setBusy(btn, busy) {
    if (!btn) return;
    btn.disabled = !!busy;
    btn.classList.toggle("is-busy", !!busy);
    btn.setAttribute("aria-busy", busy ? "true" : "false");
  }

  function formatInt(value) {
    const num = Number(value || 0);
    if (!Number.isFinite(num)) return "0";
    return Math.round(num).toLocaleString();
  }

  function formatModelCount(value) {
    const num = Number(value || 0);
    if (!Number.isFinite(num)) return "0";
    if (num >= 10000) return `${(num / 1000).toFixed(1)}K`;
    return `${Math.round(num)}`;
  }

  function createFillGradient(canvas, topColor, bottomColor) {
    const ctx = canvas?.getContext?.("2d");
    if (!ctx) return bottomColor;
    const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height || 240);
    gradient.addColorStop(0, topColor);
    gradient.addColorStop(1, bottomColor);
    return gradient;
  }

  function setActiveTab(tab, { force = false } = {}) {
    if (!force && activeTab === tab) return false;
    activeTab = tab;

    const tabs = document.querySelectorAll(".stats-tab");
    tabs.forEach((btn) => {
      const current = btn.dataset.tab || "";
      const isActive = current === tab;
      btn.classList.toggle("active", isActive);
      btn.setAttribute("aria-selected", isActive ? "true" : "false");
    });

    const reqPanel = byId("stats-panel-request");
    const logPanel = byId("stats-panel-logs");
    if (reqPanel) reqPanel.classList.toggle("hidden", tab !== "request");
    if (logPanel) logPanel.classList.toggle("hidden", tab !== "logs");
    return true;
  }

  function updateSummary(summary) {
    if (!summary) return;
    const rateValue = String(summary.success_rate ?? "0")
      .replace("%", "")
      .trim();
    const rateRaw = Number(rateValue);
    const rate = Number.isFinite(rateRaw)
      ? `${rateRaw.toFixed(1).replace(/\.0$/, "")}%`
      : "0%";

    if (byId("stat-total-req"))
      byId("stat-total-req").textContent = formatInt(summary.total);
    if (byId("stat-success-req"))
      byId("stat-success-req").textContent = formatInt(summary.success);
    if (byId("stat-failed-req"))
      byId("stat-failed-req").textContent = formatInt(summary.failed);
    if (byId("stat-success-rate")) byId("stat-success-rate").textContent = rate;
  }

  function destroyCharts() {
    if (hourlyChart) hourlyChart.destroy();
    if (dailyChart) dailyChart.destroy();
    if (modelsChart) modelsChart.destroy();
    hourlyChart = null;
    dailyChart = null;
    modelsChart = null;
  }

  function getSafeModelIndex() {
    if (!Array.isArray(modelItems) || modelItems.length === 0) return -1;
    if (activeModelIndex < 0 || activeModelIndex >= modelItems.length) return 0;
    return activeModelIndex;
  }

  function updateModelCenter(index) {
    const main = byId("models-center-main");
    const sub = byId("models-center-sub");
    if (!main || !sub) return;

    if (index < 0 || !modelItems[index]) {
      main.textContent = "-";
      sub.textContent = "调用: 0 次 (0%)";
      return;
    }

    const item = modelItems[index];
    main.textContent = item.model;
    sub.textContent = `调用: ${formatModelCount(item.count)} 次 (${item.percent}%)`;
  }

  function renderModelLegend() {
    const legend = byId("models-legend");
    if (!legend) return;
    legend.replaceChildren();

    if (!Array.isArray(modelItems) || modelItems.length === 0) {
      const empty = document.createElement("div");
      empty.className = "models-empty";
      empty.textContent = "暂无模型调用数据";
      legend.appendChild(empty);
      return;
    }

    const totalCount = modelItems.reduce((sum, item) => sum + item.count, 0);
    const totalEl = document.createElement("div");
    totalEl.className = "model-donut-total";
    totalEl.textContent = `${formatInt(totalCount)} 总调用`;
    legend.appendChild(totalEl);

    const safeIndex = getSafeModelIndex();
    modelItems.forEach((item, index) => {
      const row = document.createElement("button");
      row.type = "button";
      row.className = `model-donut-legend-row ${index === safeIndex ? "active" : ""}`;
      row.setAttribute("role", "listitem");

      const left = document.createElement("div");
      left.className = "model-donut-legend-left";

      const dot = document.createElement("span");
      dot.className = "model-donut-legend-dot";
      dot.style.backgroundColor = item.color;

      const name = document.createElement("span");
      name.className = "model-donut-legend-name";
      name.title = item.model;
      name.textContent = item.model;

      const value = document.createElement("span");
      value.className = "model-donut-legend-value";
      value.textContent = `${formatModelCount(item.count)} (${item.percent}%)`;

      left.appendChild(dot);
      left.appendChild(name);
      row.appendChild(left);
      row.appendChild(value);

      row.addEventListener("click", () => {
        setActiveModel(index);
      });

      legend.appendChild(row);
    });
  }

  function applyChartActiveState() {
    if (!modelsChart || !Array.isArray(modelItems) || modelItems.length === 0)
      return;
    const safeIndex = getSafeModelIndex();
    const dataset = modelsChart.data.datasets && modelsChart.data.datasets[0];
    if (!dataset) return;

    dataset.offset = modelItems.map((_, idx) => (idx === safeIndex ? 6 : 0));
    dataset.borderColor = modelItems.map((_, idx) =>
      idx === safeIndex ? "rgba(17, 24, 39, 0.9)" : "#ffffff",
    );
    dataset.borderWidth = modelItems.map((_, idx) =>
      idx === safeIndex ? 2 : 1,
    );

    modelsChart.update("none");
  }

  function setActiveModel(index) {
    if (!Array.isArray(modelItems) || modelItems.length === 0) {
      activeModelIndex = 0;
      updateModelCenter(-1);
      return;
    }
    if (index < 0 || index >= modelItems.length) return;

    activeModelIndex = index;
    updateModelCenter(index);
    renderModelLegend();
    applyChartActiveState();
  }

  function renderTrendCharts(payload) {
    if (typeof Chart === "undefined") return;

    const hourly = Array.isArray(payload.hourly) ? payload.hourly : [];
    const daily = Array.isArray(payload.daily) ? payload.daily : [];

    const hourlyCanvas = byId("chart-hourly");
    if (hourlyCanvas) {
      hourlyChart = new Chart(hourlyCanvas, {
        type: "line",
        data: {
          labels: hourly.map((item) => item.hour),
          datasets: [
            {
              label: "成功",
              data: hourly.map((item) => Number(item.success || 0)),
              borderColor: "#10b981",
              backgroundColor: createFillGradient(
                hourlyCanvas,
                "rgba(16, 185, 129, 0.18)",
                "rgba(16, 185, 129, 0.02)",
              ),
              fill: true,
              borderWidth: 2.2,
              tension: 0.32,
              pointRadius: 0,
              pointHoverRadius: 4,
              pointHitRadius: 10,
            },
            {
              label: "失败",
              data: hourly.map((item) => Number(item.failed || 0)),
              borderColor: "#ef4444",
              backgroundColor: createFillGradient(
                hourlyCanvas,
                "rgba(239, 68, 68, 0.14)",
                "rgba(239, 68, 68, 0.02)",
              ),
              fill: true,
              borderWidth: 2.1,
              tension: 0.32,
              pointRadius: 0,
              pointHoverRadius: 4,
              pointHitRadius: 10,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: false,
          interaction: { mode: "index", intersect: false },
          plugins: {
            legend: {
              display: true,
              position: "top",
              labels: {
                boxWidth: 10,
                boxHeight: 10,
                usePointStyle: true,
                pointStyle: "circle",
              },
            },
          },
          scales: {
            x: { grid: { display: false } },
            y: {
              beginAtZero: true,
              ticks: { precision: 0 },
              grid: { color: "rgba(148, 163, 184, 0.2)" },
            },
          },
        },
      });
    }

    const dailyCanvas = byId("chart-daily");
    if (dailyCanvas) {
      const dayLabels = daily.map((item) => item.date);
      const dayTotal = daily.map((item) => {
        const explicit = Number(item.total);
        if (Number.isFinite(explicit)) return explicit;
        return Number(item.success || 0) + Number(item.failed || 0);
      });
      const daySuccess = daily.map((item) => Number(item.success || 0));
      const dayRate = dayTotal.map((total, index) =>
        total > 0 ? (daySuccess[index] / total) * 100 : 0,
      );

      dailyChart = new Chart(dailyCanvas, {
        type: "line",
        data: {
          labels: dayLabels,
          datasets: [
            {
              label: "请求量",
              yAxisID: "y",
              data: dayTotal,
              borderColor: "#3b82f6",
              backgroundColor: createFillGradient(
                dailyCanvas,
                "rgba(59, 130, 246, 0.16)",
                "rgba(59, 130, 246, 0.02)",
              ),
              fill: true,
              borderWidth: 2.2,
              tension: 0.28,
              pointRadius: 2,
              pointHoverRadius: 4,
              pointHitRadius: 10,
            },
            {
              label: "成功率",
              yAxisID: "yRate",
              data: dayRate,
              borderColor: "#f59e0b",
              backgroundColor: "rgba(245, 158, 11, 0.12)",
              fill: false,
              borderWidth: 2,
              tension: 0.25,
              pointRadius: 2,
              pointHoverRadius: 4,
              pointHitRadius: 10,
              borderDash: [6, 4],
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: false,
          interaction: { mode: "index", intersect: false },
          plugins: {
            legend: {
              display: true,
              position: "top",
              labels: {
                boxWidth: 10,
                boxHeight: 10,
                usePointStyle: true,
                pointStyle: "circle",
              },
            },
            tooltip: {
              callbacks: {
                label(context) {
                  if (context.dataset && context.dataset.yAxisID === "yRate") {
                    const value = Number(context.raw || 0);
                    return `${context.dataset.label}: ${value.toFixed(1).replace(/\.0$/, "")}%`;
                  }
                  return `${context.dataset.label}: ${formatInt(context.raw)}`;
                },
              },
            },
          },
          scales: {
            x: { grid: { display: false } },
            y: {
              position: "left",
              beginAtZero: true,
              ticks: { precision: 0 },
              grid: { color: "rgba(148, 163, 184, 0.2)" },
            },
            yRate: {
              position: "right",
              beginAtZero: true,
              min: 0,
              max: 100,
              ticks: {
                callback(value) {
                  return `${value}%`;
                },
              },
              grid: { drawOnChartArea: false },
            },
          },
        },
      });
    }
  }

  function renderModelChart() {
    if (typeof Chart === "undefined") return;

    const modelsCanvas = byId("chart-models");
    if (!modelsCanvas) return;

    if (!Array.isArray(modelItems) || modelItems.length === 0) {
      updateModelCenter(-1);
      return;
    }

    const total = modelItems.reduce((sum, item) => sum + item.count, 0);

    modelsChart = new Chart(modelsCanvas, {
      type: "doughnut",
      data: {
        labels: modelItems.map((item) => item.model),
        datasets: [
          {
            label: "调用次数",
            data: modelItems.map((item) => item.count),
            backgroundColor: modelItems.map((item) => item.color),
            borderColor: "#ffffff",
            borderWidth: 1,
            hoverOffset: 5,
            offset: modelItems.map(() => 0),
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        cutout: "68%",
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label(context) {
                const value = Number(context.raw || 0);
                const ratio = total > 0 ? (value / total) * 100 : 0;
                return `${context.label}: ${formatInt(value)} (${ratio.toFixed(ratio >= 10 ? 0 : 1)}%)`;
              },
            },
          },
        },
        onClick(_evt, elements) {
          if (!elements || elements.length === 0) return;
          const first = elements[0];
          if (typeof first.index === "number") {
            setActiveModel(first.index);
          }
        },
      },
    });

    const safeIndex = getSafeModelIndex();
    setActiveModel(safeIndex < 0 ? 0 : safeIndex);
  }

  function renderStats(payload) {
    const rawModels = (
      Array.isArray(payload.models) ? payload.models : []
    ).slice(0, 10);
    const normalized = rawModels.map((item) => ({
      model: String(item.model || "-"),
      count: Number(item.count || 0),
    }));
    const total = normalized.reduce((sum, item) => sum + item.count, 0);

    modelItems = normalized.map((item, index) => {
      const rawPercent = total > 0 ? (item.count / total) * 100 : 0;
      return {
        ...item,
        color: MODEL_COLORS[index % MODEL_COLORS.length],
        percent: Number(rawPercent.toFixed(rawPercent >= 10 ? 0 : 1)),
      };
    });

    activeModelIndex = 0;

    destroyCharts();
    renderTrendCharts(payload);
    renderModelLegend();
    renderModelChart();
  }

  async function loadStats({ silent = false } = {}) {
    if (statsPending) return;
    statsPending = true;
    const refreshBtn = byId("stats-refresh-btn");
    if (!silent && !refreshPending) setBusy(refreshBtn, true);

    try {
      const res = await fetch("/v1/admin/stats?hours=24&days=7", {
        headers: buildAuthHeaders(apiKey),
        cache: "no-store",
      });
      if (res.status === 401) {
        logout();
        return;
      }
      const data = await res.json();
      updateSummary(data.summary);
      renderStats(data);
    } catch (e) {
      if (typeof showToast === "function") showToast("加载统计失败", "error");
    } finally {
      statsPending = false;
      if (!silent && !refreshPending) setBusy(refreshBtn, false);
    }
  }

  function getLogStatusType(status) {
    const code = Number(status || 0);
    if (code >= 200 && code < 300) return "success";
    if (code >= 300 && code < 400) return "warn";
    return "error";
  }

  function getLogFilterLabel(filter) {
    if (filter === "success") return "成功";
    if (filter === "error") return "失败";
    return "全部";
  }

  function statusBadge(status) {
    const span = document.createElement("span");
    const type = getLogStatusType(status);
    span.className = "status-badge";
    span.classList.add(type);
    if (type === "success") {
      span.textContent = "成功";
    } else if (type === "warn") {
      span.textContent = "跳转";
    } else {
      span.textContent = "失败";
    }
    return span;
  }

  function formatDuration(duration) {
    const value = Number(duration || 0);
    if (!Number.isFinite(value) || value <= 0) return "-";
    if (value < 1) return `${(value * 1000).toFixed(0)}ms`;
    if (value < 10) return `${value.toFixed(2)}s`;
    return `${value.toFixed(1)}s`;
  }

  function splitLogTime(rawTime) {
    const text = String(rawTime || "").trim();
    if (!text) return { date: "-", clock: "" };
    const parts = text.split(" ");
    if (parts.length >= 2) {
      return { date: parts[0], clock: parts.slice(1).join(" ") };
    }
    return { date: text, clock: "" };
  }

  function updateLogsSummary(filteredCount, recentCount, totalCount) {
    const summary = byId("logs-summary");
    const summarySub = byId("logs-summary-sub");
    if (summary) {
      summary.textContent = `显示 ${formatInt(filteredCount)} / ${formatInt(recentCount)} 条请求记录`;
    }
    if (summarySub) {
      summarySub.textContent = `累计 ${formatInt(totalCount)} 条 · 筛选：${getLogFilterLabel(logsFilter)}`;
    }
  }

  async function resetStats() {
    const resetBtn = byId("stats-reset-btn");
    if (resetBtn?.disabled) return;

    const ok = window.confirm("确定要重置请求统计吗？日志审计数据不会被清空。");
    if (!ok) return;

    setBusy(resetBtn, true);
    try {
      const res = await fetch("/v1/admin/stats/reset", {
        method: "POST",
        headers: buildAuthHeaders(apiKey),
      });
      if (res.status === 401) {
        logout();
        return;
      }
      if (!res.ok) throw new Error("重置统计失败");

      destroyCharts();
      modelItems = [];
      activeModelIndex = 0;
      updateSummary({ total: 0, success: 0, failed: 0, success_rate: 0 });
      renderModelLegend();
      updateModelCenter(-1);

      await loadStats({ silent: true });
      if (typeof showToast === "function") showToast("统计已重置", "success");
    } catch (e) {
      if (typeof showToast === "function") showToast("重置统计失败", "error");
    } finally {
      setBusy(resetBtn, false);
    }
  }

  function updateLogFilterTabs() {
    const buttons = document.querySelectorAll(".logs-filter-btn");
    buttons.forEach((btn) => {
      const isActive = (btn.dataset.filter || "all") === logsFilter;
      btn.classList.toggle("active", isActive);
      btn.setAttribute("aria-selected", isActive ? "true" : "false");
    });
  }

  function updateLogFilterCounts(list) {
    const safeList = Array.isArray(list) ? list : [];
    const success = safeList.filter(
      (item) => getLogStatusType(item?.status) === "success",
    ).length;
    const error = safeList.length - success;

    const allEl = byId("logs-filter-all");
    const successEl = byId("logs-filter-success");
    const errorEl = byId("logs-filter-error");

    if (allEl) allEl.textContent = formatInt(safeList.length);
    if (successEl) successEl.textContent = formatInt(success);
    if (errorEl) errorEl.textContent = formatInt(error);
  }

  function filterLogs(list) {
    const safeList = Array.isArray(list) ? list : [];

    return safeList.filter((item) => {
      const type = getLogStatusType(item?.status);
      if (logsFilter === "success" && type !== "success") return false;
      if (logsFilter === "error" && type === "success") return false;
      return true;
    });
  }

  function renderLogs(logs) {
    const tbody = byId("logs-table-body");
    const empty = byId("logs-empty");
    if (!tbody) return;
    tbody.replaceChildren();

    if (!logs || logs.length === 0) {
      if (empty) empty.classList.remove("hidden");
      return;
    }
    if (empty) empty.classList.add("hidden");

    const fragment = document.createDocumentFragment();
    logs.forEach((item) => {
      const tr = document.createElement("tr");
      const statusType = getLogStatusType(item.status || 0);
      if (statusType === "error") tr.classList.add("log-row-error");

      const tdTime = document.createElement("td");
      tdTime.className = "text-left";
      const timeWrap = document.createElement("div");
      timeWrap.className = "log-time";
      const timeMain = document.createElement("div");
      timeMain.className = "log-time-main";
      const timeSub = document.createElement("div");
      timeSub.className = "log-time-sub";
      const splitTime = splitLogTime(item.time);
      timeMain.textContent = splitTime.date;
      timeSub.textContent = splitTime.clock || "--:--:--";
      timeWrap.appendChild(timeMain);
      timeWrap.appendChild(timeSub);
      tdTime.appendChild(timeWrap);

      const tdIp = document.createElement("td");
      tdIp.className = "text-left log-muted";
      tdIp.textContent = item.ip || "-";

      const tdModel = document.createElement("td");
      tdModel.className = "text-left";
      const modelPill = document.createElement("span");
      modelPill.className = "log-pill";
      modelPill.textContent = item.model || "-";
      modelPill.title = item.model || "-";
      tdModel.appendChild(modelPill);

      const tdDuration = document.createElement("td");
      tdDuration.className = "text-center log-muted";
      tdDuration.textContent = formatDuration(item.duration);

      const tdStatus = document.createElement("td");
      tdStatus.className = "text-center";
      tdStatus.appendChild(statusBadge(item.status || 0));

      const tdKey = document.createElement("td");
      tdKey.className = "text-left";
      const keyLabel = item.key_name || item.key_masked || "";
      if (keyLabel) {
        const keyPill = document.createElement("span");
        keyPill.className = "log-pill log-pill-key";
        keyPill.textContent = keyLabel;
        keyPill.title = keyLabel;
        tdKey.appendChild(keyPill);
      } else {
        tdKey.textContent = "-";
        tdKey.classList.add("log-muted");
      }

      const tdError = document.createElement("td");
      tdError.className = "text-left";
      if (item.error) {
        const errorText = document.createElement("div");
        errorText.className = "log-error-text";
        errorText.textContent = item.error;
        errorText.title = item.error;
        tdError.appendChild(errorText);
      } else {
        tdError.classList.add("log-muted");
        tdError.textContent = "-";
      }

      tr.appendChild(tdTime);
      tr.appendChild(tdIp);
      tr.appendChild(tdModel);
      tr.appendChild(tdDuration);
      tr.appendChild(tdStatus);
      tr.appendChild(tdKey);
      tr.appendChild(tdError);
      fragment.appendChild(tr);
    });

    tbody.appendChild(fragment);
  }

  function getLogsTotalPages(filteredLogs) {
    const total = Array.isArray(filteredLogs) ? filteredLogs.length : 0;
    return Math.max(1, Math.ceil(total / logsPageSize));
  }

  function getLogsPageData(filteredLogs) {
    const safeList = Array.isArray(filteredLogs) ? filteredLogs : [];
    const totalPages = getLogsTotalPages(safeList);
    const safePage = Math.max(1, Math.min(logsCurrentPage, totalPages));

    const startIndex = (safePage - 1) * logsPageSize;
    const endIndex = startIndex + logsPageSize;
    const pageItems = safeList.slice(startIndex, endIndex);

    return { pageItems, totalPages, safePage, totalItems: safeList.length };
  }

  function updateLogsPagination(pageData) {
    const { safePage, totalPages, totalItems } = pageData;

    const info = byId("logs-pagination-info");
    if (info) {
      info.textContent = `第 ${safePage} / ${totalPages} 页 · 共 ${formatInt(totalItems)} 条`;
    }

    const firstBtn = byId("logs-page-first");
    const prevBtn = byId("logs-page-prev");
    const nextBtn = byId("logs-page-next");
    const lastBtn = byId("logs-page-last");

    if (firstBtn) firstBtn.disabled = safePage <= 1;
    if (prevBtn) prevBtn.disabled = safePage <= 1;
    if (nextBtn) nextBtn.disabled = safePage >= totalPages;
    if (lastBtn) lastBtn.disabled = safePage >= totalPages;
  }

  function applyLogsView() {
    updateLogFilterTabs();

    const sourceLogs = Array.isArray(logsRaw) ? logsRaw : [];
    updateLogFilterCounts(sourceLogs);

    const filteredLogs = filterLogs(sourceLogs);
    const pageData = getLogsPageData(filteredLogs);

    logsCurrentPage = pageData.safePage;

    renderLogs(pageData.pageItems);
    updateLogsSummary(
      pageData.totalItems,
      sourceLogs.length,
      logsTotal || sourceLogs.length,
    );
    updateLogsPagination(pageData);
  }

  async function loadLogs({ silent = false } = {}) {
    if (logsPending) return;
    logsPending = true;

    const clearBtn = byId("logs-clear-btn");
    if (!silent && clearBtn) clearBtn.disabled = true;

    try {
      const res = await fetch("/v1/admin/logs?limit=100&offset=0", {
        headers: buildAuthHeaders(apiKey),
        cache: "no-store",
      });
      if (res.status === 401) {
        logout();
        return;
      }
      const data = await res.json();
      logsRaw = Array.isArray(data.logs) ? data.logs : [];
      logsTotal = Number.isFinite(Number(data.total))
        ? Number(data.total)
        : logsRaw.length;
      applyLogsView();
      logsLoaded = true;
    } catch (e) {
      if (typeof showToast === "function") showToast("加载日志失败", "error");
    } finally {
      logsPending = false;
      if (!silent && clearBtn) clearBtn.disabled = false;
    }
  }

  async function clearLogs() {
    const clearBtn = byId("logs-clear-btn");
    if (clearBtn?.disabled) return;

    const ok = window.confirm("确定要清空所有日志吗？");
    if (!ok) return;

    setBusy(clearBtn, true);
    try {
      const res = await fetch("/v1/admin/logs/clear", {
        method: "POST",
        headers: buildAuthHeaders(apiKey),
      });
      if (res.status === 401) {
        logout();
        return;
      }
      if (!res.ok) throw new Error("清空失败");
      await loadLogs({ silent: true });
      if (typeof showToast === "function") showToast("日志已清空", "success");
    } catch (e) {
      if (typeof showToast === "function") showToast("清空失败", "error");
    } finally {
      setBusy(clearBtn, false);
    }
  }

  async function refreshAll() {
    if (refreshPending) return;
    refreshPending = true;
    const refreshBtn = byId("stats-refresh-btn");
    setBusy(refreshBtn, true);
    try {
      await Promise.all([
        loadStats({ silent: true }),
        loadLogs({ silent: true }),
      ]);
    } finally {
      refreshPending = false;
      setBusy(refreshBtn, false);
    }
  }

  function bindEvents() {
    const refreshBtn = byId("stats-refresh-btn");
    if (refreshBtn) refreshBtn.addEventListener("click", refreshAll);
    const resetBtn = byId("stats-reset-btn");
    if (resetBtn) resetBtn.addEventListener("click", resetStats);

    const tabs = document.querySelectorAll(".stats-tab");
    tabs.forEach((tabBtn) => {
      tabBtn.addEventListener("click", async () => {
        const targetTab = tabBtn.dataset.tab || "request";
        const changed = setActiveTab(targetTab);
        if (!changed) return;
        if (targetTab === "logs" && !logsLoaded) {
          await loadLogs();
        }
      });
    });

    const filterBtns = document.querySelectorAll(".logs-filter-btn");
    filterBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        const nextFilter = btn.dataset.filter || "all";
        if (logsFilter === nextFilter) return;
        logsFilter = nextFilter;
        applyLogsView();
      });
    });

    const clearBtn = byId("logs-clear-btn");
    if (clearBtn) clearBtn.addEventListener("click", clearLogs);
  }

  window.logsGoFirstPage = function () {
    logsCurrentPage = 1;
    applyLogsView();
  };

  window.logsGoPrevPage = function () {
    if (logsCurrentPage > 1) {
      logsCurrentPage--;
      applyLogsView();
    }
  };

  window.logsGoNextPage = function () {
    const sourceLogs = Array.isArray(logsRaw) ? logsRaw : [];
    const filteredLogs = filterLogs(sourceLogs);
    const totalPages = getLogsTotalPages(filteredLogs);
    if (logsCurrentPage < totalPages) {
      logsCurrentPage++;
      applyLogsView();
    }
  };

  window.logsGoLastPage = function () {
    const sourceLogs = Array.isArray(logsRaw) ? logsRaw : [];
    const filteredLogs = filterLogs(sourceLogs);
    const totalPages = getLogsTotalPages(filteredLogs);
    logsCurrentPage = totalPages;
    applyLogsView();
  };

  window.logsChangePageSize = function () {
    const select = byId("logs-page-size");
    if (!select) return;
    const newSize = Number(select.value);
    if (Number.isFinite(newSize) && newSize > 0) {
      logsPageSize = newSize;
      logsCurrentPage = 1;
      applyLogsView();
    }
  };

  async function init() {
    apiKey = await ensureAdminKey();
    if (apiKey === null) return false;

    bindEvents();
    applyLogsView();
    setActiveTab("request", { force: true });
    await Promise.all([loadStats(), loadLogs()]);
    return true;
  }

  let statsInitStarted = false;
  async function initStatsPage() {
    if (statsInitStarted) return;
    statsInitStarted = true;
    try {
      const ok = await init();
      if (ok === false) {
        statsInitStarted = false;
      }
    } catch (e) {
      statsInitStarted = false;
      throw e;
    }
  }

  if (window.__registerAdminPage) {
    window.__registerAdminPage("stats", initStatsPage);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initStatsPage);
  } else {
    initStatsPage();
  }
})();
