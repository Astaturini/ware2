// =====================================================================
// Application state, core infrastructure, MultiSelect
// =====================================================================

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
let decisionSubview = "overview";
let jobPollingInterval = null;

// =====================================================================
// MultiSelect
// =====================================================================

class MultiSelect {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.options = [];
        this.selected = new Set();
        this.isOpen = false;
        if (!this.container) return;
        this.render();
    }

    render() {
        this.container.innerHTML = `
            <div class="multi-select-trigger"></div>
            <div class="multi-select-dropdown"></div>
        `;
        this.trigger = this.container.querySelector('.multi-select-trigger');
        this.dropdown = this.container.querySelector('.multi-select-dropdown');
        this.trigger.addEventListener('click', (e) => { e.stopPropagation(); this.toggle(); });
        document.addEventListener('click', (e) => { if (!this.container.contains(e.target)) this.close(); });
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
// View management
// =====================================================================

function initViews() {
    ["setup", "run", "fast", "results", "experiments", "visualization", "analysis", "compare", "decision"]
        .forEach(name => { views[name] = document.getElementById(`view-${name}`); });
}

function showView(name) {
    currentView = name;
    Object.entries(views).forEach(([key, el]) => { if (el) el.hidden = key !== name; });
}

// =====================================================================
// Shared UI builders
// =====================================================================

function createMetricCard(title, value, detail) {
    const card = document.createElement("div");
    card.className = "metric-card";
    card.innerHTML =
        `<div class="metric-title">${escapeHtml(title)}</div>` +
        `<div class="metric-value">${escapeHtml(value)}</div>` +
        `<div class="metric-detail">${escapeHtml(detail)}</div>`;
    return card;
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
        `<div class="task-title">${escapeHtml(task.pickup)} → ${escapeHtml(task.dropoff)}</div>` +
        `<div class="task-sub">${escapeHtml(task.assignedRobotId || task.status)} • ${escapeHtml(task.phase)}</div>`;

    row.append(badge, info);
    return row;
}

// =====================================================================
// Polling
// =====================================================================

async function refresh() {
    if (updateInProgress) return;
    updateInProgress = true;

    try {
        const state = await fetch("/api/state").then(r => r.json());

        if (currentView === "run") render(state);

        if (currentView === "fast") {
            const el = document.getElementById("fast-status");
            if (el) el.textContent = `Tick ${state.tick} | Completed ${state.metrics?.tasksCompleted ?? 0}`;
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
// Run select population
// =====================================================================

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
        fillSelect("spatial-run-select");
        fillSelect("cost-run-select");

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