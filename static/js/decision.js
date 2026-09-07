// =====================================================================
// Decision Center: all subviews, job launcher, polling
// =====================================================================

function decisionContainer(name) {
    return document.getElementById(`decision-${name}`);
}

function setDecisionLoading(container) {
    if (!container) return;
    container.innerHTML = `<div class="decision-status loading">Loading…</div>`;
}

function setDecisionError(container, message) {
    if (!container) return;
    container.innerHTML = `<div class="decision-status error">${escapeHtml(message || "Request failed.")}</div>`;
}

function setDecisionEmpty(container, message) {
    if (!container) return;
    container.innerHTML = `<div class="decision-status">${escapeHtml(message || "No data found.")}</div>`;
}

function decisionCard(title, value) {
    return `
        <div class="decision-card">
            <div class="decision-card-title">${escapeHtml(title)}</div>
            <div class="decision-card-value" style="font-size:16px;">${escapeHtml(formatValue(value))}</div>
        </div>
    `;
}

function decisionTableHtml(columns, rows, options = {}) {
    if (!rows.length) return `<div class="decision-status">${escapeHtml(options.emptyMessage || "No rows.")}</div>`;

    const head = columns.map(column => `<th>${escapeHtml(column.label || column.key)}</th>`).join("");
    const body = rows.map(row => {
        const cells = columns.map(column => {
            let html;
            if (options.linkRunId && column.key === "run_id" && row.run_id != null) {
                html = `<button data-open-run="${escapeHtml(row.run_id)}">${escapeHtml(row.run_id)}</button>`;
            } else if (column.render) {
                html = column.render(row);
            } else {
                html = escapeHtml(formatValue(row[column.key]));
            }
            return `<td>${html}</td>`;
        }).join("");
        return `<tr>${cells}</tr>`;
    }).join("");

    return `
        <div class="decision-table-wrapper">
            <table class="decision-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>
        </div>
    `;
}

function renderDecisionTable(container, columns, rows, emptyMessage = "No rows.") {
    if (!container) return;
    container.innerHTML = decisionTableHtml(columns, rows, { emptyMessage });
}

function renderRowsTable(container, rows, options = {}) {
    if (!container) return;
    let prepared = rows || [];
    if (options.flatten) prepared = prepared.map(flattenRow);
    if (!prepared.length) { setDecisionEmpty(container, options.emptyMessage || "No rows."); return; }
    const columns = deriveColumns(prepared[0], options.preferredKeys || []);
    container.innerHTML = decisionTableHtml(columns, prepared, options);
    if (options.linkRunId) {
        container.onclick = (event) => {
            const runBtn = event.target.closest("[data-open-run]");
            if (runBtn) openRunSummary(runBtn.dataset.openRun);
        };
    }
}

function paginationControls(page, pageSize, totalRows) {
    if (totalRows <= pageSize) return "";
    const totalPages = Math.max(1, Math.ceil(totalRows / pageSize));
    return `
        <div class="decision-toolbar">
            <button class="pg-prev" ${page <= 1 ? "disabled" : ""}>Previous</button>
            <div>Page ${escapeHtml(page)} of ${escapeHtml(totalPages)} • ${escapeHtml(totalRows)} rows</div>
            <button class="pg-next" ${page >= totalPages ? "disabled" : ""}>Next</button>
        </div>
    `;
}

async function renderPaginatedDynamicTable(container, urlBuilder, options = {}) {
    if (!container) return;
    let page = 1;
    const pageSize = options.pageSize || 50;
    let totalPages = 1;
    let columns = null;

    async function load() {
        setDecisionLoading(container);
        try {
            const data = await decisionFetchJson(urlBuilder(page, pageSize));
            let rows = data.rows || [];
            const totalRows = data.total_rows ?? rows.length;
            totalPages = Math.max(1, Math.ceil(totalRows / pageSize));
            if (options.flatten) rows = rows.map(flattenRow);
            if (!columns && rows.length) columns = deriveColumns(rows[0], options.preferredKeys || []);
            if (!columns) { setDecisionEmpty(container, options.emptyMessage || "No rows."); return; }

            container.innerHTML = decisionTableHtml(columns, rows, options) + paginationControls(page, pageSize, totalRows);

            container.onclick = (event) => {
                if (event.target.closest(".pg-prev:not([disabled])")) { page = Math.max(1, page - 1); load(); return; }
                if (event.target.closest(".pg-next:not([disabled])")) { page = Math.min(totalPages, page + 1); load(); return; }
                if (options.linkRunId) {
                    const runBtn = event.target.closest("[data-open-run]");
                    if (runBtn) openRunSummary(runBtn.dataset.openRun);
                }
            };
        } catch (e) {
            setDecisionError(container, e.message);
        }
    }

    await load();
}

function renderObjectTable(container, obj, keyLabel = "Field", valueLabel = "Value") {
    const rows = Object.entries(obj || {}).map(([key, value]) => ({
        key, value: typeof value === "object" && value !== null ? JSON.stringify(value) : value
    }));
    renderDecisionTable(container, [{ key: "key", label: keyLabel }, { key: "value", label: valueLabel }], rows, "No data.");
}

function renderErrorsTable(container, errors) {
    const rows = (errors || []).map(error =>
        typeof error === "object" && error !== null ? { error: JSON.stringify(error) } : { error: String(error) }
    );
    renderDecisionTable(container, [{ key: "error", label: "Error" }], rows, "No errors.");
}

function probabilityBarHtml(value, threshold) {
    const num = Number(value);
    const pct = Number.isFinite(num) ? Math.max(0, Math.min(100, num * 100)) : 0;
    const color = Number.isFinite(num) && threshold != null && num >= threshold ? "var(--success)" : "var(--error)";
    return `
        <div style="min-width:120px;">
            <div style="height:8px; background:rgba(255,255,255,0.08); border-radius:4px; overflow:hidden;">
                <div style="width:${pct}%; height:100%; background:${color};"></div>
            </div>
            <div style="font-size:11px; color:var(--text-secondary); margin-top:2px;">${escapeHtml(formatProbability(value))}</div>
        </div>
    `;
}

function robustPassBadge(value) {
    return value ? '<span class="badge badge-success">Pass</span>' : '<span class="badge badge-error">Fail</span>';
}

// =====================================================================
// Subview state machine
// =====================================================================

function showDecisionSubview(name) {
    decisionSubview = name;
    document.querySelectorAll(".decision-subview").forEach(el => { el.hidden = true; });
    const el = decisionContainer(name);
    if (el) el.hidden = false;

    const loaders = {
        "overview": loadDecisionOverview,
        "studies": loadDecisionStudies,
        "reports": loadDecisionReports,
        "spatial": () => populateRunSelects(),
        "cost": () => populateRunSelects(),
        "monte-carlo": loadDecisionMonteCarlo,
        "sensitivity": loadDecisionSensitivity,
        "optimization": loadDecisionOptimizations,
        "multiobjective": loadDecisionMultiobjective,
        "robustness": loadDecisionRobustness,
        "jobs": loadDecisionJobs
    };

    if (loaders[name]) loaders[name]();
}

function refreshDecision() { showDecisionSubview(decisionSubview); }

// =====================================================================
// Overview
// =====================================================================

async function loadDecisionOverview() {
    const el = decisionContainer("overview");
    if (!el) return;
    setDecisionLoading(el);

    try {
        const data = await decisionFetchJson("/api/decision/overview");
        const cards = [
            ["Studies", data.studies, "studies"], ["Reports", data.reports, "reports"],
            ["Monte Carlo", data.monte_carlo, "monte-carlo"], ["Sensitivity", data.sensitivity, "sensitivity"],
            ["Optimization", data.optimizations, "optimization"], ["Multi-Objective", data.multiobjective, "multiobjective"],
            ["Robustness", data.robustness, "robustness"], ["Jobs", data.jobs, "jobs"]
        ];

        el.innerHTML = `<div class="decision-cards">${cards.map(([title, item, subview]) => `
            <div class="decision-card">
                <div class="decision-card-title">${escapeHtml(title)}</div>
                <div class="decision-card-value">${escapeHtml(item?.count ?? 0)}</div>
                <div class="decision-card-detail">Latest: ${escapeHtml(item?.latest_id || "-")}</div>
                <div class="decision-card-detail">Generated: ${escapeHtml(item?.latest_generated_at || "-")}</div>
                <button data-open-subview="${escapeHtml(subview)}">Open</button>
            </div>
        `).join("")}</div>`;

        el.onclick = (event) => {
            const btn = event.target.closest("[data-open-subview]");
            if (btn) showDecisionSubview(btn.dataset.openSubview);
        };
    } catch (e) { setDecisionError(el, e.message); }
}

// =====================================================================
// Studies
// =====================================================================

async function loadDecisionStudies() {
    const el = decisionContainer("studies");
    if (!el) return;
    setDecisionLoading(el);

    try {
        const data = await decisionFetchJson("/api/decision/studies");
        const studies = data.studies || [];
        if (!studies.length) { setDecisionEmpty(el, "No studies found."); return; }

        renderDecisionTable(el, [
            { key: "study_id", label: "Study ID" },
            { key: "generated_at", label: "Generated" },
            { key: "report_available", label: "Report", render: row => row.report_available ? '<span class="badge badge-success">Available</span>' : '<span class="badge badge-info">None</span>' },
            { key: "action", label: "Action", render: row => `<button data-open-study="${escapeHtml(row.study_id)}">Open</button>` }
        ], studies);

        el.onclick = (event) => {
            const btn = event.target.closest("[data-open-study]");
            if (btn) loadStudyDetail(btn.dataset.openStudy);
        };
    } catch (e) { setDecisionError(el, e.message); }
}

async function loadStudyDetail(studyId) {
    const el = decisionContainer("studies");
    if (!el) return;
    setDecisionLoading(el);

    try {
        const detailData = await decisionFetchJson(`/api/decision/studies/${encodeURIComponent(studyId)}`);
        const resultsData = await decisionFetchJson(`/api/decision/studies/${encodeURIComponent(studyId)}/results?page=1&page_size=50`);
        const rows = resultsData.rows || [];
        let columns = rows.length ? Object.keys(rows[0]) : [];
        if (columns.includes("run_id")) columns = ["run_id", ...columns.filter(c => c !== "run_id")];

        el.innerHTML = `
            <div class="decision-toolbar"><button id="study-back-btn">Back to studies</button></div>
            <div class="decision-cards">
                ${decisionCard("Study ID", detailData.study_id)}
                ${decisionCard("Generated", detailData.generated_at)}
                ${decisionCard("Report", detailData.report_available ? "Available" : "Not available")}
                ${decisionCard("Result rows", resultsData.total_rows ?? rows.length)}
            </div>
            <details><summary>Study config</summary><pre class="json-preview">${escapeHtml(JSON.stringify(detailData.config || {}, null, 2))}</pre></details>
            <h3>Results</h3><div id="study-results-table"></div>
        `;

        const tableContainer = el.querySelector("#study-results-table");
        renderDecisionTable(tableContainer, columns.map(key => ({
            key, label: key,
            render: key === "run_id" ? row => `<button data-open-run="${escapeHtml(row.run_id)}">${escapeHtml(row.run_id)}</button>` : undefined
        })), rows, "No study result rows.");

        tableContainer.onclick = (event) => {
            const runBtn = event.target.closest("[data-open-run]");
            if (runBtn) openRunSummary(runBtn.dataset.openRun);
        };

        el.onclick = (event) => { if (event.target.closest("#study-back-btn")) loadDecisionStudies(); };
    } catch (e) { setDecisionError(el, e.message); }
}

// =====================================================================
// Reports
// =====================================================================

async function loadDecisionReports() {
    const el = decisionContainer("reports");
    if (!el) return;
    setDecisionLoading(el);

    try {
        const data = await decisionFetchJson("/api/decision/reports");
        const reports = data.reports || [];
        if (!reports.length) { setDecisionEmpty(el, "No reports found."); return; }

        renderDecisionTable(el, [
            { key: "report_id", label: "Report ID" },
            { key: "source_type", label: "Source Type" },
            { key: "source_id", label: "Source ID" },
            { key: "generated_at", label: "Generated" },
            { key: "action", label: "Action", render: row => `<button data-open-report="${escapeHtml(row.report_id)}">Open</button>` }
        ], reports);

        el.onclick = (event) => {
            const btn = event.target.closest("[data-open-report]");
            if (btn) openReport(btn.dataset.openReport);
        };
    } catch (e) { setDecisionError(el, e.message); }
}

async function openReport(reportId) {
    const el = decisionContainer("reports");
    if (!el) return;
    setDecisionLoading(el);

    try {
        const data = await decisionFetchJson(`/api/decision/reports/${encodeURIComponent(reportId)}`);
        el.innerHTML = `
            <div class="decision-toolbar"><button id="report-back-btn">Back to reports</button></div>
            <div class="decision-cards">
                ${decisionCard("Report ID", data.report_id)}
                ${decisionCard("Source Type", data.source_type)}
                ${decisionCard("Source ID", data.source_id)}
                ${decisionCard("Generated", data.generated_at)}
            </div>
            <pre class="markdown-preview">${escapeHtml(data.markdown || "")}</pre>
        `;
        el.onclick = (event) => { if (event.target.closest("#report-back-btn")) loadDecisionReports(); };
    } catch (e) { setDecisionError(el, e.message); }
}

// =====================================================================
// Spatial
// =====================================================================

async function generateSpatial() {
    const el = document.getElementById("spatial-detail");
    const runId = formValue("spatial-run-select");
    const top = formNumber("spatial-top", 20);
    const by = safeString(formValue("spatial-by")) || "blocked_ticks";
    if (!el) return;
    if (!runId) { setDecisionError(el, "Select a run."); return; }
    setDecisionLoading(el);

    try {
        const data = await decisionFetchJson(`/api/runs/${encodeURIComponent(runId)}/spatial?top=${encodeURIComponent(top)}&by=${encodeURIComponent(by)}`);
        const warning = (data.coverage === 0 || data.coverage === 0.0)
            ? `<div class="decision-status warning">Coverage is 0.0. Pre-v0.7.2 run or no spatial coordinates.</div>` : "";

        el.innerHTML = `
            <div class="decision-cards">
                ${decisionCard("Run ID", data.run_id)}
                ${decisionCard("Total blocked events", data.total_blocked_events)}
                ${decisionCard("Events with coordinates", data.events_with_coordinates)}
                ${decisionCard("Coverage", data.coverage)}
            </div>
            ${warning}
            <div class="decision-status warning">Spatial coordinates are approximate.</div>
            <div id="spatial-table"></div>
        `;

        renderDecisionTable(el.querySelector("#spatial-table"), [
            { key: "x", label: "x" }, { key: "y", label: "y" },
            { key: "blocked_events", label: "blocked_events" }, { key: "blocked_ticks", label: "blocked_ticks" }
        ], data.top_cells || [], "No bottleneck cells returned.");
    } catch (e) { setDecisionError(el, e.message); }
}

// =====================================================================
// Cost KPIs
// =====================================================================

async function generateCostKpis() {
    const el = document.getElementById("cost-detail");
    const runId = formValue("cost-run-select");
    if (!el) return;
    if (!runId) { setDecisionError(el, "Select a run."); return; }

    let costConfig;
    try {
        costConfig = JSON.parse(formValue("cost-config-editor"));
        if (costConfig === null || typeof costConfig !== "object" || Array.isArray(costConfig))
            throw new Error("Cost config must be a JSON object.");
    } catch (e) { setDecisionError(el, `Invalid cost config JSON: ${e.message}`); return; }

    setDecisionLoading(el);

    try {
        const url = `/api/runs/${encodeURIComponent(runId)}/cost-kpis?cost_config=${encodeURIComponent(JSON.stringify(costConfig))}`;
        const data = await decisionFetchJson(url);
        const currency = data.currency || "";
        const breakdownRows = Object.entries(data.cost_breakdown || {}).map(([key, value]) => ({ item: key, value }));

        el.innerHTML = `
            <div class="decision-cards">
                ${decisionCard("Total Operating Cost", formatMoney(data.total_operating_cost, currency))}
                ${decisionCard("Cost Per Task", data.cost_per_task == null ? "Unavailable" : formatMoney(data.cost_per_task, currency))}
                ${decisionCard("SLA Compliance", formatPercent(data.sla_compliance_rate))}
                ${decisionCard("Completed Tasks", data.completed_tasks)}
                ${decisionCard("SLA Evaluated Tasks", data.sla_evaluated_tasks)}
                ${decisionCard("Late Tasks", data.late_tasks)}
                ${decisionCard("Simulation Seconds", data.simulation_seconds)}
                ${decisionCard("Currency", currency)}
            </div>
            <h3>Cost Breakdown</h3><div id="cost-breakdown-table"></div>
        `;

        renderDecisionTable(el.querySelector("#cost-breakdown-table"), [
            { key: "item", label: "Item" },
            { key: "value", label: `Cost (${currency || "USD"})`, render: row => escapeHtml(formatMoney(row.value, currency)) }
        ], breakdownRows, "No cost breakdown available.");
    } catch (e) { setDecisionError(el, e.message); }
}

// =====================================================================
// Monte Carlo
// =====================================================================

async function loadDecisionMonteCarlo() {
    const el = decisionContainer("monte-carlo");
    if (!el) return;
    setDecisionLoading(el);

    try {
        const data = await decisionFetchJson("/api/decision/monte-carlo");
        const items = data.monte_carlo || [];
        if (!items.length) { setDecisionEmpty(el, "No Monte Carlo studies found."); return; }

        renderDecisionTable(el, [
            { key: "mc_id", label: "Monte Carlo ID" }, { key: "generated_at", label: "Generated" },
            { key: "n_runs_requested", label: "Requested" }, { key: "successful_runs", label: "Successful" },
            { key: "failed_runs", label: "Failed" }, { key: "effective_sla_target_ticks", label: "SLA Target" },
            { key: "action", label: "Action", render: row => `<button data-open-mc="${escapeHtml(row.mc_id)}">Open</button>` }
        ], items);

        el.onclick = (event) => {
            const btn = event.target.closest("[data-open-mc]");
            if (btn) openMonteCarloDetail(btn.dataset.openMc);
        };
    } catch (e) { setDecisionError(el, e.message); }
}

async function openMonteCarloDetail(mcId) {
    const el = decisionContainer("monte-carlo");
    if (!el) return;
    setDecisionLoading(el);

    try {
        const data = await decisionFetchJson(`/api/decision/monte-carlo/${encodeURIComponent(mcId)}`);
        const summary = data.summary || {};
        const aggregate = summary.aggregate || {};
        const kpis = aggregate.kpis || {};
        const sla = aggregate.sla || null;
        const errors = summary.errors || [];

        el.innerHTML = `
            <div class="decision-toolbar"><button data-back-mc>Back to Monte Carlo studies</button></div>
            <div class="decision-cards">
                ${decisionCard("Monte Carlo ID", summary.mc_id || mcId)}
                ${decisionCard("Generated", summary.generated_at || data.generated_at)}
                ${decisionCard("Requested Runs", summary.n_runs_requested)}
                ${decisionCard("Successful Runs", summary.successful_runs)}
                ${decisionCard("Failed Runs", summary.failed_runs)}
                ${decisionCard("Effective SLA Target", summary.effective_sla_target_ticks)}
            </div>
            <div class="decision-status warning">task_late_probability is the fraction of completed tasks that violated the SLA target.</div>
            ${toNumber(summary.failed_runs, 0) > 0 ? `<h3>Errors</h3><div class="mc-errors-table"></div>` : ""}
            <h3>Aggregate KPIs</h3><div class="mc-kpi-table"></div>
            <h3>SLA Statistics</h3>
            ${sla ? `<div class="mc-sla-table"></div>` : `<div class="decision-status">SLA metrics unavailable.</div>`}
            <h3>Trial Results</h3><div class="mc-results-table"></div>
        `;

        if (toNumber(summary.failed_runs, 0) > 0) renderErrorsTable(el.querySelector(".mc-errors-table"), errors);

        const kpiRows = Object.entries(kpis || {}).map(([metric, stats]) => ({
            metric, ...(typeof stats === "object" && stats !== null ? stats : { value: stats })
        }));

        renderDecisionTable(el.querySelector(".mc-kpi-table"), [
            { key: "metric", label: "KPI" }, { key: "count", label: "count" }, { key: "mean", label: "mean" },
            { key: "stdev", label: "stdev" }, { key: "min", label: "min" }, { key: "p05", label: "p05" },
            { key: "median", label: "median" }, { key: "p95", label: "p95" }, { key: "max", label: "max" },
            { key: "mean_ci95_low", label: "ci95_low" }, { key: "mean_ci95_high", label: "ci95_high" }
        ], kpiRows, "No aggregate KPIs.");

        if (sla) renderObjectTable(el.querySelector(".mc-sla-table"), sla, "SLA Field", "Value");

        renderPaginatedDynamicTable(el.querySelector(".mc-results-table"),
            (page, pageSize) => `/api/decision/monte-carlo/${encodeURIComponent(mcId)}/results?page=${page}&page_size=${pageSize}`,
            { flatten: true, linkRunId: true, preferredKeys: ["run_id", "seed", "tasks_completed", "average_cycle_time", "p95_cycle_time", "average_throughput", "cost_per_task", "sla_compliance_rate"] }
        );

        el.onclick = (event) => { if (event.target.closest("[data-back-mc]")) loadDecisionMonteCarlo(); };
    } catch (e) { setDecisionError(el, e.message); }
}

// =====================================================================
// Sensitivity
// =====================================================================

async function loadDecisionSensitivity() {
    const el = decisionContainer("sensitivity");
    if (!el) return;
    setDecisionLoading(el);

    try {
        const data = await decisionFetchJson("/api/decision/sensitivity");
        const items = data.sensitivity || [];
        if (!items.length) { setDecisionEmpty(el, "No sensitivity studies found."); return; }

        renderDecisionTable(el, [
            { key: "study_id", label: "Study ID" }, { key: "generated_at", label: "Generated" },
            { key: "reps", label: "Reps" }, { key: "successful_runs", label: "Successful" },
            { key: "failed_runs", label: "Failed" }, { key: "effective_sla_target_ticks", label: "SLA Target" },
            { key: "action", label: "Action", render: row => `<button data-open-sensitivity="${escapeHtml(row.study_id)}">Open</button>` }
        ], items);

        el.onclick = (event) => {
            const btn = event.target.closest("[data-open-sensitivity]");
            if (btn) openSensitivityDetail(btn.dataset.openSensitivity);
        };
    } catch (e) { setDecisionError(el, e.message); }
}

async function openSensitivityDetail(studyId) {
    const el = decisionContainer("sensitivity");
    if (!el) return;
    setDecisionLoading(el);

    try {
        const detailData = await decisionFetchJson(`/api/decision/sensitivity/${encodeURIComponent(studyId)}`);
        let tornadoData = { tornado: {} };
        try { tornadoData = await decisionFetchJson(`/api/decision/sensitivity/${encodeURIComponent(studyId)}/tornado`); } catch (e) { /* optional */ }

        const summary = detailData.summary || {};
        const baseline = summary.baseline || {};
        const factorResults = summary.factor_results || [];
        const errors = summary.errors || [];
        const tornado = tornadoData.tornado || summary.tornado || {};

        el.innerHTML = `
            <div class="decision-toolbar"><button data-back-sensitivity>Back to sensitivity studies</button></div>
            <div class="decision-cards">
                ${decisionCard("Study ID", summary.study_id || studyId)}
                ${decisionCard("Generated", summary.generated_at || detailData.generated_at)}
                ${decisionCard("Reps", summary.reps)}
                ${decisionCard("Successful Runs", summary.successful_runs)}
                ${decisionCard("Failed Runs", summary.failed_runs)}
            </div>
            <div class="decision-status warning">One-at-a-time sensitivity does not reveal interaction effects.</div>
            ${toNumber(summary.failed_runs, 0) > 0 ? `<h3>Errors</h3><div class="sens-errors-table"></div>` : ""}
            <h3>Baseline</h3><div class="sens-baseline-table"></div>
            <h3>Factor Results</h3><div class="sens-factor-table"></div>
            <h3>Tornado Data</h3><div class="sens-tornado"></div>
            <h3>Raw Results</h3><div class="sens-results-table"></div>
        `;

        if (toNumber(summary.failed_runs, 0) > 0) renderErrorsTable(el.querySelector(".sens-errors-table"), errors);

        renderRowsTable(el.querySelector(".sens-baseline-table"), [baseline], {
            flatten: true, preferredKeys: ["runs", "cost_per_task", "p95_cycle_time", "average_cycle_time", "average_throughput", "tasks_completed"]
        });

        renderRowsTable(el.querySelector(".sens-factor-table"), factorResults, {
            flatten: true, linkRunId: true,
            preferredKeys: ["factor", "name", "value", "reused_baseline", "runs", "cost_per_task", "p95_cycle_time", "delta_cost_per_task", "delta_percent_cost_per_task"]
        });

        const tornadoContainer = el.querySelector(".sens-tornado");
        const tornadoEntries = Object.entries(tornado || {});
        if (!tornadoEntries.length) {
            setDecisionEmpty(tornadoContainer, "No tornado data available.");
        } else {
            tornadoContainer.innerHTML = "";
            tornadoEntries.forEach(([target, rows]) => {
                const block = document.createElement("div");
                block.style.marginBottom = "16px";
                block.innerHTML = `<h4>${escapeHtml(target)}</h4><div class="sens-tornado-target"></div>`;
                tornadoContainer.appendChild(block);
                renderRowsTable(block.querySelector(".sens-tornado-target"), Array.isArray(rows) ? rows : [], {
                    flatten: true, preferredKeys: ["factor", "name", "value", "delta", "delta_percent"]
                });
            });
        }

        renderPaginatedDynamicTable(el.querySelector(".sens-results-table"),
            (page, pageSize) => `/api/decision/sensitivity/${encodeURIComponent(studyId)}/results?page=${page}&page_size=${pageSize}`,
            { flatten: true, linkRunId: true, preferredKeys: ["run_id", "factor", "value", "rep", "seed", "cost_per_task", "p95_cycle_time"] }
        );

        el.onclick = (event) => { if (event.target.closest("[data-back-sensitivity]")) loadDecisionSensitivity(); };
    } catch (e) { setDecisionError(el, e.message); }
}

// =====================================================================
// Optimization
// =====================================================================

async function loadDecisionOptimizations() {
    const el = decisionContainer("optimization");
    if (!el) return;
    setDecisionLoading(el);

    try {
        const data = await decisionFetchJson("/api/decision/optimizations");
        const items = data.optimizations || [];
        if (!items.length) { setDecisionEmpty(el, "No optimization studies found."); return; }

        renderDecisionTable(el, [
            { key: "opt_id", label: "Optimization ID" }, { key: "generated_at", label: "Generated" },
            { key: "objective", label: "Objective" }, { key: "direction", label: "Direction" },
            { key: "n_trials", label: "Trials" }, { key: "feasible_count", label: "Feasible" },
            { key: "infeasible_count", label: "Infeasible" },
            { key: "action", label: "Action", render: row => `<button data-open-optimization="${escapeHtml(row.opt_id)}">Open</button>` }
        ], items);

        el.onclick = (event) => {
            const btn = event.target.closest("[data-open-optimization]");
            if (btn) openOptimizationDetail(btn.dataset.openOptimization);
        };
    } catch (e) { setDecisionError(el, e.message); }
}

async function openOptimizationDetail(optId) {
    const el = decisionContainer("optimization");
    if (!el) return;
    setDecisionLoading(el);

    try {
        const data = await decisionFetchJson(`/api/decision/optimizations/${encodeURIComponent(optId)}`);
        const summary = data.summary || {};
        const bestTrial = summary.best_trial;

        el.innerHTML = `
            <div class="decision-toolbar"><button data-back-optimization>Back to optimization studies</button></div>
            <div class="decision-cards">
                ${decisionCard("Optimization ID", summary.opt_id || optId)}
                ${decisionCard("Generated", summary.generated_at || data.generated_at)}
                ${decisionCard("Objective", summary.objective)}
                ${decisionCard("Direction", summary.direction)}
                ${decisionCard("Trials", summary.n_trials)}
                ${decisionCard("Feasible", summary.feasible_count)}
                ${decisionCard("Infeasible", summary.infeasible_count)}
            </div>
            <div class="decision-status warning">Single-replica results are exploratory. Verify with robustness.</div>
            <h3>Best Trial</h3>
            ${bestTrial ? `<div class="opt-best-trial"></div>` : `<div class="decision-status error">No feasible solution found.</div>`}
            <h3>Constraints</h3><div class="opt-constraints-table"></div>
            <h3>Search Space</h3><div class="opt-search-space-table"></div>
            <h3>Trials</h3><div class="opt-trials-table"></div>
        `;

        if (bestTrial) renderRowsTable(el.querySelector(".opt-best-trial"), [bestTrial], { flatten: true, preferredKeys: ["number", "state", "feasible", "value"] });
        renderObjectTable(el.querySelector(".opt-constraints-table"), summary.constraints || {}, "Constraint", "Limit");
        renderRowsTable(el.querySelector(".opt-search-space-table"), summary.search_space || [], { flatten: true, preferredKeys: ["name", "type", "low", "high", "choices"] });

        renderPaginatedDynamicTable(el.querySelector(".opt-trials-table"),
            (page, pageSize) => `/api/decision/optimizations/${encodeURIComponent(optId)}/trials?page=${page}&page_size=${pageSize}`,
            { flatten: true, linkRunId: true, preferredKeys: ["number", "state", "feasible", "value", "objective"] }
        );

        el.onclick = (event) => { if (event.target.closest("[data-back-optimization]")) loadDecisionOptimizations(); };
    } catch (e) { setDecisionError(el, e.message); }
}

// =====================================================================
// Multi-objective
// =====================================================================

async function loadDecisionMultiobjective() {
    const el = decisionContainer("multiobjective");
    if (!el) return;
    setDecisionLoading(el);

    try {
        const data = await decisionFetchJson("/api/decision/multiobjective");
        const items = data.multiobjective || [];
        if (!items.length) { setDecisionEmpty(el, "No multi-objective studies found."); return; }

        renderDecisionTable(el, [
            { key: "study_id", label: "Study ID" }, { key: "generated_at", label: "Generated" },
            { key: "n_trials", label: "Trials" }, { key: "feasible_count", label: "Feasible" },
            { key: "pareto_count", label: "Pareto" },
            { key: "action", label: "Action", render: row => `<button data-open-multiobjective="${escapeHtml(row.study_id)}">Open</button>` }
        ], items);

        el.onclick = (event) => {
            const btn = event.target.closest("[data-open-multiobjective]");
            if (btn) openMultiobjectiveDetail(btn.dataset.openMultiobjective);
        };
    } catch (e) { setDecisionError(el, e.message); }
}

async function openMultiobjectiveDetail(studyId) {
    const el = decisionContainer("multiobjective");
    if (!el) return;
    setDecisionLoading(el);

    try {
        const data = await decisionFetchJson(`/api/decision/multiobjective/${encodeURIComponent(studyId)}`);
        const summary = data.summary || {};

        el.innerHTML = `
            <div class="decision-toolbar"><button data-back-multiobjective>Back to multi-objective studies</button></div>
            <div class="decision-cards">
                ${decisionCard("Study ID", summary.study_id || studyId)}
                ${decisionCard("Generated", summary.generated_at || data.generated_at)}
                ${decisionCard("Trials", summary.n_trials ?? summary.total_trials)}
                ${decisionCard("Feasible", summary.feasible_count)}
                ${decisionCard("Pareto Count", summary.pareto_count)}
            </div>
            <div class="decision-status warning">Pareto candidates are not deployable until verified by robustness.</div>
            <h3>Objectives</h3><div class="mo-objectives-table"></div>
            <h3>Constraints</h3><div class="mo-constraints-table"></div>
            <h3>Search Space</h3><div class="mo-search-space-table"></div>
            <h3>Pareto Trials</h3><div class="mo-pareto-table"></div>
            <h3>All Trials</h3><div class="mo-trials-table"></div>
        `;

        renderRowsTable(el.querySelector(".mo-objectives-table"), summary.objectives || [], { flatten: true, preferredKeys: ["metric", "direction"] });
        renderObjectTable(el.querySelector(".mo-constraints-table"), summary.constraints || {}, "Constraint", "Limit");
        renderRowsTable(el.querySelector(".mo-search-space-table"), summary.search_space || [], { flatten: true, preferredKeys: ["name", "type", "low", "high", "choices"] });

        renderPaginatedDynamicTable(el.querySelector(".mo-pareto-table"),
            (page, pageSize) => `/api/decision/multiobjective/${encodeURIComponent(studyId)}/pareto?page=${page}&page_size=${pageSize}`,
            { flatten: true, preferredKeys: ["trial_number", "feasible", "cost_per_task", "p95_cycle_time"] }
        );

        renderPaginatedDynamicTable(el.querySelector(".mo-trials-table"),
            (page, pageSize) => `/api/decision/multiobjective/${encodeURIComponent(studyId)}/trials?page=${page}&page_size=${pageSize}`,
            { flatten: true, linkRunId: true, preferredKeys: ["number", "state", "feasible"] }
        );

        el.onclick = (event) => { if (event.target.closest("[data-back-multiobjective]")) loadDecisionMultiobjective(); };
    } catch (e) { setDecisionError(el, e.message); }
}

// =====================================================================
// Robustness
// =====================================================================

async function loadDecisionRobustness() {
    const el = decisionContainer("robustness");
    if (!el) return;
    setDecisionLoading(el);

    try {
        const data = await decisionFetchJson("/api/decision/robustness");
        const items = data.robustness || [];
        if (!items.length) { setDecisionEmpty(el, "No robustness studies found."); return; }

        renderDecisionTable(el, [
            { key: "robust_id", label: "Robustness ID" }, { key: "generated_at", label: "Generated" },
            { key: "reps", label: "Reps" }, { key: "objective", label: "Objective" },
            { key: "direction", label: "Direction" }, { key: "successful_runs", label: "Successful" },
            { key: "failed_runs", label: "Failed" },
            { key: "recommended", label: "Recommended", render: row => row.recommended == null ? "-" : escapeHtml(typeof row.recommended === "object" ? (row.recommended.label || JSON.stringify(row.recommended)) : row.recommended) },
            { key: "action", label: "Action", render: row => `<button data-open-robustness="${escapeHtml(row.robust_id)}">Open</button>` }
        ], items);

        el.onclick = (event) => {
            const btn = event.target.closest("[data-open-robustness]");
            if (btn) openRobustnessDetail(btn.dataset.openRobustness);
        };
    } catch (e) { setDecisionError(el, e.message); }
}

async function openRobustnessDetail(robustId) {
    const el = decisionContainer("robustness");
    if (!el) return;
    setDecisionLoading(el);

    try {
        const data = await decisionFetchJson(`/api/decision/robustness/${encodeURIComponent(robustId)}`);
        const summary = data.summary || {};
        const candidates = summary.candidates || [];
        const errors = summary.errors || [];
        const reps = toNumber(summary.reps, 0);
        const minPassProbability = summary.min_pass_probability;

        el.innerHTML = `
            <div class="decision-toolbar"><button data-back-robustness>Back to robustness studies</button></div>
            <div class="decision-cards">
                ${decisionCard("Robustness ID", summary.robust_id || robustId)}
                ${decisionCard("Generated", summary.generated_at || data.generated_at)}
                ${decisionCard("Reps", summary.reps)}
                ${decisionCard("Objective", summary.objective)}
                ${decisionCard("Direction", summary.direction)}
                ${decisionCard("Min Pass Probability", formatProbability(minPassProbability))}
                ${decisionCard("Successful Runs", summary.successful_runs)}
                ${decisionCard("Failed Runs", summary.failed_runs)}
            </div>
            ${reps < 20 ? `<div class="decision-status warning">reps below 20 is not recommended for deployment decisions.</div>` : ""}
            ${summary.recommended == null
                ? `<div class="decision-status error">No candidate met the required constraint pass probability.</div>`
                : `<div class="decision-status success">Recommended: ${escapeHtml(typeof summary.recommended === "object" ? (summary.recommended.label || JSON.stringify(summary.recommended)) : summary.recommended)}</div>`}
            ${toNumber(summary.failed_runs, 0) > 0 ? `<h3>Errors</h3><div class="rob-errors-table"></div>` : ""}
            <h3>Constraints</h3><div class="rob-constraints-table"></div>
            <h3>Candidates</h3><div class="rob-candidates-table"></div>
            <h3>Replication Results</h3><div class="rob-results-table"></div>
        `;

        if (toNumber(summary.failed_runs, 0) > 0) renderErrorsTable(el.querySelector(".rob-errors-table"), errors);
        renderObjectTable(el.querySelector(".rob-constraints-table"), summary.constraints || {}, "Constraint", "Limit");

        if (!candidates.length) {
            setDecisionEmpty(el.querySelector(".rob-candidates-table"), "No candidate summary available.");
        } else {
            renderDecisionTable(el.querySelector(".rob-candidates-table"), [
                { key: "label", label: "Candidate" },
                { key: "successful_reps", label: "Successful Reps" },
                { key: "failed_reps", label: "Failed Reps" },
                { key: "constraint_pass_probability", label: "Pass Probability", render: row => probabilityBarHtml(row.constraint_pass_probability, minPassProbability) },
                { key: "robust_pass", label: "Robust Pass", render: row => robustPassBadge(row.robust_pass) },
                { key: "objective_mean", label: "Objective Mean" },
                { key: "objective_stdev", label: "Objective Stdev" },
                { key: "constraint_details", label: "Details", render: row => `<details><summary>Details</summary><pre class="json-preview">${escapeHtml(JSON.stringify(row.constraint_details || {}, null, 2))}</pre></details>` }
            ], candidates);
        }

        renderPaginatedDynamicTable(el.querySelector(".rob-results-table"),
            (page, pageSize) => `/api/decision/robustness/${encodeURIComponent(robustId)}/results?page=${page}&page_size=${pageSize}`,
            { flatten: true, linkRunId: true, preferredKeys: ["candidate_label", "label", "rep", "seed", "run_id", "cost_per_task", "p95_cycle_time"] }
        );

        el.onclick = (event) => { if (event.target.closest("[data-back-robustness]")) loadDecisionRobustness(); };
    } catch (e) { setDecisionError(el, e.message); }
}

// =====================================================================
// Jobs
// =====================================================================

async function loadDecisionJobs() {
    const el = decisionContainer("jobs");
    if (!el) return;
    setDecisionLoading(el);

    try {
        const data = await decisionFetchJson("/api/decision/jobs");
        const jobs = data.jobs || [];
        renderJobs(el, jobs);

        const hasActive = jobs.some(j => j.status === "queued" || j.status === "running");
        if (hasActive && !jobPollingInterval) startJobPolling();
        else if (!hasActive && jobPollingInterval) stopJobPolling();
    } catch (e) { setDecisionError(el, e.message); }
}

function renderJobs(el, jobs) {
    el.innerHTML = `
        <div class="decision-toolbar"><button id="decision-job-launch-btn">Launch New Job</button></div>
        <div id="jobs-table"></div>
    `;
    el.querySelector("#decision-job-launch-btn").onclick = openJobModal;

    if (!jobs.length) {
        el.querySelector("#jobs-table").innerHTML = `<div class="decision-status">No active or recent decision jobs.</div>`;
        return;
    }

    renderDecisionTable(el.querySelector("#jobs-table"), [
        { key: "job_id", label: "Job ID" },
        { key: "module", label: "Module" },
        { key: "status", label: "Status", render: row => {
            const map = { finished: "badge-success", failed: "badge-error", running: "badge-info", queued: "badge-warning", cancelled: "badge-warning" };
            return `<span class="badge ${map[row.status] || ""}">${escapeHtml(row.status)}</span>`;
        }},
        { key: "created_at", label: "Created" },
        { key: "finished_at", label: "Finished" },
        { key: "artifact_type", label: "Artifact Type" },
        { key: "action", label: "Action", render: row => {
            if (row.status === "finished" && row.artifact_type && row.artifact_id)
                return `<button data-open-artifact-type="${escapeHtml(row.artifact_type)}" data-open-artifact-id="${escapeHtml(row.artifact_id)}">Open</button>`;
            if (row.status === "queued") return `<button data-cancel-job="${escapeHtml(row.job_id)}">Cancel</button>`;
            if (row.status === "failed" && row.error) return `<details><summary>Error</summary><pre class="json-preview">${escapeHtml(row.error)}</pre></details>`;
            return "-";
        }}
    ], jobs);

    el.onclick = (event) => {
        const openBtn = event.target.closest("[data-open-artifact-type]");
        if (openBtn) { openArtifact(openBtn.dataset.openArtifactType, openBtn.dataset.openArtifactId); return; }
        const cancelBtn = event.target.closest("[data-cancel-job]");
        if (cancelBtn) cancelJob(cancelBtn.dataset.cancelJob);
    };
}

function openArtifact(type, id) {
    const map = {
        monte_carlo: ["monte-carlo", openMonteCarloDetail],
        sensitivity: ["sensitivity", openSensitivityDetail],
        optimization: ["optimization", openOptimizationDetail],
        multiobjective: ["multiobjective", openMultiobjectiveDetail],
        robustness: ["robustness", openRobustnessDetail],
        study: ["studies", loadStudyDetail],
        report: ["reports", openReport]
    };
    const entry = map[type];
    if (!entry) { alert(`Opening artifact type '${type}' is not supported yet.`); return; }
    showDecisionSubview(entry[0]);
    setTimeout(() => entry[1](id), 100);
}

async function cancelJob(jobId) {
    if (!confirm(`Cancel job ${jobId}?`)) return;
    try {
        const res = await fetch(`/api/decision/jobs/${encodeURIComponent(jobId)}/cancel`, { method: "POST" });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Failed to cancel job.");
        loadDecisionJobs();
    } catch (e) { alert(e.message); }
}

function startJobPolling() {
    if (jobPollingInterval) return;
    jobPollingInterval = setInterval(() => {
        if (currentView === "decision" && decisionSubview === "jobs") loadDecisionJobs();
    }, 2000);
}

function stopJobPolling() {
    if (jobPollingInterval) { clearInterval(jobPollingInterval); jobPollingInterval = null; }
}

// =====================================================================
// Job Modal
// =====================================================================

function openJobModal() {
    const modal = document.getElementById("decision-job-modal");
    if (!modal) return;
    modal.hidden = false;
    document.getElementById("decision-job-error").hidden = true;
    loadJobTemplate(document.getElementById("decision-job-module").value);
}

function closeJobModal() {
    const modal = document.getElementById("decision-job-modal");
    if (modal) modal.hidden = true;
}

function loadJobTemplate(module) {
    const editor = document.getElementById("decision-job-config-editor");
    if (!editor) return;

    const templates = {
        monte_carlo: { from_run_id: "REPLACE_WITH_RUN_ID", n_runs: 2, base_seed: 42, sla_target_ticks: 300, cost_config: { robot_opex_per_hour: 12.5, charger_infra_cost_per_hour: 2.0, downtime_cost_per_hour: 30.0, sla_target_ticks: 300, sla_penalty_per_late_tick: 0.5, currency: "USD" } },
        sensitivity: { from_run_id: "REPLACE_WITH_RUN_ID", reps: 2, base_seed: 42, factors: [{ name: "num_robots", values: [4, 6, 8] }] },
        optimizer: { from_run_id: "REPLACE_WITH_RUN_ID", objective: "cost_per_task", direction: "minimize", n_trials: 5, reps: 1, base_seed: 42, constraints: { p95_cycle_time_max: 60.0 }, search_space: [{ name: "num_robots", type: "int", low: 4, high: 8 }] },
        multiobjective: { from_run_id: "REPLACE_WITH_RUN_ID", n_trials: 5, reps: 1, base_seed: 42, objectives: [{ metric: "cost_per_task", direction: "minimize" }, { metric: "p95_cycle_time", direction: "minimize" }], search_space: [{ name: "num_robots", type: "int", low: 4, high: 8 }] },
        robustness: { from_multiobjective_id: "REPLACE_WITH_MULTIOBJECTIVE_ID", max_candidates: 2, reps: 5, base_seed: 123, constraints: { p95_cycle_time_max: 60.0 }, objective: "cost_per_task", direction: "minimize", min_pass_probability: 0.90 },
        study: { from_run_id: "REPLACE_WITH_RUN_ID", factors: [{ name: "num_robots", values: [4, 6] }] },
        report: { run_id: "REPLACE_WITH_RUN_ID" },
        spatial: { run_id: "REPLACE_WITH_RUN_ID", top: 20, by: "blocked_ticks" }
    };

    editor.value = JSON.stringify(templates[module] || {}, null, 2);
}

async function submitJob() {
    const module = document.getElementById("decision-job-module").value;
    const editor = document.getElementById("decision-job-config-editor");
    const errorEl = document.getElementById("decision-job-error");

    let config;
    try { config = JSON.parse(editor.value); }
    catch (e) { errorEl.textContent = `Invalid JSON: ${e.message}`; errorEl.hidden = false; return; }

    errorEl.hidden = true;

    try {
        const res = await fetch("/api/decision/jobs", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ module, config })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Failed to submit job.");
        closeJobModal();
        loadDecisionJobs();
    } catch (e) {
        errorEl.textContent = e.message;
        errorEl.hidden = false;
    }
}