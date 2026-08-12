const CELL_SIZE = 32;
const POLL_INTERVAL_MS = 300;

const warehouseEl = document.getElementById("warehouse");
const dashboardGridEl = document.getElementById("dashboard-grid");
const robotListEl = document.getElementById("robot-list");
const taskListEl = document.getElementById("task-list");
const simulationStateEl = document.getElementById("simulation-state");
const pauseBtn = document.getElementById("pause-btn");
const resumeBtn = document.getElementById("resume-btn");
const resetBtn = document.getElementById("reset-btn");

let robotElements = {};
let previousWarehouseKey = null;
let updateInProgress = false;

function refresh() {
    if (updateInProgress) return;
    updateInProgress = true;
    fetchState()
        .then(render)
        .catch(console.error)
        .finally(() => { updateInProgress = false; });
}

function fetchState() {
    return fetch("/api/state").then((response) => response.json());
}

function postCommand(url) {
    return fetch(url, { method: "POST" });
}

function render(state) {
    const warehouseKey = JSON.stringify(state.warehouse);
    if (warehouseKey !== previousWarehouseKey) {
        buildStaticLayer(state.warehouse);
        previousWarehouseKey = warehouseKey;
    }

    updateRobots(state.robots);
    updateSidePanel(state);
    simulationStateEl.textContent = state.paused ? "Paused" : `Tick ${state.tick}`;
}

function buildStaticLayer(warehouse) {
    warehouseEl.innerHTML = "";
    warehouseEl.style.width = `${warehouse.width * CELL_SIZE}px`;
    warehouseEl.style.height = `${warehouse.height * CELL_SIZE}px`;

    warehouse.layout.forEach((row, y) => {
        row.forEach((cell, x) => {
            addCell(x, y, cell.toLowerCase());
        });
    });

    // Rack labels: show the letter only, e.g. "B".
    for (const [rack, [x, y]] of Object.entries(warehouse.racks ?? {})) {
        const label = document.createElement("div");
        label.className = "rack-label";
        label.textContent = rack;
        label.style.left = `${(x + 0.5) * CELL_SIZE}px`;
        label.style.top = `${(y + 0.5) * CELL_SIZE}px`;
        warehouseEl.appendChild(label);
    }

}

function shortLabel(name) {
    const parts = name.split("-");
    return parts[0][0] + (parts[1] ?? "");
}

function addCell(x, y, className, label) {
    const cell = document.createElement("div");
    cell.className = `tile ${className}`;
    cell.style.left = `${x * CELL_SIZE}px`;
    cell.style.top = `${y * CELL_SIZE}px`;
    cell.style.width = `${CELL_SIZE}px`;
    cell.style.height = `${CELL_SIZE}px`;
    if (label) cell.textContent = label;
    warehouseEl.appendChild(cell);
}

function addMarker([x, y], text, tooltip) {
    const marker = document.createElement("div");
    marker.className = "marker";
    marker.textContent = text;
    marker.title = tooltip ?? "";
    marker.style.left = `${(x + 0.5) * CELL_SIZE}px`;
    marker.style.top = `${(y + 0.5) * CELL_SIZE}px`;
    warehouseEl.appendChild(marker);
}

function updateRobots(robots) {
    const seen = new Set();

    for (const robot of robots) {
        seen.add(robot.id);
        let el = robotElements[robot.id];
        if (!el) {
            el = document.createElement("div");
            el.className = "robot";
            warehouseEl.appendChild(el);
            robotElements[robot.id] = el;
        }
        el.style.backgroundColor = robot.color;
        el.style.left = `${robot.x * CELL_SIZE}px`;
        el.style.top = `${robot.y * CELL_SIZE}px`;
        el.classList.toggle("idle", robot.status === "Idle");
        el.title = robot.id;
    }

    for (const id of Object.keys(robotElements)) {
        if (!seen.has(id)) {
            robotElements[id].remove();
            delete robotElements[id];
        }
    }
}

function updateSidePanel(state) {
    const metrics = state.metrics ?? {};
    const taskCounts = state.tasks.reduce((counts, task) => {
        counts.total += 1;
        counts[task.status.toLowerCase()] = (counts[task.status.toLowerCase()] ?? 0) + 1;
        return counts;
    }, { total: 0, pending: 0, assigned: 0, completed: 0, failed: 0 });

    dashboardGridEl.innerHTML = "";
    const metricCards = [
        ["Generated", metrics.tasksGenerated ?? 0, "tasks"],
        ["Pending", taskCounts.pending ?? 0, "queue"],
        ["Active", taskCounts.assigned ?? 0, "in motion"],
        ["Completed", metrics.tasksCompleted ?? 0, "tasks"],
        ["Failed", metrics.tasksFailed ?? 0, "tasks"],
        ["Throughput", (metrics.throughputPerTick ?? 0).toFixed(2), "per tick"],
        ["Avg wait", (metrics.averageTaskWaitingTime ?? 0).toFixed(1), "ticks"],
        ["Avg cycle", (metrics.averageTaskCompletionTime ?? 0).toFixed(1), "ticks"],
    ];

    metricCards.forEach(([title, value, detail]) => {
        dashboardGridEl.appendChild(createMetricCard(title, value, detail));
    });

    robotListEl.innerHTML = "";
    for (const robot of state.robots) {
        const utilization = metrics.robotUtilization?.[robot.id] ?? 0;
        robotListEl.appendChild(createCard(robot.id, [
            ["Status", robot.status],
            ["Task", robot.currentTaskId ?? "—"],
            ["Target", robot.currentTarget ? robot.currentTarget.join(", ") : "—"],
            ["Utilization", `${(utilization * 100).toFixed(0)}%`],
        ]));
    }

    taskListEl.innerHTML = "";
    for (const task of state.tasks) {
        taskListEl.appendChild(createCard(task.name, [
            ["Type", task.taskType ?? "LEGACY"],
            ["From", task.pickup],
            ["To", task.dropoff],
            ["Status", task.status],
            ["Phase", task.phase],
            ["Robot", task.assignedRobotId ?? "—"],
        ], task.status === "Completed" ? "done" : ""));
    }
}

function createCard(title, rows, extraClass) {
    const card = document.createElement("div");
    card.className = `card ${extraClass ?? ""}`.trim();

    const titleEl = document.createElement("div");
    titleEl.className = "card-title";
    titleEl.textContent = title;
    card.appendChild(titleEl);

    for (const [label, value] of rows) {
        const row = document.createElement("div");
        row.className = "row";

        const labelEl = document.createElement("span");
        labelEl.className = "label";
        labelEl.textContent = label;

        const valueEl = document.createElement("span");
        valueEl.className = "value";
        valueEl.textContent = value;

        row.appendChild(labelEl);
        row.appendChild(valueEl);
        card.appendChild(row);
    }

    return card;
}

function createMetricCard(title, value, detail) {
    const card = document.createElement("div");
    card.className = "metric-card";

    const titleEl = document.createElement("div");
    titleEl.className = "metric-title";
    titleEl.textContent = title;

    const valueEl = document.createElement("div");
    valueEl.className = "metric-value";
    valueEl.textContent = value;

    const detailEl = document.createElement("div");
    detailEl.className = "metric-detail";
    detailEl.textContent = detail;

    card.appendChild(titleEl);
    card.appendChild(valueEl);
    card.appendChild(detailEl);
    return card;
}

pauseBtn.addEventListener("click", () => postCommand("/api/pause").then(refresh));
resumeBtn.addEventListener("click", () => postCommand("/api/resume").then(refresh));
resetBtn.addEventListener("click", () => postCommand("/api/reset").then(refresh));

refresh();
setInterval(refresh, POLL_INTERVAL_MS);