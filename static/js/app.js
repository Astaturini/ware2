// =====================================================================
// Initialization and event listeners. Load last.
// =====================================================================

initViews();
showView("setup");

if (
  typeof MultiSelect === "function" &&
  document.getElementById("compare-run-select")
) {
  compareMultiSelect = new MultiSelect("compare-run-select");
}

// =====================================================================
// Experiment lifecycle
// =====================================================================

on("start-experiment-btn", "click", startExperiment);

on("pause-btn", "click", async () => {
  await fetch("/api/pause", { method: "POST" });
  refresh();
});

on("resume-btn", "click", async () => {
  await fetch("/api/resume", { method: "POST" });
  refresh();
});

on("reset-btn", "click", async () => {
  await fetch("/api/reset", { method: "POST" });

  activeRunId = null;
  robotElements = {};
  previousWarehouseKey = null;

  showView("setup");
  refresh();

  if (typeof updateResultsDecisionActionsVisibility === "function") {
    updateResultsDecisionActionsVisibility();
  }
});

on("fast-stop-btn", "click", async () => {
  await fetch("/api/experiment/stop", { method: "POST" });
  refresh();
});

// =====================================================================
// Navigation
// =====================================================================

on("nav-setup-btn", "click", () => showView("setup"));
on("nav-run-btn", "click", () => showView("run"));

on("nav-results-btn", "click", () => {
  showView("results");

  if (typeof updateResultsDecisionActionsVisibility === "function") {
    updateResultsDecisionActionsVisibility();
  }
});

on("nav-experiments-btn", "click", () => {
  loadExperiments();
  showView("experiments");
});

on("nav-visualization-btn", "click", () => {
  populateRunSelects();
  showView("visualization");
});

on("nav-analysis-btn", "click", () => {
  populateRunSelects();
  showView("analysis");
});

on("nav-compare-btn", "click", () => {
  populateRunSelects();
  showView("compare");
});

on("nav-decision-btn", "click", () => {
  populateRunSelects();
  showView("decision");
  showDecisionSubview("overview");
});

// =====================================================================
// Results shortcuts
// =====================================================================

on("run-again-btn", "click", () => showView("setup"));

on("view-experiments-btn", "click", () => {
  loadExperiments();
  showView("experiments");
});

on("view-visualization-btn", "click", () => {
  populateRunSelects();
  showView("visualization");
});

on("view-analysis-btn", "click", () => {
  populateRunSelects();
  showView("analysis");
});

on("back-to-setup-btn", "click", () => showView("setup"));

// =====================================================================
// Analysis / Visualization / Compare
// =====================================================================

on("visualization-generate-btn", "click", generateVisualization);
on("analysis-generate-btn", "click", generateAnalysis);
on("compare-generate-btn", "click", generateComparison);

// =====================================================================
// Decision subnav
// =====================================================================

on("decision-open-overview-btn", "click", () => showDecisionSubview("overview"));
on("decision-open-studies-btn", "click", () => showDecisionSubview("studies"));
on("decision-open-reports-btn", "click", () => showDecisionSubview("reports"));
on("decision-open-spatial-btn", "click", () => showDecisionSubview("spatial"));
on("decision-open-cost-btn", "click", () => showDecisionSubview("cost"));
on("decision-open-monte-carlo-btn", "click", () => showDecisionSubview("monte-carlo"));
on("decision-open-sensitivity-btn", "click", () => showDecisionSubview("sensitivity"));
on("decision-open-optimization-btn", "click", () => showDecisionSubview("optimization"));
on("decision-open-multiobjective-btn", "click", () => showDecisionSubview("multiobjective"));
on("decision-open-robustness-btn", "click", () => showDecisionSubview("robustness"));
on("decision-open-jobs-btn", "click", () => showDecisionSubview("jobs"));
on("decision-refresh-btn", "click", refreshDecision);

// =====================================================================
// Decision actions
// =====================================================================

on("spatial-generate-btn", "click", generateSpatial);
on("cost-generate-btn", "click", generateCostKpis);

// =====================================================================
// Phase 3: run-linked actions
// =====================================================================

document.addEventListener("click", async event => {
  const button = event.target.closest("[data-run-action]");
  if (!button) return;

  try {
    await handleRunLinkedAction(button);
  } catch (error) {
    console.error(error);
    alert(error && error.message ? error.message : "Run action failed.");
  }
});

// =====================================================================
// Job modal
// =====================================================================

on("decision-job-module", "change", event => {
  loadJobTemplate(event.target.value);
});

on("decision-job-template-btn", "click", () => {
  loadJobTemplate(document.getElementById("decision-job-module").value);
});

on("decision-job-submit-btn", "click", submitJob);
on("decision-job-close-btn", "click", closeJobModal);

// =====================================================================
// Setup conditional visibility
// =====================================================================

const stopModeSelect = document.getElementById("cfg-stop-mode");
const targetTasksField = document.getElementById("target-tasks-field");

function updateSetupVisibility() {
  if (!stopModeSelect || !targetTasksField) return;

  const mode = stopModeSelect.value;

  targetTasksField.style.display =
    mode === "workload" || mode === "target_tasks"
      ? "flex"
      : "none";
}

if (stopModeSelect) {
  stopModeSelect.addEventListener("change", updateSetupVisibility);
  updateSetupVisibility();
}

// =====================================================================
// Start polling
// =====================================================================

refresh();
setInterval(refresh, POLL_INTERVAL_MS);