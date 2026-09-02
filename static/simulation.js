const CELL_SIZE = 32;
const POLL_INTERVAL_MS = 300;
const CHART_COLORS = [
    '#E69F00', '#56B4E9', '#009E73', '#F0E442',
    '#0072B2', '#D55E00', '#CC79A7', '#999999'
];

const warehouseEl = document.getElementById("warehouse");
const dashboardGridEl = document.getElementById("dashboard-grid");
const taskListEl = document.getElementById("task-list");
const simulationStateEl = document.getElementById("simulation-state");
const resultSummaryEl = document.getElementById("result-summary");
const experimentListEl = document.getElementById("experiment-list");

const views = {};
let currentView = "setup";
let activeRunId = null;
let robotElements = {};
let previousWarehouseKey = null;
let updateInProgress = false;
let visualizationChart = null;
let compareChart = null;
let analysisCharts = [];
let compareMultiSelect = null;

// =====================================================================
// MultiSelect
// =====================================================================
class MultiSelect {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.options = [];
        this.selected = new Set();
        this.isOpen = false;
        this.render();
    }

    render() {
        this.container.innerHTML = `
            <div class="multi-select-trigger"></div>
            <div class="multi-select-dropdown"></div>
        `;
        this.trigger = this.container.querySelector('.multi-select-trigger');
        this.dropdown = this.container.querySelector('.multi-select-dropdown');
        this.trigger.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggle();
        });
        document.addEventListener('click', (e) => {
            if (!this.container.contains(e.target)) this.close();
        });
        this.updateDisplay();
    }

    toggle() { this.isOpen ? this.close() : this.open(); }
    open() { this.isOpen = true; this.dropdown.classList.add('open'); this.renderOptions(); }
    close() { this.isOpen = false; this.dropdown.classList.remove('open'); }

    renderOptions() {
        this.dropdown.innerHTML = this.options.map(opt => `
            <div class="multi-select-option ${this.selected.has(opt.value) ? 'selected' : ''}" data-value="${opt.value}">
                <input type="checkbox" ${this.selected.has(opt.value) ? 'checked' : ''} onclick="event.stopPropagation()">
                <span>${opt.label}</span>
            </div>
        `).join('');
        this.dropdown.querySelectorAll('.multi-select-option').forEach(el => {
            el.addEventListener('click', () => {
                const val = el.dataset.value;
                this.selected.has(val) ? this.selected.delete(val) : this.selected.add(val);
                this.renderOptions();
                this.updateDisplay();
            });
        });
    }

    updateDisplay() {
        const tags = Array.from(this.selected).map(val => {
            const opt = this.options.find(o => o.value === val);
            return `<span class="multi-select-tag">${opt?.label || val}<span class="multi-select-tag-remove" data-value="${val}">×</span></span>`;
        }).join('');
        this.trigger.innerHTML = tags || '<span style="color: var(--text-secondary);">Select runs...</span>';
        this.trigger.querySelectorAll('.multi-select-tag-remove').forEach(el => {
            el.addEventListener('click', (e) => {
                e.stopPropagation();
                this.selected.delete(el.dataset.value);
                this.renderOptions();
                this.updateDisplay();
            });
        });
    }

    setOptions(options) { this.options = options; }
    getSelected() { return Array.from(this.selected); }
    clear() { this.selected.clear(); this.updateDisplay(); }
}

// =====================================================================
// Chart helpers
// =====================================================================
function getBaseChartOption() {
    return {
        backgroundColor: 'transparent',
        textStyle: { color: '#eaeaea' },
        tooltip: {
            trigger: 'axis',
            backgroundColor: '#16213e',
            borderColor: '#2d3748',
            textStyle: { color: '#eaeaea' }
        },
        legend: { top: 0, textStyle: { color: '#eaeaea' } },
        grid: { left: 60, right: 30, top: 50, bottom: 80 },
        xAxis: {
            type: 'value', name: 'Tick',
            axisLine: { lineStyle: { color: '#2d3748' } },
            axisLabel: { color: '#a8a8a8' }
        },
        yAxis: {
            type: 'value',
            axisLine: { lineStyle: { color: '#2d3748' } },
            axisLabel: { color: '#a8a8a8' },
            splitLine: { lineStyle: { color: '#2d3748' } }
        },
        dataZoom: [
            { type: 'inside' },
            { type: 'slider', height: 20, bottom: 10, borderColor: '#2d3748', fillerColor: 'rgba(245,158,11,0.2)' }
        ],
        color: CHART_COLORS
    };
}

function renderLineChart(containerId, series, options = {}) {
    const el = document.getElementById(containerId);
    if (!el || typeof echarts === 'undefined') return null;
    if (options.existingChart) options.existingChart.dispose();
    const chart = echarts.init(el, 'dark');
    const opt = getBaseChartOption();
    opt.series = series.map(item => ({
        name: item.name,
        type: 'line',
        showSymbol: false,
        data: item.points,
        smooth: options.smooth !== false,
        lineStyle: item.lineStyle || { width: 2 }
    }));
    chart.setOption(opt);
    return chart;
}

function renderStackedAreaChart(containerId, series) {
    const el = document.getElementById(containerId);
    if (!el || typeof echarts === 'undefined') return null;
    if (visualizationChart) visualizationChart.dispose();
    const chart = echarts.init(el, 'dark');
    const opt = getBaseChartOption();
    opt.series = series.map(item => ({
        name: item.name,
        type: 'line',
        stack: 'total',
        areaStyle: { opacity: 0.6 },
        showSymbol: false,
        data: item.points,
        smooth: true,
        emphasis: { focus: 'series' }
    }));
    chart.setOption(opt);
    return chart;
}

function renderBarChart(containerId, categories, values, title) {
    const el = document.getElementById(containerId);
    if (!el || typeof echarts === 'undefined') return null;
    if (compareChart) compareChart.dispose();
    const chart = echarts.init(el, 'dark');
    const opt = getBaseChartOption();
    opt.xAxis = { type: 'category', data: categories, axisLabel: { color: '#a8a8a8', rotate: 30 } };
    opt.yAxis = { type: 'value', axisLine: { lineStyle: { color: '#2d3748' } }, splitLine: { lineStyle: { color: '#2d3748' } } };
    opt.dataZoom = [];
    opt.series = [{ name: title, type: 'bar', data: values, itemStyle: { borderRadius: [4, 4, 0, 0] } }];
    chart.setOption(opt);
    return chart;
}

function renderHistogramChart(containerEl, histogram) {
    if (!containerEl || typeof echarts === 'undefined') return;
    const chart = echarts.init(containerEl, 'dark');
    const opt = getBaseChartOption();
    opt.xAxis = { type: 'category', data: (histogram.bin_centers || []).map(v => Number(v).toFixed(1)), axisLabel: { color: '#a8a8a8' } };
    opt.yAxis = { type: 'value', axisLine: { lineStyle: { color: '#2d3748' } }, splitLine: { lineStyle: { color: '#2d3748' } } };
    opt.dataZoom = [];
    opt.series = [{ type: 'bar', data: histogram.counts || [], itemStyle: { color: '#E69F00' } }];
    chart.setOption(opt);
    analysisCharts.push(chart);
}

// =====================================================================
// Views / helpers
// =====================================================================
function initViews() {
    ["setup", "run", "fast", "results", "experiments", "visualization", "analysis", "compare"].forEach(name => {
        views[name] = document.getElementById(`view-${name}`);
    });
}

function showView(name) {
    currentView = name;
    Object.entries(views).forEach(([key, el]) => { if (el) el.hidden = key !== name; });
}

function on(id, eventName, handler) {
    const el = document.getElementById(id);
    if (el) el.addEventListener(eventName, handler);
}

function safeString(value) { return value == null ? "" : String(value).trim(); }
function toNumber(value, fallback = 0) { const p = Number(value); return Number.isFinite(p) ? p : fallback; }
function formatValue(value) {
    if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(4);
    return value == null ? "-" : String(value);
}
function formValue(id) { const el = document.getElementById(id); return el ? el.value : ""; }
function formNumber(id, fallback = 0) { return toNumber(formValue(id), fallback); }
function formNumberOrNull(id) { const raw = formValue(id); if (raw === "") return null; return toNumber(raw, 0); }
function formBool(id) { const el = document.getElementById(id); return el ? el.checked : false; }

// =====================================================================
// Polling
// =====================================================================
async function refresh() {
    if (updateInProgress) return;
    updateInProgress = true;
    try {
        const state = await fetch("/api/state").then(r => r.json());
        if (currentView === "run") {
            render(state);
        }
        if (currentView === "fast") {
            const el = document.getElementById("fast-status");
            if (el) {
                el.textContent =
                    `Tick ${state.tick} | ` +
                    `Completed ${state.metrics?.tasksCompleted ?? 0}`;
            }
        }
        const finished = state.experiment?.finished;
        if ((currentView === "run" || currentView === "fast") && finished) {
            await showResults();
        }
    } catch (e) {
        console.error(e);
    } finally {
        updateInProgress = false;
    }
}

// =====================================================================
// Experiment lifecycle
// =====================================================================
function readExperimentConfig() {
    const stopMode = safeString(formValue("cfg-stop-mode")) || "workload";
    return {
        display_name: safeString(formValue("cfg-display-name")),
        seed: formNumber("cfg-seed", 42),
        num_robots: formNumber("cfg-num-robots", 6),
        stop_mode: stopMode,
        target_tasks: stopMode === "workload" ? formNumberOrNull("cfg-target-tasks") : null,
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
        mttr_ticks: formNumber("cfg-mttr-ticks", 25),
    };
}

async function startExperiment() {
    try {
        const config = readExperimentConfig();
        const res = await fetch("/api/experiment/start", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(config),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Failed to start");
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
    entries.forEach(([k, v]) => resultSummaryEl.appendChild(createMetricCard(k, formatValue(v), "")));
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
                `<strong>${displayName}</strong><br>` +
                `<small>${run.run_id} | robots=${config.num_robots || '?'} | ` +
                `completed=${summary.tasks_completed || '?'} | stop=${summary.stop_reason || 'not finished'}</small>`;
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
        experimentListEl.textContent = "Failed to load.";
    }
}

async function populateRunSelects() {
    try {
        const data = await fetch("/api/runs").then(r => r.json());
        const runs = data.runs || [];
        const fillSelect = (id) => {
            const sel = document.getElementById(id);
            if (!sel) return;
            sel.innerHTML = "";
            if (runs.length === 0) { sel.innerHTML = '<option value="">No saved runs</option>'; return; }
            runs.forEach(r => {
                const opt = document.createElement("option");
                opt.value = r.run_id;
                opt.textContent = `${r.config?.display_name || r.run_id} (${r.summary?.tasks_completed || 0} tasks)`;
                sel.appendChild(opt);
            });
        };
        fillSelect("visualization-run-select");
        fillSelect("analysis-run-select");
        if (compareMultiSelect) {
            compareMultiSelect.setOptions(runs.map(r => ({
                value: r.run_id,
                label: r.config?.display_name || r.run_id
            })));
        }
    } catch (e) {
        console.error(e);
    }
}

// =====================================================================
// Visualization / Analysis / Compare
// =====================================================================
async function generateVisualization() {
    const runId = document.getElementById("visualization-run-select").value;
    const metric = document.getElementById("visualization-metric-select").value;
    if (!runId) return alert("Select a run.");
    try {
        let url = `/api/runs/${encodeURIComponent(runId)}/series?max_points=2000`;
        if (metric === "battery_overlay") {
            url += "&columns=average_battery,min_battery,max_battery";
        } else if (metric === "robot_states_stacked") {
            url += "&columns=robots_active,robots_idle,robots_blocked,robots_charging,robots_to_charger,robots_waiting_for_charger,robots_failed";
        } else {
            url += `&columns=${metric}`;
        }
        const data = await fetch(url).then(r => r.json());
        const series = data.series || [];
        if (metric === "battery_overlay") {
            series.forEach((s, i) => {
                s.lineStyle = { width: i === 0 ? 3 : 1, type: i === 0 ? 'solid' : 'dashed' };
            });
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
            statsEl.appendChild(createMetricCard(
                name,
                formatValue(vals.mean),
                `median=${formatValue(vals.median)} p95=${formatValue(vals.p95)}`
            ));
        });
        const hists = data.histograms || {};
        const createChartBox = (title) => {
            const wrap = document.createElement("div");
            wrap.className = "analysis-chart-wrapper";
            wrap.innerHTML = `<h4>${title}</h4><div class="analysis-chart"></div>`;
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
            const values = data.runs.map(r => {
                const pts = r.points || [];
                return pts.length > 0 ? pts[pts.length - 1][1] : 0;
            });
            compareChart = renderBarChart("compare-chart", categories, values, metric);
        } else {
            const series = data.runs.map(r => ({ name: r.run_id, points: r.points }));
            compareChart = renderLineChart("compare-chart", series, { existingChart: compareChart });
        }
    } catch (e) {
        alert("Failed to load comparison.");
    }
}

// =====================================================================
// Warehouse rendering
// =====================================================================
function staticWarehouseKey(warehouse) {
    return JSON.stringify({
        width: warehouse?.width ?? 0,
        height: warehouse?.height ?? 0,
        layout: warehouse?.layout ?? [],
        racks: warehouse?.racks ?? {},
    });
}

function render(state) {
    if (!warehouseEl) return;
    const warehouse = state.warehouse || {};
    const warehouseKey = staticWarehouseKey(warehouse);
    if (warehouseKey !== previousWarehouseKey) {
        buildStaticLayer(warehouse);
        previousWarehouseKey = warehouseKey;
    }
    updateRobots(state.robots || [], state.tasks || []);
    updateTaskHighlights(state);
    updateSidePanel(state);
    const exp = state.experiment || {};
    if (exp.active) {
        simulationStateEl.textContent = state.paused ? `Paused | Tick ${state.tick}` : `Tick ${state.tick}`;
    } else if (exp.finished) {
        simulationStateEl.textContent = `Finished | Tick ${state.tick} | ${exp.stopReason || ""}`;
    } else {
        simulationStateEl.textContent = state.paused ? "Paused" : `Tick ${state.tick}`;
    }
}

function buildStaticLayer(warehouse) {
    warehouseEl.innerHTML = "";
    warehouseEl.style.width = `${toNumber(warehouse?.width) * CELL_SIZE}px`;
    warehouseEl.style.height = `${toNumber(warehouse?.height) * CELL_SIZE}px`;
    (warehouse?.layout || []).forEach((row, y) =>
        row.forEach((cell, x) => addCell(x, y, safeString(cell).toLowerCase()))
    );
    Object.entries(warehouse?.racks || {}).forEach(([rack, [x, y]]) => {
        const label = document.createElement("div");
        label.className = "rack-label";
        label.textContent = rack;
        label.style.left = `${(toNumber(x) + 0.5) * CELL_SIZE}px`;
        label.style.top = `${(toNumber(y) + 0.5) * CELL_SIZE}px`;
        warehouseEl.appendChild(label);
    });
}

function addCell(x, y, className) {
    const cell = document.createElement("div");
    cell.className = `tile ${className}`;
    cell.dataset.x = x;
    cell.dataset.y = y;
    cell.style.left = `${x * CELL_SIZE}px`;
    cell.style.top = `${y * CELL_SIZE}px`;
    cell.style.width = `${CELL_SIZE}px`;
    cell.style.height = `${CELL_SIZE}px`;
    warehouseEl.appendChild(cell);
}

function updateRobots(robots, tasks) {
    const seen = new Set();
    const tasksById = new Map(tasks.map(t => [t.id, t]));
    robots.forEach(robot => {
        seen.add(robot.id);
        let el = robotElements[robot.id];
        if (!el) {
            el = document.createElement("div");
            el.className = "robot";
            warehouseEl.appendChild(el);
            robotElements[robot.id] = el;
        }
        el.style.backgroundColor = safeString(robot.color) || "#888";
        el.style.left = `${toNumber(robot.x) * CELL_SIZE}px`;
        el.style.top = `${toNumber(robot.y) * CELL_SIZE}px`;
        el.classList.toggle("idle", safeString(robot.status) === "Idle");
        el.classList.remove(
            "has-task", "task-putaway", "task-pick", "task-pack", "task-ship",
            "low-battery", "to-charger", "waiting-for-charger", "charging", "failed"
        );
        const mode = safeString(robot.mode);
        const battery = typeof robot.battery === "number" ? robot.battery : null;
        if (mode === "To charger") el.classList.add("to-charger");
        else if (mode === "Waiting for charger") el.classList.add("waiting-for-charger");
        else if (mode === "Charging") el.classList.add("charging");
        else if (mode === "Failed" || mode === "Repairing") el.classList.add("failed");
        if (battery !== null && battery <= 20) el.classList.add("low-battery");
        const task = robot.currentTaskId ? tasksById.get(robot.currentTaskId) : null;
        const batteryText = battery !== null ? ` | battery ${battery.toFixed(1)}` : "";
        const modeText = mode && mode !== "Idle" && mode !== "Moving" ? ` | ${mode}` : "";
        if (task) {
            el.classList.add("has-task");
            const tt = safeString(task.taskType).toLowerCase();
            if (tt === "putaway") el.classList.add("task-putaway");
            else if (tt === "pick") el.classList.add("task-pick");
            else if (tt === "pack") el.classList.add("task-pack");
            else if (tt === "ship") el.classList.add("task-ship");
            el.title = `${safeString(robot.id)} | ${safeString(task.name)} | ${safeString(task.pickup)} → ${safeString(task.dropoff)}${batteryText}${modeText}`;
        } else {
            el.title = `${safeString(robot.id)} | ${mode || "Idle"}${batteryText}`;
        }
    });
    Object.keys(robotElements).forEach(id => {
        if (!seen.has(id)) {
            robotElements[id].remove();
            delete robotElements[id];
        }
    });
}

function updateTaskHighlights(state) {
    document.querySelectorAll(".task-pickup-active, .task-dropoff-active, .task-pickup-faint, .task-dropoff-faint").forEach(el => {
        el.classList.remove("task-pickup-active", "task-dropoff-active", "task-pickup-faint", "task-dropoff-faint");
    });
    const tasks = state.tasks || [];
    const locs = state.warehouse?.locations || {};
    tasks.filter(t => safeString(t.status) === "Assigned" && t.assignedRobotId).forEach(task => {
        const phase = safeString(task.phase);
        if (phase === "To pickup") {
            highlightLocation(locs, task.pickup, "task-pickup-active");
            highlightLocation(locs, task.dropoff, "task-dropoff-faint");
        } else if (phase === "To dropoff") {
            highlightLocation(locs, task.dropoff, "task-dropoff-active");
        }
    });
    tasks.filter(t => safeString(t.status) === "Interrupted").forEach(task => {
        highlightLocation(locs, task.pickup, "task-pickup-faint");
        highlightLocation(locs, task.dropoff, "task-dropoff-faint");
    });
}

function highlightLocation(locations, name, className) {
    const loc = locations[safeString(name)];
    if (!loc) return;
    addTileClass(loc.cell, className);
    addTileClass(loc.access, className);
}

function addTileClass(coord, className) {
    if (!coord) return;
    const [x, y] = coord;
    const el = document.querySelector(`.tile[data-x="${x}"][data-y="${y}"]`);
    if (el) el.classList.add(className);
}

function updateSidePanel(state) {
    if (!dashboardGridEl || !taskListEl) return;
    const metrics = state.metrics || {};
    const tasks = state.tasks || [];
    dashboardGridEl.innerHTML = "";
    const assignedCount = tasks.filter(t => safeString(t.status) === "Assigned").length;
    const pendingCount = tasks.filter(t => safeString(t.status) === "Pending").length;
    const interruptedCount = tasks.filter(t => safeString(t.status) === "Interrupted").length;
    const avgBatt = toNumber(metrics.averageBatteryPercent, 0);
    const avgChargerWait = toNumber(metrics.averageChargerWaitTicks, 0);
    const cards = [
        ["Generated", metrics.tasksGenerated ?? 0, "total"],
        ["Completed", metrics.tasksCompleted ?? 0, "tasks"],
        ["Active", assignedCount, "robots"],
        ["Pending", pendingCount, "queue"],
        ["Interrupted", interruptedCount, "tasks"],
        ["Throughput", toNumber(metrics.throughputPerTick).toFixed(2), "per tick"],
        ["Avg Cycle", toNumber(metrics.averageTaskCompletionTime).toFixed(1), "ticks"],
        ["Blocked", toNumber(metrics.blockedTimeSeconds).toFixed(1), "secs"],
        ["Replans", metrics.replanningCount ?? 0, "events"],
        ["Battery", avgBatt.toFixed(1), "% avg"],
        ["Charging", metrics.chargingEvents ?? 0, "events"],
        ["Charger Wait", avgChargerWait.toFixed(1), "ticks avg"],
        ["Batt Stops", metrics.batteryTaskInterruptions ?? 0, "interrupts"],
        ["Reassigned", metrics.taskReassignments ?? 0, "tasks"],
        ["Failures", metrics.failedRobotEvents ?? 0, "robots"],
        ["Downtime", toNumber(metrics.failureDowntimeSeconds).toFixed(1), "secs"],
    ];
    cards.forEach(([t, v, d]) => dashboardGridEl.appendChild(createMetricCard(t, v, d)));
    taskListEl.innerHTML = "";
    const activeTasks = tasks.filter(t => ["Pending", "Assigned", "Interrupted"].includes(safeString(t.status)));
    const recentDone = tasks
        .filter(t => ["Completed", "Failed"].includes(safeString(t.status)))
        .sort((a, b) => toNumber(b.completedAt) - toNumber(a.completedAt))
        .slice(0, 5);
    taskListEl.appendChild(Object.assign(document.createElement("h3"), {
        className: "section-header", textContent: `Active Queue (${activeTasks.length})`
    }));
    if (activeTasks.length === 0) {
        taskListEl.appendChild(Object.assign(document.createElement("div"), { className: "empty-msg", textContent: "No active tasks" }));
    } else {
        activeTasks.forEach(t => taskListEl.appendChild(createTaskRow(t)));
    }
    taskListEl.appendChild(Object.assign(document.createElement("h3"), {
        className: "section-header", textContent: `Recent History (${metrics.tasksCompleted ?? 0} completed)`
    }));
    if (recentDone.length === 0) {
        taskListEl.appendChild(Object.assign(document.createElement("div"), { className: "empty-msg", textContent: "No completed tasks yet" }));
    } else {
        recentDone.forEach(t => taskListEl.appendChild(createTaskRow(t, true)));
    }
}

function createTaskRow(task, isHistory = false) {
    const row = document.createElement("div");
    row.className = `task-row ${safeString(task.status).toLowerCase()} ${isHistory ? "history" : ""}`;
    const badge = document.createElement("span");
    badge.className = `task-badge ${safeString(task.taskType).toLowerCase() || "legacy"}`;
    badge.textContent = (safeString(task.taskType) || "?").substring(0, 4);
    const info = document.createElement("div");
    info.className = "task-info";
    info.innerHTML =
        `<div class="task-title">${safeString(task.pickup)} → ${safeString(task.dropoff)}</div>` +
        `<div class="task-sub">${safeString(task.assignedRobotId) || safeString(task.status)} • ${safeString(task.phase)}</div>`;
    row.append(badge, info);
    return row;
}

function createMetricCard(title, value, detail) {
    const card = document.createElement("div");
    card.className = "metric-card";
    card.innerHTML =
        `<div class="metric-title">${title}</div>` +
        `<div class="metric-value">${value}</div>` +
        `<div class="metric-detail">${detail}</div>`;
    return card;
}

// =====================================================================
// Init / listeners
// =====================================================================
initViews();
showView("setup");
compareMultiSelect = new MultiSelect("compare-run-select");

on("start-experiment-btn", "click", startExperiment);
on("pause-btn", "click", async () => { await fetch("/api/pause", { method: "POST" }); refresh(); });
on("resume-btn", "click", async () => { await fetch("/api/resume", { method: "POST" }); refresh(); });
on("reset-btn", "click", async () => {
    await fetch("/api/reset", { method: "POST" });
    activeRunId = null;
    robotElements = {};
    previousWarehouseKey = null;
    showView("setup");
    refresh();
});
on("fast-stop-btn", "click", async () => {
    await fetch("/api/experiment/stop", { method: "POST" });
    refresh();
});

on("nav-setup-btn", "click", () => showView("setup"));
on("nav-run-btn", "click", () => showView("run"));
on("nav-results-btn", "click", () => showView("results"));
on("nav-experiments-btn", "click", () => { loadExperiments(); showView("experiments"); });
on("nav-visualization-btn", "click", () => { populateRunSelects(); showView("visualization"); });
on("nav-analysis-btn", "click", () => { populateRunSelects(); showView("analysis"); });
on("nav-compare-btn", "click", () => { populateRunSelects(); showView("compare"); });

on("run-again-btn", "click", () => showView("setup"));
on("view-experiments-btn", "click", () => { loadExperiments(); showView("experiments"); });
on("view-visualization-btn", "click", () => { populateRunSelects(); showView("visualization"); });
on("view-analysis-btn", "click", () => { populateRunSelects(); showView("analysis"); });
on("back-to-setup-btn", "click", () => showView("setup"));

on("visualization-generate-btn", "click", generateVisualization);
on("analysis-generate-btn", "click", generateAnalysis);
on("compare-generate-btn", "click", generateComparison);

refresh();
setInterval(refresh, POLL_INTERVAL_MS);