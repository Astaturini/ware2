// =====================================================================
// Experiment lifecycle, experiments list, visualization, analysis, compare
// =====================================================================

// =====================================================================
// Setup JSON helpers
// =====================================================================

function parseSetupJson(id, fallback) {
  const el = document.getElementById(id);
  if (!el) return fallback;

  const raw = el.value.trim();
  if (!raw) return fallback;

  try {
    return JSON.parse(raw);
  } catch (error) {
    throw new Error(`${id} contains invalid JSON.`);
  }
}

function parseSetupJsonObject(id, fallback = {}) {
  const value = parseSetupJson(id, fallback);

  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${id} must be a JSON object.`);
  }

  return value;
}

function parseSetupJsonArray(id, fallback = []) {
  const value = parseSetupJson(id, fallback);

  if (!Array.isArray(value)) {
    throw new Error(`${id} must be a JSON array.`);
  }

  return value;
}

function validateNonNegativeNumberObject(obj, label) {
  const cleaned = {};

  Object.entries(obj || {}).forEach(([key, value]) => {
    const num = Number(value);

    if (!Number.isFinite(num) || num < 0) {
      throw new Error(`${label}.${key} must be a finite number >= 0.`);
    }

    cleaned[key] = num;
  });

  return cleaned;
}

function validateRelativeTrustedPath(path, label) {
  if (!path) return path;

  const cleaned = String(path).trim();

  if (!cleaned) {
    return "";
  }

  if (cleaned.includes("..")) {
    throw new Error(`${label} must not contain path traversal.`);
  }

  if (cleaned.startsWith("/") || /^[A-Za-z]:/i.test(cleaned)) {
    throw new Error(`${label} must be a relative trusted path.`);
  }

  return cleaned;
}

function validateDemandSegments(segments) {
  if (!Array.isArray(segments)) {
    throw new Error("demand_segments must be a JSON array.");
  }

  segments.forEach((segment, index) => {
    if (
      segment === null ||
      typeof segment !== "object" ||
      Array.isArray(segment)
    ) {
      throw new Error(`demand_segments[${index}] must be a JSON object.`);
    }

    const startTick = Number(segment.start_tick);
    const endTick = Number(segment.end_tick);
    const rate = Number(segment.rate);

    if (!Number.isFinite(startTick) || startTick < 0) {
      throw new Error(`demand_segments[${index}].start_tick must be a finite number >= 0.`);
    }

    if (!Number.isFinite(endTick) || endTick <= startTick) {
      throw new Error(`demand_segments[${index}].end_tick must be greater than start_tick.`);
    }

    if (!Number.isFinite(rate) || rate < 0) {
      throw new Error(`demand_segments[${index}].rate must be a finite number >= 0.`);
    }

    segment.start_tick = startTick;
    segment.end_tick = endTick;
    segment.rate = rate;
  });

  return segments;
}

function validateDemandEvents(events) {
  if (!Array.isArray(events)) {
    throw new Error("demand_events must be a JSON array.");
  }

  events.forEach((event, index) => {
    if (
      event === null ||
      typeof event !== "object" ||
      Array.isArray(event)
    ) {
      throw new Error(`demand_events[${index}] must be a JSON object.`);
    }

    if (event.tick != null) {
      const tick = Number(event.tick);

      if (!Number.isFinite(tick) || tick < 0) {
        throw new Error(`demand_events[${index}].tick must be a finite number >= 0.`);
      }

      event.tick = tick;
    }
  });

  return events;
}

// =====================================================================
// Experiment config reader
// =====================================================================

function readExperimentConfig() {
  const stopMode = safeString(formValue("cfg-stop-mode")) || "workload";

  const demandMode = safeString(formValue("cfg-demand-mode")) || "legacy";
  const layoutPreset = safeString(formValue("cfg-layout-preset")) || "default";

  const demandModes = [
    "legacy",
    "uniform",
    "rate_schedule",
    "csv_orders"
  ];

  const layoutPresets = [
    "default",
    "high_density",
    "one_way_aisles"
  ];

  if (!demandModes.includes(demandMode)) {
    throw new Error("Unsupported demand_mode.");
  }

  if (!layoutPresets.includes(layoutPreset)) {
    throw new Error("Unsupported layout_preset.");
  }

  const numRobots = formNumber("cfg-num-robots", 6);
  const maxTicks = formNumber("cfg-max-ticks", 100000);
  const tickInterval = formNumber("cfg-tick-interval", 0.3);

  if (!Number.isFinite(numRobots) || numRobots < 1) {
    throw new Error("num_robots must be >= 1.");
  }

  if (!Number.isFinite(maxTicks) || maxTicks < 1) {
    throw new Error("max_ticks must be >= 1.");
  }

  if (!Number.isFinite(tickInterval) || tickInterval <= 0) {
    throw new Error("tick_interval must be > 0.");
  }

  const wantsTargetTasks =
    stopMode === "workload" || stopMode === "target_tasks";

  const targetTasks = wantsTargetTasks
    ? formNumberOrNull("cfg-target-tasks")
    : null;

  if (wantsTargetTasks && (!Number.isFinite(targetTasks) || targetTasks < 1)) {
    throw new Error("target_tasks must be >= 1 for workload stopping.");
  }

  const failureEnabled = formBool("cfg-failure-enabled");
  const mtbfTicks = formNumber("cfg-mtbf-ticks", 0);
  const mttrTicks = formNumber("cfg-mttr-ticks", 25);

  if (failureEnabled && (!Number.isFinite(mtbfTicks) || mtbfTicks <= 0)) {
    throw new Error("mtbf_ticks must be > 0 when failures are enabled.");
  }

  let demandRatePerTick = 0.0;
  let demandTaskWeights = {};
  let demandSegments = [];
  let demandCsvPath = null;
  let demandEvents = [];

  if (demandMode === "uniform") {
    demandRatePerTick = formNumber("cfg-demand-rate-per-tick", 0);

    if (!Number.isFinite(demandRatePerTick) || demandRatePerTick < 0) {
      throw new Error("demand_rate_per_tick must be >= 0.");
    }

    demandTaskWeights = validateNonNegativeNumberObject(
      parseSetupJsonObject("cfg-demand-task-weights", {}),
      "demand_task_weights"
    );
  }

  if (demandMode === "rate_schedule") {
    demandSegments = validateDemandSegments(
      parseSetupJsonArray("cfg-demand-segments", [])
    );

    if (demandSegments.length === 0) {
      throw new Error("rate_schedule requires at least one demand segment.");
    }
  }

  if (demandMode === "csv_orders") {
    demandCsvPath = validateRelativeTrustedPath(
      safeString(formValue("cfg-demand-csv-file")),
      "demand_csv_path"
    );

    if (!demandCsvPath) {
      throw new Error(
        "csv_orders requires demand_csv_path. Managed file selection/upload is not implemented yet."
      );
    }

    demandEvents = validateDemandEvents(
      parseSetupJsonArray("cfg-demand-events", [])
    );
  }

  const layoutFile = validateRelativeTrustedPath(
    safeString(formValue("cfg-layout-file")) || null,
    "layout_file"
  );

  return {
    display_name: safeString(formValue("cfg-display-name")),
    seed: formNumber("cfg-seed", 42),
    num_robots: numRobots,
    stop_mode: stopMode,
    target_tasks: targetTasks,
    max_ticks: maxTicks,
    tick_interval: tickInterval,
    fast_mode: formBool("cfg-fast-mode"),
    blocked_replan_seconds: formNumber("cfg-blocked-replan-seconds", 0.7),
    replan_cooldown_ticks: formNumber("cfg-replan-cooldown-ticks", 7),
    path_planner: safeString(formValue("cfg-path-planner")) || "bfs",
    scheduler: safeString(formValue("cfg-scheduler")) || "baseline",
    conflict_manager: safeString(formValue("cfg-conflict-manager")) || "local_yield",
    battery_capacity: formNumber("cfg-battery-capacity", 100),
    empty_move_energy: formNumber("cfg-empty-move-energy", 0.35),
    loaded_move_energy: formNumber("cfg-loaded-move-energy", 0.5),
    critical_battery: formNumber("cfg-critical-battery", 15),
    opportunistic_charge_threshold: formNumber("cfg-opportunistic-charge-threshold", 30),
    charger_capacity: formNumber("cfg-charger-capacity", 4),
    charge_duration_ticks: formNumber("cfg-charge-duration-ticks", 10),
    failure_enabled: failureEnabled,
    mtbf_ticks: mtbfTicks,
    mttr_ticks: mttrTicks,

    demand_mode: demandMode,
    demand_rate_per_tick: demandRatePerTick,
    demand_task_weights: demandTaskWeights,
    demand_segments: demandSegments,
    demand_csv_path: demandCsvPath,
    demand_events: demandEvents,
    layout_preset: layoutPreset,
    layout_file: layoutFile
  };
}

// =====================================================================
// Experiment lifecycle
// =====================================================================

async function startExperiment() {
  try {
    const config = readExperimentConfig();

    const res = await fetch("/api/experiment/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config)
    });

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.error || "Failed to start experiment.");
    }

    activeRunId = data.runId;
    robotElements = {};
    previousWarehouseKey = null;

    showView(config.fast_mode ? "fast" : "run");

    if (typeof updateResultsDecisionActionsVisibility === "function") {
      updateResultsDecisionActionsVisibility();
    }
  } catch (error) {
    alert(error.message);
  }
}

async function showResults() {
  try {
    const res = await fetch("/api/experiment/summary");
    if (!res.ok) return;

    renderSummary(await res.json());
    showView("results");

    if (typeof updateResultsDecisionActionsVisibility === "function") {
      updateResultsDecisionActionsVisibility();
    }
  } catch (error) {
    console.error(error);
  }
}

function renderSummary(summary) {
  if (!resultSummaryEl) return;

  resultSummaryEl.innerHTML = "";

  const entries = Object.entries(summary || {}).filter(
    ([, value]) => typeof value !== "object"
  );

  if (entries.length === 0) {
    resultSummaryEl.textContent = "No summary available.";
    return;
  }

  entries.forEach(([key, value]) => {
    resultSummaryEl.appendChild(createMetricCard(key, formatValue(value), ""));
  });
}

async function openRunSummary(runId) {
  try {
    const res = await fetch(`/api/runs/${encodeURIComponent(runId)}/summary`);
    const payload = await res.json();

    if (!res.ok) {
      throw new Error(payload.error || "Run not found.");
    }

    activeRunId = runId;

    renderSummary(payload.summary || {});
    showView("results");

    if (typeof updateResultsDecisionActionsVisibility === "function") {
      updateResultsDecisionActionsVisibility();
    }
  } catch (error) {
    alert(error.message);
  }
}

// =====================================================================
// Results decision actions
// =====================================================================

function updateResultsDecisionActionsVisibility() {
  const cardEl = document.getElementById("results-decision-actions-card");
  if (!cardEl) return;

  const hasRun =
    typeof activeRunId !== "undefined" &&
    activeRunId !== null &&
    String(activeRunId).trim() !== "";

  cardEl.hidden = !hasRun;
}

// =====================================================================
// Experiments list
// =====================================================================

function createRunActionButton(label, action, runId) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.textContent = label;
  btn.dataset.runAction = action;
  btn.dataset.runId = runId;
  return btn;
}

function createRunLinkedActionsGroup(runId) {
  const group = document.createElement("div");
  group.className = "decision-toolbar";

  const actions = [
    ["Cost", "cost"],
    ["Spatial", "spatial"],
    ["Report", "report"],
    ["MC", "monte_carlo"],
    ["Sens", "sensitivity"],
    ["Opt", "optimizer"],
    ["Multi", "multiobjective"]
  ];

  actions.forEach(([label, action]) => {
    group.appendChild(createRunActionButton(label, action, runId));
  });

  return group;
}

async function loadExperiments() {
  if (!experimentListEl) return;

  experimentListEl.innerHTML = "Loading...";

  try {
    const data = await fetch("/api/runs").then(response => response.json());

    experimentListEl.innerHTML = "";

    const runs = data.runs || [];

    if (runs.length === 0) {
      experimentListEl.textContent = "No saved experiments.";
      return;
    }

    runs.forEach(run => {
      const row = document.createElement("div");
      row.className = "experiment-row";

      const config = run.config || {};
      const summary = run.summary || {};
      const displayName = config.display_name || run.run_id;

      const info = document.createElement("div");
      info.className = "experiment-info";

      info.innerHTML =
        `<strong>${escapeHtml(displayName)}</strong><br>` +
        `<small>${escapeHtml(run.run_id)} | robots=${escapeHtml(config.num_robots ?? "?")} | ` +
        `completed=${escapeHtml(summary.tasks_completed ?? "?")} | stop=${escapeHtml(summary.stop_reason || "not finished")}</small>`;

      const actionsGroup = createRunLinkedActionsGroup(run.run_id);

      const btnGroup = document.createElement("div");
      btnGroup.style.display = "flex";
      btnGroup.style.gap = "8px";

      const openBtn = document.createElement("button");
      openBtn.textContent = "Open";

      openBtn.onclick = async () => {
        try {
          const summaryRes = await fetch(
            `/api/runs/${encodeURIComponent(run.run_id)}/summary`
          );

          if (!summaryRes.ok) {
            throw new Error("Could not open run summary.");
          }

          const payload = await summaryRes.json();

          activeRunId = run.run_id;

          renderSummary(payload.summary || {});
          showView("results");

          if (typeof updateResultsDecisionActionsVisibility === "function") {
            updateResultsDecisionActionsVisibility();
          }
        } catch (error) {
          alert(error.message);
        }
      };

      const delBtn = document.createElement("button");
      delBtn.textContent = "Delete";
      delBtn.className = "delete-btn";

      delBtn.onclick = async () => {
        if (!confirm(`Delete "${displayName}"? This cannot be undone.`)) return;

        await fetch(`/api/runs/${encodeURIComponent(run.run_id)}`, {
          method: "DELETE"
        });

        if (activeRunId === run.run_id) {
          activeRunId = null;
        }

        if (typeof updateResultsDecisionActionsVisibility === "function") {
          updateResultsDecisionActionsVisibility();
        }

        loadExperiments();
      };

      btnGroup.append(openBtn, delBtn);
      row.append(info, actionsGroup, btnGroup);

      experimentListEl.appendChild(row);
    });
  } catch (error) {
    experimentListEl.textContent = "Failed to load experiments.";
  }
}

// =====================================================================
// Visualization
// =====================================================================

async function generateVisualization() {
  const runId = document.getElementById("visualization-run-select")?.value;
  const metric = document.getElementById("visualization-metric-select")?.value;

  if (!runId) {
    alert("Select a run.");
    return;
  }

  try {
    let url = `/api/runs/${encodeURIComponent(runId)}/series?max_points=2000`;

    if (metric === "battery_overlay") {
      url += "&columns=average_battery,min_battery,max_battery";
    } else if (metric === "robot_states_stacked") {
      url +=
        "&columns=robots_active,robots_idle,robots_blocked,robots_charging,robots_to_charger,robots_waiting_for_charger,robots_failed";
    } else {
      url += `&columns=${metric}`;
    }

    const data = await fetch(url).then(response => response.json());
    const series = data.series || [];

    if (metric === "battery_overlay") {
      series.forEach((s, index) => {
        s.lineStyle = {
          width: index === 0 ? 3 : 1,
          type: index === 0 ? "solid" : "dashed"
        };
      });

      visualizationChart = renderLineChart(
        "visualization-chart",
        series,
        { smooth: false, existingChart: visualizationChart }
      );
    } else if (metric === "robot_states_stacked") {
      visualizationChart = renderStackedAreaChart("visualization-chart", series);
    } else {
      visualizationChart = renderLineChart(
        "visualization-chart",
        series,
        { existingChart: visualizationChart }
      );
    }
  } catch (error) {
    alert("Failed to load visualization.");
  }
}

// =====================================================================
// Analysis
// =====================================================================

async function generateAnalysis() {
  const runId = document.getElementById("analysis-run-select")?.value;
  const statsEl = document.getElementById("analysis-stats");
  const chartsEl = document.getElementById("analysis-charts");

  if (!runId) {
    alert("Select a run.");
    return;
  }

  analysisCharts.forEach(chart => chart.dispose());
  analysisCharts = [];

  if (statsEl) statsEl.innerHTML = "";
  if (chartsEl) chartsEl.innerHTML = "";

  try {
    const data = await fetch(
      `/api/runs/${encodeURIComponent(runId)}/distributions?bins=50`
    ).then(response => response.json());

    Object.entries(data.stats || {}).forEach(([name, vals]) => {
      if (!statsEl) return;

      statsEl.appendChild(
        createMetricCard(
          name,
          formatValue(vals.mean),
          `median=${formatValue(vals.median)} p95=${formatValue(vals.p95)}`
        )
      );
    });

    const histograms = data.histograms || {};

    const createChartBox = title => {
      if (!chartsEl) return null;

      const wrap = document.createElement("div");
      wrap.className = "analysis-chart-wrapper";
      wrap.innerHTML = `<h4>${escapeHtml(title)}</h4><div class="analysis-chart"></div>`;

      chartsEl.appendChild(wrap);
      return wrap.querySelector(".analysis-chart");
    };

    if (histograms.task_waiting_time) {
      const el = createChartBox("Task Waiting Time");
      if (el) renderHistogramChart(el, histograms.task_waiting_time);
    }

    if (histograms.task_cycle_time) {
      const el = createChartBox("Task Cycle Time");
      if (el) renderHistogramChart(el, histograms.task_cycle_time);
    }

    if (histograms.robot_blocked_episode_ticks) {
      const el = createChartBox("Robot Blocked Duration");
      if (el) renderHistogramChart(el, histograms.robot_blocked_episode_ticks);
    }

    if (Array.isArray(data.robot_utilization) && data.robot_utilization.length > 0) {
      const el = createChartBox("Robot Utilization");

      if (el) {
        const chart = echarts.init(el, "dark");
        const opt = getBaseChartOption();

        opt.xAxis = {
          type: "category",
          data: data.robot_utilization.map(row => row.robot_id)
        };

        opt.yAxis = {
          type: "value",
          max: 1.0
        };

        opt.dataZoom = [];

        opt.series = [
          {
            type: "bar",
            data: data.robot_utilization.map(row => row.utilization)
          }
        ];

        chart.setOption(opt);
        analysisCharts.push(chart);
      }
    }
  } catch (error) {
    alert("Failed to load analysis.");
  }
}

// =====================================================================
// Compare
// =====================================================================

async function generateComparison() {
  const runIds = compareMultiSelect ? compareMultiSelect.getSelected() : [];
  const metric = document.getElementById("compare-metric-select")?.value;
  const chartType = document.getElementById("compare-chart-type")?.value;

  if (!runIds || runIds.length === 0) {
    alert("Select at least one run.");
    return;
  }

  try {
    const url =
      `/api/runs/compare/series?runs=${encodeURIComponent(runIds.join(","))}` +
      `&column=${metric}&max_points=2000`;

    const data = await fetch(url).then(response => response.json());

    if (chartType === "bar") {
      const categories = data.runs.map(run => run.run_id);

      const values = data.runs.map(run => {
        const points = run.points || [];
        return points.length > 0 ? points[points.length - 1][1] : 0;
      });

      compareChart = renderBarChart("compare-chart", categories, values, metric);
    } else {
      const series = data.runs.map(run => ({
        name: run.run_id,
        points: run.points
      }));

      compareChart = renderLineChart(
        "compare-chart",
        series,
        { existingChart: compareChart }
      );
    }
  } catch (error) {
    alert("Failed to load comparison.");
  }
}