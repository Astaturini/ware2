// =====================================================================
// Phase 4 guided decision job forms
// Includes:
// monte_carlo, sensitivity, report, spatial,
// optimizer, multiobjective, robustness, study
//
// Loads after decision.js and before app.js.
// =====================================================================

// =====================================================================
// Guided modal helpers
// =====================================================================

function isGuidedJobFormEnabled() {
  const checkbox = document.getElementById("decision-job-use-guided");
  return Boolean(checkbox && checkbox.checked);
}

function hasGuidedJobForm(module) {
  return [
    "monte_carlo",
    "sensitivity",
    "report",
    "spatial",
    "optimizer",
    "multiobjective",
    "robustness",
    "study"
  ].includes(module);
}

function setJobGuidedError(message) {
  const guidedErrorEl = document.getElementById("decision-job-guided-error");
  const legacyErrorEl = document.getElementById("decision-job-error");

  if (guidedErrorEl) {
    guidedErrorEl.textContent = message || "";
    guidedErrorEl.hidden = !message;
  }

  if (legacyErrorEl && message) {
    legacyErrorEl.textContent = message;
    legacyErrorEl.hidden = false;
  }
}

function clearJobGuidedError() {
  setJobGuidedError("");
}

function updateJobGuidedVisibility() {
  const guidedEl = document.getElementById("decision-job-guided");
  const jsonWrapperEl = document.getElementById("decision-job-json-wrapper");
  const guidedEnabled = isGuidedJobFormEnabled();

  if (guidedEl) {
    guidedEl.hidden = !guidedEnabled;
  }

  if (jsonWrapperEl) {
    jsonWrapperEl.hidden = guidedEnabled;
  }

  clearJobGuidedError();
}

function toggleJobGuidedJson() {
  const checkbox = document.getElementById("decision-job-use-guided");
  const editor = document.getElementById("decision-job-config-editor");
  const moduleEl = document.getElementById("decision-job-module");

  if (!checkbox) return;

  const module = moduleEl ? moduleEl.value : "monte_carlo";

  // Leaving guided mode: try to serialize the guided form into JSON.
  if (checkbox.checked && hasGuidedJobForm(module)) {
    try {
      const config = buildGuidedJobConfig(module);

      if (editor) {
        editor.value = JSON.stringify(config, null, 2);
      }

      checkbox.checked = false;
    } catch (error) {
      setJobGuidedError(error.message);
      return;
    }
  } else {
    checkbox.checked = !checkbox.checked;
  }

  updateJobGuidedVisibility();
}

function onDecisionJobModuleChange(event) {
  const module = event.target.value;

  if (isGuidedJobFormEnabled()) {
    renderGuidedJobForm(module);
  } else {
    loadJobTemplate(module);
  }
}

// =====================================================================
// Small guided-form validation helpers
// =====================================================================

async function populateJobRunSelect(selectEl) {
  if (!selectEl) return;

  selectEl.innerHTML = "<option value=\"\">Loading runs…</option>";

  try {
    const data = await decisionFetchJson("/api/runs");
    const runs = data.runs || [];

    selectEl.innerHTML = "";

    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "Select run";
    selectEl.appendChild(placeholder);

    runs.forEach(run => {
      const option = document.createElement("option");
      option.value = run.run_id;

      const displayName =
        run.config && run.config.display_name
          ? ` — ${run.config.display_name}`
          : "";

      option.textContent = `${run.run_id}${displayName}`;
      selectEl.appendChild(option);
    });
  } catch (error) {
    console.error(error);
    selectEl.innerHTML = "<option value=\"\">Failed to load runs</option>";
  }
}

function parseGuidedJson(id, fallback = null) {
  const el = document.getElementById(id);
  if (!el) return fallback;

  const raw = el.value.trim();

  if (!raw) {
    return fallback;
  }

  try {
    return JSON.parse(raw);
  } catch (error) {
    throw new Error(`${id} contains invalid JSON.`);
  }
}

function parseGuidedJsonObject(id, fallback = {}) {
  const value = parseGuidedJson(id, fallback);

  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${id} must be a JSON object.`);
  }

  return value;
}

function parseGuidedJsonArray(id, fallback = []) {
  const value = parseGuidedJson(id, fallback);

  if (!Array.isArray(value)) {
    throw new Error(`${id} must be a JSON array.`);
  }

  return value;
}

function guidedRequiredInteger(id, min = null) {
  const el = document.getElementById(id);

  if (!el) {
    throw new Error(`${id} is missing.`);
  }

  const raw = el.value.trim();

  if (raw === "") {
    throw new Error(`${id} is required.`);
  }

  const value = Number(raw);

  if (!Number.isFinite(value) || !Number.isInteger(value)) {
    throw new Error(`${id} must be an integer.`);
  }

  if (min !== null && value < min) {
    throw new Error(`${id} must be >= ${min}.`);
  }

  return value;
}

function guidedOptionalInteger(id, min = null) {
  const el = document.getElementById(id);
  if (!el) return null;

  const raw = el.value.trim();

  if (raw === "") {
    return null;
  }

  const value = Number(raw);

  if (!Number.isFinite(value) || !Number.isInteger(value)) {
    throw new Error(`${id} must be an integer.`);
  }

  if (min !== null && value < min) {
    throw new Error(`${id} must be >= ${min}.`);
  }

  return value;
}

function guidedRequiredNumber(id, min = null, max = null) {
  const el = document.getElementById(id);

  if (!el) {
    throw new Error(`${id} is missing.`);
  }

  const raw = el.value.trim();

  if (raw === "") {
    throw new Error(`${id} is required.`);
  }

  const value = Number(raw);

  if (!Number.isFinite(value)) {
    throw new Error(`${id} must be a valid number.`);
  }

  if (min !== null && value < min) {
    throw new Error(`${id} must be >= ${min}.`);
  }

  if (max !== null && value > max) {
    throw new Error(`${id} must be <= ${max}.`);
  }

  return value;
}

function guidedOptionalNumber(id, min = null, max = null) {
  const el = document.getElementById(id);
  if (!el) return null;

  const raw = el.value.trim();

  if (raw === "") {
    return null;
  }

  const value = Number(raw);

  if (!Number.isFinite(value)) {
    throw new Error(`${id} must be a valid number.`);
  }

  if (min !== null && value < min) {
    throw new Error(`${id} must be >= ${min}.`);
  }

  if (max !== null && value > max) {
    throw new Error(`${id} must be <= ${max}.`);
  }

  return value;
}

function getCostConfigTemplateObject() {
  if (typeof DEFAULT_EXAMPLE_COST_CONFIG !== "undefined") {
    return JSON.parse(JSON.stringify(DEFAULT_EXAMPLE_COST_CONFIG));
  }

  return {
    robot_opex_per_hour: 12.5,
    charger_infra_cost_per_hour: 2.0,
    downtime_cost_per_hour: 30.0,
    sla_target_ticks: 300,
    sla_penalty_per_late_tick: 0.5,
    currency: "USD"
  };
}

// =====================================================================
// Shared objective / constraint / search-space helpers
// =====================================================================

function supportedObjectiveMetrics() {
  return [
    "cost_per_task",
    "p95_cycle_time",
    "average_cycle_time",
    "average_throughput",
    "tasks_completed",
    "sla_compliance_rate",
    "total_blocked_ticks"
  ];
}

function defaultDirectionForMetric(metric) {
  if (
    metric === "average_throughput" ||
    metric === "tasks_completed" ||
    metric === "sla_compliance_rate"
  ) {
    return "maximize";
  }

  return "minimize";
}

function metricOptionsHtml(selectedMetric) {
  return supportedObjectiveMetrics()
    .map(metric => {
      const selected = metric === selectedMetric ? "selected" : "";

      return `<option value="${escapeHtml(metric)}" ${selected}>${escapeHtml(metric)}</option>`;
    })
    .join("");
}

function parseGuidedCostConfig(id) {
  const costConfig = parseGuidedJson(id, null);

  if (costConfig !== null) {
    if (typeof costConfig !== "object" || Array.isArray(costConfig)) {
      throw new Error(`${id} must be a JSON object.`);
    }
  }

  return costConfig;
}

function renderGuidedExecutionSection(
  prefix,
  supportsMetricsOnly = false,
  supportsParallel = false
) {
  return `
    <div class="decision-guided-subsection">
      <h4>Trial execution</h4>

      <div class="decision-guided-row">
        <label class="field">
          Workers
          <input id="${prefix}-max-workers" type="number" min="1" max="4" step="1" value="1" ${supportsParallel ? "" : "disabled"}>
        </label>

        <label class="field">
          Trial artifacts
          <select id="${prefix}-trial-artifact-mode">
            <option value="full" selected>Full run artifacts</option>
            <option value="metrics_only" ${supportsMetricsOnly ? "" : "disabled"}>Metrics only</option>
          </select>
        </label>

        <span></span>
      </div>

      <div class="decision-guided-warning">
        Metrics-only trials do not create normal run files or support single-run reports and spatial analysis.
      </div>
    </div>
  `;
}

function buildGuidedExecutionConfig(prefix) {
  const workersEl = document.getElementById(`${prefix}-max-workers`);
  const maxWorkers = workersEl.disabled
    ? 1
    : guidedRequiredInteger(`${prefix}-max-workers`, 1);

  if (maxWorkers > 4) {
    throw new Error(`${prefix}-max-workers must be <= 4.`);
  }

  const mode = document.getElementById(`${prefix}-trial-artifact-mode`).value;
  return {
    max_workers: maxWorkers,
    trial_artifact_mode: mode
  };
}

function buildGuidedCommonConstraints(prefix) {
  const constraints = {};

  const p95Max = guidedOptionalNumber(`${prefix}-constraint-p95-max`, 0);

  if (p95Max !== null) {
    constraints.p95_cycle_time_max = p95Max;
  }

  const slaMin = guidedOptionalNumber(`${prefix}-constraint-sla-min`, 0, 1);

  if (slaMin !== null) {
    constraints.sla_compliance_rate_min = slaMin;
  }

  return constraints;
}

function renderGuidedSearchSpaceSection(prefix) {
  return `
    <div class="decision-guided-subsection">
      <h4>Search space</h4>

      <div class="decision-guided-warning">
        Enable at least one parameter.
      </div>

      <div class="decision-search-parameter">
        <label class="decision-search-parameter-title">
          <input id="${prefix}-ss-num-robots-enabled" type="checkbox" checked>
          <strong>num_robots</strong>
        </label>

        <div class="decision-guided-row">
        <label class="field">
          Low
          <input id="${prefix}-ss-num-robots-low" type="number" min="1" step="1" value="4">
        </label>

        <label class="field">
          High
          <input id="${prefix}-ss-num-robots-high" type="number" min="1" step="1" value="8">
        </label>

        <span></span>
        </div>
      </div>

      <div class="decision-search-parameter">
        <label class="decision-search-parameter-title">
          <input id="${prefix}-ss-charger-capacity-enabled" type="checkbox">
          <strong>charger_capacity</strong>
        </label>

        <div class="decision-guided-row">
        <label class="field">
          Low
          <input id="${prefix}-ss-charger-capacity-low" type="number" min="1" step="1" value="2">
        </label>

        <label class="field">
          High
          <input id="${prefix}-ss-charger-capacity-high" type="number" min="1" step="1" value="6">
        </label>

        <span></span>
        </div>
      </div>

      <div class="decision-search-parameter">
        <label class="decision-search-parameter-title">
          <input id="${prefix}-ss-conflict-manager-enabled" type="checkbox">
          <strong>conflict_manager</strong>
        </label>

        <div class="decision-guided-checkbox-grid">
        <label>
          <input type="checkbox" name="${prefix}-ss-conflict-manager-choice" value="local_yield" checked>
          local_yield
        </label>

        <label>
          <input type="checkbox" name="${prefix}-ss-conflict-manager-choice" value="zone_locks">
          zone_locks
        </label>

        <label>
          <input type="checkbox" name="${prefix}-ss-conflict-manager-choice" value="priority_reservation">
          priority_reservation
        </label>
        </div>
      </div>

      <div class="decision-search-parameter">
        <label class="decision-search-parameter-title">
          <input id="${prefix}-ss-scheduler-enabled" type="checkbox">
          <strong>scheduler</strong>
        </label>

        <div class="decision-guided-checkbox-grid">
        <label>
          <input type="checkbox" name="${prefix}-ss-scheduler-choice" value="baseline" checked>
          baseline
        </label>

        <label>
          <input type="checkbox" name="${prefix}-ss-scheduler-choice" value="priority">
          priority
        </label>

        <label>
          <input type="checkbox" name="${prefix}-ss-scheduler-choice" value="fifo">
          fifo
        </label>

        <label>
          <input type="checkbox" name="${prefix}-ss-scheduler-choice" value="total_cost">
          total_cost
        </label>

        <label>
          <input type="checkbox" name="${prefix}-ss-scheduler-choice" value="auction">
          auction
        </label>
        </div>
      </div>
    </div>
  `;
}

function getGuidedCheckedChoices(name) {
  return Array.from(
    document.querySelectorAll(`input[name="${name}"]:checked`)
  ).map(el => el.value);
}

function buildGuidedSearchSpace(prefix) {
  const searchSpace = [];

  if (document.getElementById(`${prefix}-ss-num-robots-enabled`)?.checked) {
    const low = guidedRequiredInteger(`${prefix}-ss-num-robots-low`, 1);
    const high = guidedRequiredInteger(`${prefix}-ss-num-robots-high`, 1);

    if (low > high) {
      throw new Error("num_robots search space requires low <= high.");
    }

    searchSpace.push({
      name: "num_robots",
      type: "int",
      low,
      high
    });
  }

  if (document.getElementById(`${prefix}-ss-charger-capacity-enabled`)?.checked) {
    const low = guidedRequiredInteger(`${prefix}-ss-charger-capacity-low`, 1);
    const high = guidedRequiredInteger(`${prefix}-ss-charger-capacity-high`, 1);

    if (low > high) {
      throw new Error("charger_capacity search space requires low <= high.");
    }

    searchSpace.push({
      name: "charger_capacity",
      type: "int",
      low,
      high
    });
  }

  if (document.getElementById(`${prefix}-ss-conflict-manager-enabled`)?.checked) {
    const choices = getGuidedCheckedChoices(`${prefix}-ss-conflict-manager-choice`);

    if (!choices.length) {
      throw new Error("Select at least one conflict_manager choice.");
    }

    searchSpace.push({
      name: "conflict_manager",
      type: "categorical",
      choices
    });
  }

  if (document.getElementById(`${prefix}-ss-scheduler-enabled`)?.checked) {
    const choices = getGuidedCheckedChoices(`${prefix}-ss-scheduler-choice`);

    if (!choices.length) {
      throw new Error("Select at least one scheduler choice.");
    }

    searchSpace.push({
      name: "scheduler",
      type: "categorical",
      choices
    });
  }

  if (!searchSpace.length) {
    throw new Error("Enable at least one search-space parameter.");
  }

  return searchSpace;
}

// =====================================================================
// Shared factor helpers for sensitivity and study
// =====================================================================

function commonFactorOptions() {
  return [
    "num_robots",
    "charger_capacity",
    "charge_duration_ticks",
    "critical_battery",
    "opportunistic_charge_threshold",
    "blocked_replan_seconds",
    "replan_cooldown_ticks",
    "tick_interval",
    "path_planner",
    "scheduler",
    "conflict_manager",
    "demand_rate_per_tick"
  ];
}

function parseGuidedFactorValues(raw) {
  const parts = String(raw || "")
    .split(",")
    .map(part => part.trim())
    .filter(Boolean);

  if (!parts.length) {
    throw new Error("Each factor needs at least one value.");
  }

  return parts.map(part => {
    const num = Number(part);

    if (Number.isFinite(num)) {
      return num;
    }

    return part;
  });
}

function addGuidedFactorRow(rowsEl, datalistId) {
  if (!rowsEl) return;

  const row = document.createElement("div");
  row.className = "decision-guided-row";

  row.innerHTML = `
    <label class="field">
      Factor
      <input class="guided-factor-name" type="text" list="${datalistId}" placeholder="num_robots">
    </label>

    <label class="field">
      Values
      <input class="guided-factor-values" type="text" placeholder="6, 8, 10">
    </label>

    <button type="button" class="guided-remove-factor-btn">Remove</button>
  `;

  row.querySelector(".guided-remove-factor-btn").addEventListener("click", () => {
    row.remove();
  });

  rowsEl.appendChild(row);
}

function buildGuidedFactors(rowsEl) {
  if (!rowsEl) {
    throw new Error("Factor rows container is missing.");
  }

  const rows = Array.from(rowsEl.querySelectorAll(".decision-guided-row"));

  const factors = rows.map(row => {
    const name = row.querySelector(".guided-factor-name").value.trim();
    const valuesRaw = row.querySelector(".guided-factor-values").value;

    if (!name) {
      throw new Error("Factor name is required.");
    }

    return {
      name,
      values: parseGuidedFactorValues(valuesRaw)
    };
  });

  if (!factors.length) {
    throw new Error("At least one factor is required.");
  }

  return factors;
}

// =====================================================================
// Guided form router
// =====================================================================

function renderGuidedJobForm(module) {
  const container = document.getElementById("decision-job-guided");
  if (!container) return;

  clearJobGuidedError();
  container.innerHTML = "";

  switch (module) {
    case "monte_carlo":
      renderMonteCarloGuidedForm(container);
      return;

    case "sensitivity":
      renderSensitivityGuidedForm(container);
      return;

    case "report":
      renderReportGuidedForm(container);
      return;

    case "spatial":
      renderSpatialGuidedForm(container);
      return;

    case "optimizer":
      renderOptimizerGuidedForm(container);
      return;

    case "multiobjective":
      renderMultiobjectiveGuidedForm(container);
      return;

    case "robustness":
      renderRobustnessGuidedForm(container);
      return;

    case "study":
      renderStudyGuidedForm(container);
      return;

    default:
      container.innerHTML = `
        <div class="decision-status">
          No guided form is available for ${escapeHtml(module)} yet.
          Disable guided mode and use the JSON editor.
        </div>
      `;
  }
}

function buildGuidedJobConfig(module) {
  switch (module) {
    case "monte_carlo":
      return buildMonteCarloGuidedConfig();

    case "sensitivity":
      return buildSensitivityGuidedConfig();

    case "report":
      return buildReportGuidedConfig();

    case "spatial":
      return buildSpatialGuidedConfig();

    case "optimizer":
      return buildOptimizerGuidedConfig();

    case "multiobjective":
      return buildMultiobjectiveGuidedConfig();

    case "robustness":
      return buildRobustnessGuidedConfig();

    case "study":
      return buildStudyGuidedConfig();

    default:
      throw new Error(`No guided config builder for module: ${module}`);
  }
}

// =====================================================================
// Monte Carlo guided form
// =====================================================================

function renderMonteCarloGuidedForm(container) {
  container.innerHTML = `
    <div class="decision-guided-subsection">
      <h4>Source</h4>

      <label class="field">
        Source type
        <select id="mc-source-type">
          <option value="from_run_id" selected>Existing run</option>
          <option value="base_config">Base config JSON</option>
        </select>
      </label>

      <div id="mc-source-run-field" class="field">
        Run
        <select id="mc-run-id"></select>
      </div>

      <div id="mc-source-config-field" class="field" hidden>
        Base config JSON
        <textarea id="mc-base-config" rows="8" placeholder='{
  "seed": 42,
  "num_robots": 6,
  "stop_mode": "workload",
  "target_tasks": 100,
  "max_ticks": 100000
}'></textarea>
      </div>
    </div>

    <div class="decision-guided-subsection">
      <h4>Monte Carlo settings</h4>

      <label class="field">
        Number of runs
        <input id="mc-n-runs" type="number" min="1" step="1" value="2">
      </label>

      <label class="field">
        Base seed
        <input id="mc-base-seed" type="number" step="1" value="42">
      </label>

      <label class="field">
        SLA target ticks, optional
        <input id="mc-sla-target-ticks" type="number" min="1" step="1" placeholder="300">
      </label>
    </div>

    <div class="decision-guided-subsection">
      <h4>Cost config, optional</h4>

      <div class="decision-toolbar">
        <button id="mc-cost-template-btn" type="button">
          Load cost config template
        </button>
      </div>

      <label class="field">
        Cost config JSON
        <textarea id="mc-cost-config" rows="8" placeholder='{
  "robot_opex_per_hour": 12.5,
  "charger_infra_cost_per_hour": 2.0,
  "downtime_cost_per_hour": 30.0,
  "sla_target_ticks": 300,
  "sla_penalty_per_late_tick": 0.5,
  "currency": "USD"
}'></textarea>
      </label>
    </div>

    ${renderGuidedExecutionSection("mc", true, true)}
  `;

  populateJobRunSelect(container.querySelector("#mc-run-id"));

  const sourceTypeEl = container.querySelector("#mc-source-type");
  const runFieldEl = container.querySelector("#mc-source-run-field");
  const configFieldEl = container.querySelector("#mc-source-config-field");

  function updateSourceVisibility() {
    const sourceType = sourceTypeEl.value;

    runFieldEl.hidden = sourceType !== "from_run_id";
    configFieldEl.hidden = sourceType !== "base_config";
  }

  sourceTypeEl.addEventListener("change", updateSourceVisibility);
  updateSourceVisibility();

  container.querySelector("#mc-cost-template-btn").addEventListener("click", () => {
    container.querySelector("#mc-cost-config").value = JSON.stringify(
      getCostConfigTemplateObject(),
      null,
      2
    );
  });
}

function buildMonteCarloGuidedConfig() {
  const sourceType = document.getElementById("mc-source-type").value;

  const config = {};

  if (sourceType === "from_run_id") {
    const runId = document.getElementById("mc-run-id").value;

    if (!runId) {
      throw new Error("Select a source run.");
    }

    config.from_run_id = runId;
  } else {
    config.base_config = parseGuidedJsonObject("mc-base-config", {});
  }

  config.n_runs = guidedRequiredInteger("mc-n-runs", 1);

  const baseSeed = guidedOptionalInteger("mc-base-seed", null);

  if (baseSeed !== null) {
    config.base_seed = baseSeed;
  }

  const slaTargetTicks = guidedOptionalInteger("mc-sla-target-ticks", 1);

  if (slaTargetTicks !== null) {
    config.sla_target_ticks = slaTargetTicks;
  }

  const costConfig = parseGuidedCostConfig("mc-cost-config");

  if (costConfig !== null) {
    config.cost_config = costConfig;
  }

  Object.assign(config, buildGuidedExecutionConfig("mc"));

  return config;
}

// =====================================================================
// Sensitivity guided form
// =====================================================================

function renderSensitivityGuidedForm(container) {
  const factorOptions = commonFactorOptions()
    .map(name => `<option value="${escapeHtml(name)}">`)
    .join("");

  container.innerHTML = `
    <datalist id="sens-factor-options">
      ${factorOptions}
    </datalist>

    <div class="decision-guided-subsection">
      <h4>Source</h4>

      <label class="field">
        Source type
        <select id="sens-source-type">
          <option value="from_run_id" selected>Existing run</option>
          <option value="base_config">Base config JSON</option>
        </select>
      </label>

      <div id="sens-source-run-field" class="field">
        Run
        <select id="sens-run-id"></select>
      </div>

      <div id="sens-source-config-field" class="field" hidden>
        Base config JSON
        <textarea id="sens-base-config" rows="8"></textarea>
      </div>
    </div>

    <div class="decision-guided-subsection">
      <h4>Sensitivity settings</h4>

      <label class="field">
        Reps
        <input id="sens-reps" type="number" min="1" step="1" value="2">
      </label>

      <label class="field">
        Base seed
        <input id="sens-base-seed" type="number" step="1" value="42">
      </label>

      <label class="field">
        SLA target ticks, optional
        <input id="sens-sla-target-ticks" type="number" min="1" step="1" placeholder="300">
      </label>

      <label class="field">
        Cost config JSON, optional
        <textarea id="sens-cost-config" rows="8"></textarea>
      </label>
    </div>

    <div class="decision-guided-subsection">
      <h4>Factors</h4>

      <div id="sens-factor-rows"></div>

      <div class="decision-toolbar">
        <button id="sens-add-factor-btn" type="button">
          Add factor
        </button>
      </div>

      <div class="decision-guided-warning">
        Values are comma-separated. Numeric values are converted automatically.
        Example: 6, 8, 10
      </div>

      <div class="decision-guided-warning">
        One-at-a-time sensitivity does not reveal interaction effects.
      </div>
    </div>

    ${renderGuidedExecutionSection("sens")}
  `;

  populateJobRunSelect(container.querySelector("#sens-run-id"));

  const sourceTypeEl = container.querySelector("#sens-source-type");
  const runFieldEl = container.querySelector("#sens-source-run-field");
  const configFieldEl = container.querySelector("#sens-source-config-field");

  function updateSourceVisibility() {
    const sourceType = sourceTypeEl.value;

    runFieldEl.hidden = sourceType !== "from_run_id";
    configFieldEl.hidden = sourceType !== "base_config";
  }

  sourceTypeEl.addEventListener("change", updateSourceVisibility);
  updateSourceVisibility();

  const factorRowsEl = container.querySelector("#sens-factor-rows");

  container.querySelector("#sens-add-factor-btn").addEventListener("click", () => {
    addGuidedFactorRow(factorRowsEl, "sens-factor-options");
  });

  addGuidedFactorRow(factorRowsEl, "sens-factor-options");
}

function buildSensitivityGuidedConfig() {
  const sourceType = document.getElementById("sens-source-type").value;

  const config = {};

  if (sourceType === "from_run_id") {
    const runId = document.getElementById("sens-run-id").value;

    if (!runId) {
      throw new Error("Select a source run.");
    }

    config.from_run_id = runId;
  } else {
    config.base_config = parseGuidedJsonObject("sens-base-config", {});
  }

  config.reps = guidedRequiredInteger("sens-reps", 1);

  const baseSeed = guidedOptionalInteger("sens-base-seed", null);

  if (baseSeed !== null) {
    config.base_seed = baseSeed;
  }

  const slaTargetTicks = guidedOptionalInteger("sens-sla-target-ticks", 1);

  if (slaTargetTicks !== null) {
    config.sla_target_ticks = slaTargetTicks;
  }

  const costConfig = parseGuidedCostConfig("sens-cost-config");

  if (costConfig !== null) {
    config.cost_config = costConfig;
  }

  config.factors = buildGuidedFactors(
    document.getElementById("sens-factor-rows")
  );

  Object.assign(config, buildGuidedExecutionConfig("sens"));

  return config;
}

// =====================================================================
// Report guided form
// =====================================================================

function renderReportGuidedForm(container) {
  container.innerHTML = `
    <div class="decision-guided-subsection">
      <h4>Report source</h4>

      <label class="field">
        Source type
        <select id="report-source-type">
          <option value="run" selected>Run</option>
          <option value="study">Study</option>
        </select>
      </label>

      <div id="report-run-field" class="field">
        Run
        <select id="report-run-id"></select>
      </div>

      <div id="report-study-field" class="field" hidden>
        Study ID
        <input id="report-study-id" type="text" placeholder="study id">
      </div>
    </div>
  `;

  populateJobRunSelect(container.querySelector("#report-run-id"));

  const sourceTypeEl = container.querySelector("#report-source-type");
  const runFieldEl = container.querySelector("#report-run-field");
  const studyFieldEl = container.querySelector("#report-study-field");

  function updateSourceVisibility() {
    const sourceType = sourceTypeEl.value;

    runFieldEl.hidden = sourceType !== "run";
    studyFieldEl.hidden = sourceType !== "study";
  }

  sourceTypeEl.addEventListener("change", updateSourceVisibility);
  updateSourceVisibility();
}

function buildReportGuidedConfig() {
  const sourceType = document.getElementById("report-source-type").value;

  if (sourceType === "run") {
    const runId = document.getElementById("report-run-id").value;

    if (!runId) {
      throw new Error("Select a run.");
    }

    return {
      run_id: runId
    };
  }

  const studyId = document.getElementById("report-study-id").value.trim();

  if (!studyId) {
    throw new Error("Enter a study id.");
  }

  return {
    study_id: studyId
  };
}

// =====================================================================
// Spatial guided form
// =====================================================================

function renderSpatialGuidedForm(container) {
  container.innerHTML = `
    <div class="decision-guided-subsection">
      <h4>Spatial source</h4>

      <label class="field">
        Run
        <select id="spatial-job-run-id"></select>
      </label>

      <label class="field">
        Top cells
        <input id="spatial-job-top" type="number" min="1" step="1" value="20">
      </label>

      <label class="field">
        Sort by
        <select id="spatial-job-by">
          <option value="blocked_ticks" selected>blocked_ticks</option>
          <option value="blocked_events">blocked_events</option>
        </select>
      </label>
    </div>
  `;

  populateJobRunSelect(container.querySelector("#spatial-job-run-id"));
}

function buildSpatialGuidedConfig() {
  const runId = document.getElementById("spatial-job-run-id").value;

  if (!runId) {
    throw new Error("Select a run.");
  }

  const top = guidedRequiredInteger("spatial-job-top", 1);
  const by = document.getElementById("spatial-job-by").value;

  return {
    run_id: runId,
    top,
    by
  };
}

// =====================================================================
// Optimizer guided form
// =====================================================================

function renderOptimizerGuidedForm(container) {
  container.innerHTML = `
    <div class="decision-guided-subsection">
      <h4>Source</h4>

      <label class="field">
        Source type
        <select id="opt-source-type">
          <option value="from_run_id" selected>Existing run</option>
          <option value="base_config">Base config JSON</option>
        </select>
      </label>

      <div id="opt-source-run-field" class="field">
        Run
        <select id="opt-run-id"></select>
      </div>

      <div id="opt-source-config-field" class="field" hidden>
        Base config JSON
        <textarea id="opt-base-config" rows="8" placeholder='{
  "seed": 42,
  "num_robots": 6,
  "stop_mode": "workload",
  "target_tasks": 100,
  "max_ticks": 100000
}'></textarea>
      </div>
    </div>

    <div class="decision-guided-subsection">
      <h4>Optimizer settings</h4>

      <label class="field">
        Objective
        <select id="opt-objective">
          ${metricOptionsHtml("p95_cycle_time")}
        </select>
      </label>

      <label class="field">
        Direction
        <select id="opt-direction">
          <option value="minimize" selected>minimize</option>
          <option value="maximize">maximize</option>
        </select>
      </label>

      <label class="field">
        Trials
        <input id="opt-n-trials" type="number" min="1" step="1" value="2">
      </label>

      <label class="field">
        Reps
        <input id="opt-reps" type="number" min="1" step="1" value="1">
      </label>

      <label class="field">
        Base seed
        <input id="opt-base-seed" type="number" step="1" value="42">
      </label>

      <label class="field">
        SLA target ticks, optional
        <input id="opt-sla-target-ticks" type="number" min="1" step="1" placeholder="300">
      </label>

      <div class="decision-guided-warning">
        Single-replica optimizer results are exploratory. Verify with robustness before deployment.
      </div>
    </div>

    <div class="decision-guided-subsection">
      <h4>Cost config</h4>

      <div class="decision-toolbar">
        <button id="opt-cost-template-btn" type="button">
          Load cost config template
        </button>
      </div>

      <label class="field">
        Cost config JSON
        <textarea id="opt-cost-config" rows="8" placeholder='{
  "robot_opex_per_hour": 12.5,
  "charger_infra_cost_per_hour": 2.0,
  "downtime_cost_per_hour": 30.0,
  "sla_target_ticks": 300,
  "sla_penalty_per_late_tick": 0.5,
  "currency": "USD"
}'></textarea>
      </label>

      <div class="decision-guided-warning">
        Required when objective is cost_per_task.
      </div>
    </div>

    <div class="decision-guided-subsection">
      <h4>Constraints</h4>

      <label class="field">
        p95_cycle_time_max
        <input id="opt-constraint-p95-max" type="number" step="any" min="0" placeholder="60">
      </label>

      <label class="field">
        sla_compliance_rate_min
        <input id="opt-constraint-sla-min" type="number" step="0.01" min="0" max="1" placeholder="0.95">
      </label>

      <div class="decision-guided-warning">
        Leave a constraint blank to omit it.
      </div>
    </div>

    ${renderGuidedSearchSpaceSection("opt")}

    ${renderGuidedExecutionSection("opt", false)}
  `;

  populateJobRunSelect(container.querySelector("#opt-run-id"));

  const sourceTypeEl = container.querySelector("#opt-source-type");
  const runFieldEl = container.querySelector("#opt-source-run-field");
  const configFieldEl = container.querySelector("#opt-source-config-field");

  function updateSourceVisibility() {
    const sourceType = sourceTypeEl.value;

    runFieldEl.hidden = sourceType !== "from_run_id";
    configFieldEl.hidden = sourceType !== "base_config";
  }

  sourceTypeEl.addEventListener("change", updateSourceVisibility);
  updateSourceVisibility();

  const objectiveEl = container.querySelector("#opt-objective");
  const directionEl = container.querySelector("#opt-direction");

  objectiveEl.addEventListener("change", () => {
    directionEl.value = defaultDirectionForMetric(objectiveEl.value);
  });

  container.querySelector("#opt-cost-template-btn").addEventListener("click", () => {
    container.querySelector("#opt-cost-config").value = JSON.stringify(
      getCostConfigTemplateObject(),
      null,
      2
    );
  });
}

function buildOptimizerGuidedConfig() {
  const sourceType = document.getElementById("opt-source-type").value;

  const config = {};

  if (sourceType === "from_run_id") {
    const runId = document.getElementById("opt-run-id").value;

    if (!runId) {
      throw new Error("Select a source run.");
    }

    config.from_run_id = runId;
  } else {
    config.base_config = parseGuidedJsonObject("opt-base-config", {});
  }

  const objective = document.getElementById("opt-objective").value;
  const direction = document.getElementById("opt-direction").value;

  if (!supportedObjectiveMetrics().includes(objective)) {
    throw new Error("Unsupported optimizer objective.");
  }

  if (direction !== "minimize" && direction !== "maximize") {
    throw new Error("Direction must be minimize or maximize.");
  }

  config.objective = objective;
  config.direction = direction;
  config.n_trials = guidedRequiredInteger("opt-n-trials", 1);
  config.reps = guidedRequiredInteger("opt-reps", 1);

  const baseSeed = guidedOptionalInteger("opt-base-seed", null);

  if (baseSeed !== null) {
    config.base_seed = baseSeed;
  }

  const slaTargetTicks = guidedOptionalInteger("opt-sla-target-ticks", 1);

  if (slaTargetTicks !== null) {
    config.sla_target_ticks = slaTargetTicks;
  }

  const costConfig = parseGuidedCostConfig("opt-cost-config");

  if (objective === "cost_per_task" && costConfig === null) {
    throw new Error("cost_per_task objective requires a valid cost config.");
  }

  if (costConfig !== null) {
    config.cost_config = costConfig;
  }

  config.constraints = buildGuidedCommonConstraints("opt");
  config.search_space = buildGuidedSearchSpace("opt");
  Object.assign(config, buildGuidedExecutionConfig("opt"));

  return config;
}

// =====================================================================
// Multi-objective guided form
// =====================================================================

function addMultiobjectiveObjectiveRow(container, metric, direction) {
  const rowsEl = container.querySelector("#mo-objective-rows");
  if (!rowsEl) return;

  const row = document.createElement("div");
  row.className = "decision-guided-row mo-objective-row";

  row.innerHTML = `
    <label class="field">
      Metric
      <select class="mo-objective-metric">
        ${metricOptionsHtml(metric)}
      </select>
    </label>

    <label class="field">
      Direction
      <select class="mo-objective-direction">
        <option value="minimize" ${direction === "minimize" ? "selected" : ""}>
          minimize
        </option>

        <option value="maximize" ${direction === "maximize" ? "selected" : ""}>
          maximize
        </option>
      </select>
    </label>

    <button type="button" class="mo-remove-objective-btn">Remove</button>
  `;

  const metricEl = row.querySelector(".mo-objective-metric");
  const directionEl = row.querySelector(".mo-objective-direction");

  metricEl.addEventListener("change", () => {
    directionEl.value = defaultDirectionForMetric(metricEl.value);
  });

  row.querySelector(".mo-remove-objective-btn").addEventListener("click", () => {
    row.remove();
  });

  rowsEl.appendChild(row);
}

function renderMultiobjectiveGuidedForm(container) {
  container.innerHTML = `
    <div class="decision-guided-subsection">
      <h4>Source</h4>

      <label class="field">
        Source type
        <select id="mo-source-type">
          <option value="from_run_id" selected>Existing run</option>
          <option value="base_config">Base config JSON</option>
        </select>
      </label>

      <div id="mo-source-run-field" class="field">
        Run
        <select id="mo-run-id"></select>
      </div>

      <div id="mo-source-config-field" class="field" hidden>
        Base config JSON
        <textarea id="mo-base-config" rows="8" placeholder='{
  "seed": 42,
  "num_robots": 6,
  "stop_mode": "workload",
  "target_tasks": 100,
  "max_ticks": 100000
}'></textarea>
      </div>
    </div>

    <div class="decision-guided-subsection">
      <h4>Multi-objective settings</h4>

      <label class="field">
        Trials
        <input id="mo-n-trials" type="number" min="1" step="1" value="2">
      </label>

      <label class="field">
        Reps
        <input id="mo-reps" type="number" min="1" step="1" value="1">
      </label>

      <label class="field">
        Base seed
        <input id="mo-base-seed" type="number" step="1" value="42">
      </label>

      <label class="field">
        Population size, optional
        <input id="mo-population-size" type="number" min="1" step="1" placeholder="NSGA-II population size">
      </label>

      <label class="field">
        SLA target ticks, optional
        <input id="mo-sla-target-ticks" type="number" min="1" step="1" placeholder="300">
      </label>

      <div class="decision-guided-warning">
        Pareto candidates are not deployable until verified by robustness.
      </div>
    </div>

    <div class="decision-guided-subsection">
      <h4>Objectives</h4>

      <div id="mo-objective-rows"></div>

      <div class="decision-toolbar">
        <button id="mo-add-objective-btn" type="button">
          Add objective
        </button>
      </div>

      <div class="decision-guided-warning">
        At least two objectives are required.
      </div>
    </div>

    <div class="decision-guided-subsection">
      <h4>Cost config</h4>

      <div class="decision-toolbar">
        <button id="mo-cost-template-btn" type="button">
          Load cost config template
        </button>
      </div>

      <label class="field">
        Cost config JSON
        <textarea id="mo-cost-config" rows="8" placeholder='{
  "robot_opex_per_hour": 12.5,
  "charger_infra_cost_per_hour": 2.0,
  "downtime_cost_per_hour": 30.0,
  "sla_target_ticks": 300,
  "sla_penalty_per_late_tick": 0.5,
  "currency": "USD"
}'></textarea>
      </label>

      <div class="decision-guided-warning">
        Required when any objective is cost_per_task.
      </div>
    </div>

    <div class="decision-guided-subsection">
      <h4>Constraints</h4>

      <label class="field">
        p95_cycle_time_max
        <input id="mo-constraint-p95-max" type="number" step="any" min="0" placeholder="60">
      </label>

      <label class="field">
        sla_compliance_rate_min
        <input id="mo-constraint-sla-min" type="number" step="0.01" min="0" max="1" placeholder="0.95">
      </label>

      <div class="decision-guided-warning">
        Leave a constraint blank to omit it.
      </div>
    </div>

    ${renderGuidedSearchSpaceSection("mo")}

    ${renderGuidedExecutionSection("mo", false)}
  `;

  populateJobRunSelect(container.querySelector("#mo-run-id"));

  const sourceTypeEl = container.querySelector("#mo-source-type");
  const runFieldEl = container.querySelector("#mo-source-run-field");
  const configFieldEl = container.querySelector("#mo-source-config-field");

  function updateSourceVisibility() {
    const sourceType = sourceTypeEl.value;

    runFieldEl.hidden = sourceType !== "from_run_id";
    configFieldEl.hidden = sourceType !== "base_config";
  }

  sourceTypeEl.addEventListener("change", updateSourceVisibility);
  updateSourceVisibility();

  addMultiobjectiveObjectiveRow(
    container,
    "p95_cycle_time",
    "minimize"
  );

  addMultiobjectiveObjectiveRow(
    container,
    "average_throughput",
    "maximize"
  );

  container.querySelector("#mo-add-objective-btn").addEventListener("click", () => {
    addMultiobjectiveObjectiveRow(
      container,
      "average_cycle_time",
      "minimize"
    );
  });

  container.querySelector("#mo-cost-template-btn").addEventListener("click", () => {
    container.querySelector("#mo-cost-config").value = JSON.stringify(
      getCostConfigTemplateObject(),
      null,
      2
    );
  });
}

function buildMultiobjectiveObjectives() {
  const rows = Array.from(
    document.querySelectorAll("#mo-objective-rows .mo-objective-row")
  );

  if (rows.length < 2) {
    throw new Error("Multi-objective optimization requires at least two objectives.");
  }

  return rows.map((row, index) => {
    const metric = row.querySelector(".mo-objective-metric").value;
    const direction = row.querySelector(".mo-objective-direction").value;

    if (!supportedObjectiveMetrics().includes(metric)) {
      throw new Error(`Objective ${index + 1} uses an unsupported metric.`);
    }

    if (direction !== "minimize" && direction !== "maximize") {
      throw new Error(`Objective ${index + 1} direction must be minimize or maximize.`);
    }

    return {
      metric,
      direction
    };
  });
}

function buildMultiobjectiveGuidedConfig() {
  const sourceType = document.getElementById("mo-source-type").value;

  const config = {};

  if (sourceType === "from_run_id") {
    const runId = document.getElementById("mo-run-id").value;

    if (!runId) {
      throw new Error("Select a source run.");
    }

    config.from_run_id = runId;
  } else {
    config.base_config = parseGuidedJsonObject("mo-base-config", {});
  }

  config.objectives = buildMultiobjectiveObjectives();
  config.n_trials = guidedRequiredInteger("mo-n-trials", 1);
  config.reps = guidedRequiredInteger("mo-reps", 1);

  const baseSeed = guidedOptionalInteger("mo-base-seed", null);

  if (baseSeed !== null) {
    config.base_seed = baseSeed;
  }

  const populationSize = guidedOptionalInteger("mo-population-size", 1);

  if (populationSize !== null) {
    config.population_size = populationSize;
  }

  const slaTargetTicks = guidedOptionalInteger("mo-sla-target-ticks", 1);

  if (slaTargetTicks !== null) {
    config.sla_target_ticks = slaTargetTicks;
  }

  const costConfig = parseGuidedCostConfig("mo-cost-config");

  const usesCostObjective = config.objectives.some(
    objective => objective.metric === "cost_per_task"
  );

  if (usesCostObjective && costConfig === null) {
    throw new Error("cost_per_task objective requires a valid cost config.");
  }

  if (costConfig !== null) {
    config.cost_config = costConfig;
  }

  config.constraints = buildGuidedCommonConstraints("mo");
  config.search_space = buildGuidedSearchSpace("mo");
  Object.assign(config, buildGuidedExecutionConfig("mo"));

  return config;
}

// =====================================================================
// Robustness guided form
// =====================================================================

async function populateMultiobjectiveDatalist(datalistEl) {
  if (!datalistEl) return;

  datalistEl.innerHTML = "";

  try {
    const data = await decisionFetchJson("/api/decision/multiobjective");
    const items = data.multiobjective || [];

    items.forEach(item => {
      const option = document.createElement("option");
      option.value = item.study_id;
      datalistEl.appendChild(option);
    });
  } catch (error) {
    console.error("Could not load multi-objective study ids:", error);
  }
}

function buildRobustnessCandidates() {
  const candidates = parseGuidedJsonArray("rob-candidates-json", []);

  if (!candidates.length) {
    throw new Error("At least one candidate is required.");
  }

  return candidates.map((candidate, index) => {
    if (
      candidate === null ||
      typeof candidate !== "object" ||
      Array.isArray(candidate)
    ) {
      throw new Error(`candidates[${index}] must be a JSON object.`);
    }

    const label = candidate.label;

    if (!label || typeof label !== "string" || !label.trim()) {
      throw new Error(`candidates[${index}].label is required.`);
    }

    const overrides = candidate.overrides;

    if (
      overrides === null ||
      typeof overrides !== "object" ||
      Array.isArray(overrides)
    ) {
      throw new Error(`candidates[${index}].overrides must be a JSON object.`);
    }

    return {
      label: label.trim(),
      overrides
    };
  });
}

function renderRobustnessGuidedForm(container) {
  container.innerHTML = `
    <div class="decision-guided-subsection">
      <h4>Candidate source</h4>

      <label class="field">
        Source type
        <select id="rob-source-type">
          <option value="from_multiobjective_id" selected>Multi-objective study</option>
          <option value="explicit_candidates">Explicit candidates JSON</option>
        </select>
      </label>

      <div id="rob-source-multiobjective-field" class="field">
        Multi-objective study ID
        <input id="rob-from-mo-id" type="text" list="rob-mo-options" placeholder="multiobjective study id">
        <datalist id="rob-mo-options"></datalist>
      </div>

      <div id="rob-source-multiobjective-extra" class="field">
        Max candidates
        <input id="rob-max-candidates" type="number" min="1" step="1" value="3">
      </div>

      <div id="rob-source-candidates-field" class="field" hidden>
        Candidates JSON
        <textarea id="rob-candidates-json" rows="8" placeholder='[
  {
    "label": "candidate-1",
    "overrides": {
      "num_robots": 8,
      "charger_capacity": 4
    }
  }
]'></textarea>
      </div>
    </div>

    <div class="decision-guided-subsection">
      <h4>Robustness settings</h4>

      <label class="field">
        Reps
        <input id="rob-reps" type="number" min="1" step="1" value="20">
      </label>

      <div id="rob-reps-warning" class="decision-guided-warning" hidden>
        reps below 20 is not recommended for deployment decisions.
      </div>

      <label class="field">
        Base seed
        <input id="rob-base-seed" type="number" step="1" value="123">
      </label>

      <label class="field">
        Objective
        <select id="rob-objective">
          ${metricOptionsHtml("p95_cycle_time")}
        </select>
      </label>

      <label class="field">
        Direction
        <select id="rob-direction">
          <option value="minimize" selected>minimize</option>
          <option value="maximize">maximize</option>
        </select>
      </label>

      <label class="field">
        Min pass probability
        <input id="rob-min-pass-probability" type="number" step="0.01" min="0" max="1" value="0.90">
      </label>

      <label class="field">
        SLA target ticks, optional
        <input id="rob-sla-target-ticks" type="number" min="1" step="1" placeholder="300">
      </label>

      <div class="decision-guided-warning">
        Robustness verification is the deployability gate.
      </div>
    </div>

    <div class="decision-guided-subsection">
      <h4>Cost config</h4>

      <div class="decision-toolbar">
        <button id="rob-cost-template-btn" type="button">
          Load cost config template
        </button>
      </div>

      <label class="field">
        Cost config JSON
        <textarea id="rob-cost-config" rows="8" placeholder='{
  "robot_opex_per_hour": 12.5,
  "charger_infra_cost_per_hour": 2.0,
  "downtime_cost_per_hour": 30.0,
  "sla_target_ticks": 300,
  "sla_penalty_per_late_tick": 0.5,
  "currency": "USD"
}'></textarea>
      </label>

      <div class="decision-guided-warning">
        Required when objective is cost_per_task.
      </div>
    </div>

    <div class="decision-guided-subsection">
      <h4>Constraints</h4>

      <label class="field">
        p95_cycle_time_max
        <input id="rob-constraint-p95-max" type="number" step="any" min="0" placeholder="60">
      </label>

      <label class="field">
        sla_compliance_rate_min
        <input id="rob-constraint-sla-min" type="number" step="0.01" min="0" max="1" placeholder="0.95">
      </label>

      <div class="decision-guided-warning">
        Leave a constraint blank to omit it.
      </div>
    </div>

    ${renderGuidedExecutionSection("rob")}
  `;

  populateMultiobjectiveDatalist(container.querySelector("#rob-mo-options"));

  const sourceTypeEl = container.querySelector("#rob-source-type");
  const multiobjectiveFieldEl = container.querySelector("#rob-source-multiobjective-field");
  const multiobjectiveExtraEl = container.querySelector("#rob-source-multiobjective-extra");
  const candidatesFieldEl = container.querySelector("#rob-source-candidates-field");

  function updateSourceVisibility() {
    const sourceType = sourceTypeEl.value;

    const fromMultiobjective = sourceType === "from_multiobjective_id";

    multiobjectiveFieldEl.hidden = !fromMultiobjective;
    multiobjectiveExtraEl.hidden = !fromMultiobjective;
    candidatesFieldEl.hidden = sourceType !== "explicit_candidates";
  }

  sourceTypeEl.addEventListener("change", updateSourceVisibility);
  updateSourceVisibility();

  const objectiveEl = container.querySelector("#rob-objective");
  const directionEl = container.querySelector("#rob-direction");

  objectiveEl.addEventListener("change", () => {
    directionEl.value = defaultDirectionForMetric(objectiveEl.value);
  });

  const repsEl = container.querySelector("#rob-reps");
  const repsWarningEl = container.querySelector("#rob-reps-warning");

  function updateRepsWarning() {
    const reps = Number(repsEl.value);

    repsWarningEl.hidden = Number.isFinite(reps) && reps >= 20;
  }

  repsEl.addEventListener("input", updateRepsWarning);
  updateRepsWarning();

  container.querySelector("#rob-cost-template-btn").addEventListener("click", () => {
    container.querySelector("#rob-cost-config").value = JSON.stringify(
      getCostConfigTemplateObject(),
      null,
      2
    );
  });
}

function buildRobustnessGuidedConfig() {
  const sourceType = document.getElementById("rob-source-type").value;

  const config = {};

  if (sourceType === "from_multiobjective_id") {
    const multiobjectiveStudyId = document.getElementById("rob-from-mo-id").value.trim();

    if (!multiobjectiveStudyId) {
      throw new Error("Enter a multi-objective study id.");
    }

    config.from_multiobjective_id = multiobjectiveStudyId;

    const maxCandidates = guidedOptionalInteger("rob-max-candidates", 1);

    if (maxCandidates !== null) {
      config.max_candidates = maxCandidates;
    }
  } else {
    config.candidates = buildRobustnessCandidates();
  }

  config.reps = guidedRequiredInteger("rob-reps", 1);

  const baseSeed = guidedOptionalInteger("rob-base-seed", null);

  if (baseSeed !== null) {
    config.base_seed = baseSeed;
  }

  const objective = document.getElementById("rob-objective").value;
  const direction = document.getElementById("rob-direction").value;

  if (!supportedObjectiveMetrics().includes(objective)) {
    throw new Error("Unsupported robustness objective.");
  }

  if (direction !== "minimize" && direction !== "maximize") {
    throw new Error("Direction must be minimize or maximize.");
  }

  config.objective = objective;
  config.direction = direction;

  config.min_pass_probability = guidedRequiredNumber(
    "rob-min-pass-probability",
    0,
    1
  );

  const slaTargetTicks = guidedOptionalInteger("rob-sla-target-ticks", 1);

  if (slaTargetTicks !== null) {
    config.sla_target_ticks = slaTargetTicks;
  }

  const costConfig = parseGuidedCostConfig("rob-cost-config");

  if (objective === "cost_per_task" && costConfig === null) {
    throw new Error("cost_per_task objective requires a valid cost config.");
  }

  if (costConfig !== null) {
    config.cost_config = costConfig;
  }

  config.constraints = buildGuidedCommonConstraints("rob");
  Object.assign(config, buildGuidedExecutionConfig("rob"));

  return config;
}

// =====================================================================
// Study guided form
// =====================================================================

function renderStudyGuidedForm(container) {
  const factorOptions = commonFactorOptions()
    .map(name => `<option value="${escapeHtml(name)}">`)
    .join("");

  container.innerHTML = `
    <datalist id="study-factor-options">
      ${factorOptions}
    </datalist>

    <div class="decision-guided-subsection">
      <h4>Source</h4>

      <label class="field">
        Source type
        <select id="study-source-type">
          <option value="from_run_id" selected>Existing run</option>
          <option value="base_config">Base config JSON</option>
        </select>
      </label>

      <div id="study-source-run-field" class="field">
        Run
        <select id="study-run-id"></select>
      </div>

      <div id="study-source-config-field" class="field" hidden>
        Base config JSON
        <textarea id="study-base-config" rows="8" placeholder='{
  "seed": 42,
  "num_robots": 6,
  "stop_mode": "workload",
  "target_tasks": 100,
  "max_ticks": 100000
}'></textarea>
      </div>
    </div>

    <div class="decision-guided-subsection">
      <h4>Study factors</h4>

      <div id="study-factor-rows"></div>

      <div class="decision-toolbar">
        <button id="study-add-factor-btn" type="button">
          Add factor
        </button>
      </div>

      <div class="decision-guided-warning">
        Values are comma-separated. Numeric values are converted automatically.
        Example: 4, 6, 8
      </div>

      <div class="decision-guided-warning">
        Large factorial designs can create many runs.
      </div>
    </div>

    ${renderGuidedExecutionSection("study", false)}
  `;

  populateJobRunSelect(container.querySelector("#study-run-id"));

  const sourceTypeEl = container.querySelector("#study-source-type");
  const runFieldEl = container.querySelector("#study-source-run-field");
  const configFieldEl = container.querySelector("#study-source-config-field");

  function updateSourceVisibility() {
    const sourceType = sourceTypeEl.value;

    runFieldEl.hidden = sourceType !== "from_run_id";
    configFieldEl.hidden = sourceType !== "base_config";
  }

  sourceTypeEl.addEventListener("change", updateSourceVisibility);
  updateSourceVisibility();

  const factorRowsEl = container.querySelector("#study-factor-rows");

  container.querySelector("#study-add-factor-btn").addEventListener("click", () => {
    addGuidedFactorRow(factorRowsEl, "study-factor-options");
  });

  addGuidedFactorRow(factorRowsEl, "study-factor-options");
}

function buildStudyGuidedConfig() {
  const sourceType = document.getElementById("study-source-type").value;

  const config = {};

  if (sourceType === "from_run_id") {
    const runId = document.getElementById("study-run-id").value;

    if (!runId) {
      throw new Error("Select a source run.");
    }

    config.from_run_id = runId;
  } else {
    config.base_config = parseGuidedJsonObject("study-base-config", {});
  }

  config.factors = buildGuidedFactors(
    document.getElementById("study-factor-rows")
  );

  return config;
}

// =====================================================================
// Override job modal open behavior
// =====================================================================

function openJobModal(moduleOrEvent = null, configObject = null) {
  const modal = document.getElementById("decision-job-modal");
  const moduleEl = document.getElementById("decision-job-module");
  const editor = document.getElementById("decision-job-config-editor");
  const errorEl = document.getElementById("decision-job-error");
  const guidedCheckbox = document.getElementById("decision-job-use-guided");

  if (!modal || !moduleEl || !editor) return;

  let module = null;

  if (typeof moduleOrEvent === "string" && moduleOrEvent) {
    module = moduleOrEvent;
  } else if (moduleEl.value) {
    module = moduleEl.value;
  } else {
    module = "monte_carlo";
  }

  moduleEl.value = module;

  if (errorEl) {
    errorEl.hidden = true;
    errorEl.textContent = "";
  }

  clearJobGuidedError();

  if (configObject) {
    if (guidedCheckbox) {
      guidedCheckbox.checked = false;
    }

    editor.value = JSON.stringify(configObject, null, 2);
  } else {
    if (guidedCheckbox) {
      guidedCheckbox.checked = true;
    }

    renderGuidedJobForm(module);
  }

  updateJobGuidedVisibility();

  modal.hidden = false;
}

// =====================================================================
// Override job submission behavior
// =====================================================================

async function submitJob() {
  const module = document.getElementById("decision-job-module").value;
  const editor = document.getElementById("decision-job-config-editor");
  const errorEl = document.getElementById("decision-job-error");

  clearJobGuidedError();

  let config;

  try {
    if (isGuidedJobFormEnabled()) {
      config = buildGuidedJobConfig(module);
    } else {
      config = JSON.parse(editor.value);
    }

    if (config === null || typeof config !== "object" || Array.isArray(config)) {
      throw new Error("Job config must be a JSON object.");
    }
  } catch (error) {
    setJobGuidedError(error.message);

    if (errorEl) {
      errorEl.textContent = error.message;
      errorEl.hidden = false;
    }

    return;
  }

  if (errorEl) {
    errorEl.hidden = true;
  }

  try {
    const res = await fetch("/api/decision/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ module, config })
    });

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.error || "Failed to submit job.");
    }

    closeJobModal();
    loadDecisionJobs();
  } catch (error) {
    setJobGuidedError(error.message);

    if (errorEl) {
      errorEl.textContent = error.message;
      errorEl.hidden = false;
    }
  }
}