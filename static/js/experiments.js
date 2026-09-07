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
        target_tasks: (stopMode === "workload" || stopMode === "target_tasks") ? formNumberOrNull("cfg-target-tasks") : null,
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
        if (!res.ok) throw new Error(data.error || "Failed to start experiment.");
        activeRunId = data.runId;
        robotElements = {};
        previousWarehouseKey = null;
        showView(config.fast_mode ? "fast" : "run");
    } catch (e) {
        alert(e.message);
    }
}

async function showResults() {
    try {
        const res = await fetch("/api/experiment/summary");
        if (!res.ok) return;
        renderSummary(await res.json());
        showView("results");
    } catch (e) {
        console.error(e);
    }
}

function renderSummary(summary) {
    if (!resultSummaryEl) return;
    resultSummaryEl.innerHTML = "";
    const entries = Object.entries(summary || {}).filter(([, v]) => typeof v !== "object");
    if (entries.length === 0) { resultSummaryEl.textContent = "No summary available."; return; }
    entries.forEach(([key, value]) => {
        resultSummaryEl.appendChild(createMetricCard(key, formatValue(value), ""));
    });
}

async function openRunSummary(runId) {
    try {
        const res = await fetch(`/api/runs/${encodeURIComponent(runId)}/summary`);
        const payload = await res.json();
        if (!res.ok) throw new Error(payload.error || "Run not found.");
        activeRunId = runId;
        renderSummary(payload.summary || {});
        showView("results");
    } catch (e) {
        alert(e.message);
    }
}

// =====================================================================
// Experiments list
// =====================================================================

async function loadExperiments() {
    if (!experimentListEl) return;
    experimentListEl.innerHTML = "Loading...";

    try {
        const data = await fetch("/api/runs").then(r => r.json());
        experimentListEl.innerHTML = "";
        const runs = data.runs || [];

        if (runs.length === 0) { experimentListEl.textContent = "No saved experiments."; return; }

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

            const btnGroup = document.createElement("div");
            btnGroup.style.display = "flex";
            btnGroup.style.gap = "8px";

            const openBtn = document.createElement("button");
            openBtn.textContent = "Open";
            openBtn.onclick = async () => {
                const sumRes = await fetch(`/api/runs/${encodeURIComponent(run.run_id)}/summary`);
                if (sumRes.ok) {
                    const payload = await sumRes.json();
                    renderSummary(payload.summary || {});
                    showView("results");
                }
            };

            const delBtn = document.createElement("button");
            delBtn.textContent = "Delete";
            delBtn.className = "delete-btn";
            delBtn.onclick = async () => {
                if (!confirm(`Delete "${displayName}"? This cannot be undone.`)) return;
                await fetch(`/api/runs/${encodeURIComponent(run.run_id)}`, { method: "DELETE" });
                loadExperiments();
            };

            btnGroup.append(openBtn, delBtn);
            row.append(info, btnGroup);
            experimentListEl.appendChild(row);
        });
    } catch (e) {
        experimentListEl.textContent = "Failed to load experiments.";
    }
}

// =====================================================================
// Visualization
// =====================================================================

async function generateVisualization() {
    const runId = document.getElementById("visualization-run-select").value;
    const metric = document.getElementById("visualization-metric-select").value;
    if (!runId) return alert("Select a run.");

    try {
        let url = `/api/runs/${encodeURIComponent(runId)}/series?max_points=2000`;
        if (metric === "battery_overlay") url += "&columns=average_battery,min_battery,max_battery";
        else if (metric === "robot_states_stacked") url += "&columns=robots_active,robots_idle,robots_blocked,robots_charging,robots_to_charger,robots_waiting_for_charger,robots_failed";
        else url += `&columns=${metric}`;

        const data = await fetch(url).then(r => r.json());
        const series = data.series || [];

        if (metric === "battery_overlay") {
            series.forEach((s, i) => { s.lineStyle = { width: i === 0 ? 3 : 1, type: i === 0 ? 'solid' : 'dashed' }; });
            visualizationChart = renderLineChart("visualization-chart", series, { smooth: false, existingChart: visualizationChart });
        } else if (metric === "robot_states_stacked") {
            visualizationChart = renderStackedAreaChart("visualization-chart", series);
        } else {
            visualizationChart = renderLineChart("visualization-chart", series, { existingChart: visualizationChart });
        }
    } catch (e) {
        alert("Failed to load visualization.");
    }
}

// =====================================================================
// Analysis
// =====================================================================

async function generateAnalysis() {
    const runId = document.getElementById("analysis-run-select").value;
    const statsEl = document.getElementById("analysis-stats");
    const chartsEl = document.getElementById("analysis-charts");
    if (!runId) return alert("Select a run.");

    analysisCharts.forEach(c => c.dispose());
    analysisCharts = [];
    statsEl.innerHTML = "";
    chartsEl.innerHTML = "";

    try {
        const data = await fetch(`/api/runs/${encodeURIComponent(runId)}/distributions?bins=50`).then(r => r.json());

        Object.entries(data.stats || {}).forEach(([name, vals]) => {
            statsEl.appendChild(createMetricCard(name, formatValue(vals.mean), `median=${formatValue(vals.median)} p95=${formatValue(vals.p95)}`));
        });

        const hists = data.histograms || {};
        const createChartBox = (title) => {
            const wrap = document.createElement("div");
            wrap.className = "analysis-chart-wrapper";
            wrap.innerHTML = `<h4>${escapeHtml(title)}</h4><div class="analysis-chart"></div>`;
            chartsEl.appendChild(wrap);
            return wrap.querySelector('.analysis-chart');
        };

        if (hists.task_waiting_time) renderHistogramChart(createChartBox("Task Waiting Time"), hists.task_waiting_time);
        if (hists.task_cycle_time) renderHistogramChart(createChartBox("Task Cycle Time"), hists.task_cycle_time);
        if (hists.robot_blocked_episode_ticks) renderHistogramChart(createChartBox("Robot Blocked Duration"), hists.robot_blocked_episode_ticks);

        if (Array.isArray(data.robot_utilization) && data.robot_utilization.length > 0) {
            const el = createChartBox("Robot Utilization");
            const chart = echarts.init(el, 'dark');
            const opt = getBaseChartOption();
            opt.xAxis = { type: 'category', data: data.robot_utilization.map(r => r.robot_id) };
            opt.yAxis = { type: 'value', max: 1.0 };
            opt.dataZoom = [];
            opt.series = [{ type: 'bar', data: data.robot_utilization.map(r => r.utilization) }];
            chart.setOption(opt);
            analysisCharts.push(chart);
        }
    } catch (e) {
        alert("Failed to load analysis.");
    }
}

// =====================================================================
// Compare
// =====================================================================

async function generateComparison() {
    const runIds = compareMultiSelect.getSelected();
    const metric = document.getElementById("compare-metric-select").value;
    const chartType = document.getElementById("compare-chart-type").value;
    if (runIds.length === 0) return alert("Select at least one run.");

    try {
        const url = `/api/runs/compare/series?runs=${encodeURIComponent(runIds.join(','))}&column=${metric}&max_points=2000`;
        const data = await fetch(url).then(r => r.json());

        if (chartType === "bar") {
            const categories = data.runs.map(r => r.run_id);
            const values = data.runs.map(r => { const pts = r.points || []; return pts.length > 0 ? pts[pts.length - 1][1] : 0; });
            compareChart = renderBarChart("compare-chart", categories, values, metric);
        } else {
            const series = data.runs.map(r => ({ name: r.run_id, points: r.points }));
            compareChart = renderLineChart("compare-chart", series, { existingChart: compareChart });
        }
    } catch (e) {
        alert("Failed to load comparison.");
    }
}