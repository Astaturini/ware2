// =====================================================================
// Experiment lifecycle, experiments list, visualization, analysis, compare
// =====================================================================

function readExperimentConfig() {
  const stopMode = safeString(formValue("cfg-stop-mode")) || "workload";

  return {
    display_name: safeString(formValue("cfg-display-name")),
    seed: formNumber("cfg-seed", 42),
    num_robots: formNumber("cfg-num-robots", 6),
    stop_mode: stopMode,
    target_tasks:
      stopMode === "workload" || stopMode === "target_tasks"
        ? formNumberOrNull("cfg-target-tasks")
        : null,
    max_ticks: formNumber("cfg-max-ticks", 100000),
    tick_interval: formNumber("cfg-tick-interval", 0.3),
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
    failure_enabled: formBool("cfg-failure-enabled"),
    mtbf_ticks: formNumber("cfg-mtbf-ticks", 0),
    mttr_ticks: formNumber("cfg-mttr-ticks", 25)
  };
}

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