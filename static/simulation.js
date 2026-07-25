const CELL_SIZE = 32;
const POLL_INTERVAL_MS = 300;

const warehouseEl = document.getElementById("warehouse");
const dashboardGridEl = document.getElementById("dashboard-grid");
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

    updateRobots(state.robots, state.tasks);
    updateTaskHighlights(state);
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
    cell.dataset.x = x;
    cell.dataset.y = y;
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

function updateRobots(robots, tasks) {
    const seen = new Set();
    const tasksById = new Map(tasks.map(task => [task.id, task]));

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

        el.classList.remove(
            "has-task",
            "task-putaway",
            "task-pick",
            "task-pack",
            "task-ship"
        );

        const task = robot.currentTaskId ? tasksById.get(robot.currentTaskId) : null;

        if (task) {
            el.classList.add("has-task");
            const taskType = (task.taskType || "").toLowerCase();

            if (taskType === "putaway") {
                el.classList.add("task-putaway");
            } else if (taskType === "pick") {
                el.classList.add("task-pick");
            } else if (taskType === "pack") {
                el.classList.add("task-pack");
            } else if (taskType === "ship") {
                el.classList.add("task-ship");
            }
            el.title = `${robot.id} | ${task.name} | ${task.pickup} → ${task.dropoff}`;
        } else {
            el.title = `${robot.id} | Idle`;
        }
    }

    for (const id of Object.keys(robotElements)) {
        if (!seen.has(id)) {
            robotElements[id].remove();
            delete robotElements[id];
        }
    }
}

function updateTaskHighlights(state) {
    document.querySelectorAll(
        ".task-pickup-active, .task-dropoff-active, .task-pickup-faint, .task-dropoff-faint"
    ).forEach(el => {
        el.classList.remove(
            "task-pickup-active",
            "task-dropoff-active",
            "task-pickup-faint",
            "task-dropoff-faint"
        );
    });

    const activeTasks = state.tasks.filter(task =>
        task.status === "Assigned" && task.assignedRobotId
    );

    for (const task of activeTasks) {
        if (task.phase === "To pickup") {
            highlightLocation(state, task.pickup, "task-pickup-active");
            highlightLocation(state, task.dropoff, "task-dropoff-faint");
        } else if (task.phase === "To dropoff") {
            highlightLocation(state, task.dropoff, "task-dropoff-active");
        }
    }
}

function highlightLocation(state, locationName, className) {
    if (!locationName) return;
    const location = state.warehouse.locations?.[locationName];
    if (!location) return;

    addTileClass(location.cell, className);
    addTileClass(location.access, className);
}

function addTileClass(coord, className) {
    if (!coord) return;
    const [x, y] = coord;
    const tileEl = document.querySelector(
        `.tile[data-x="${x}"][data-y="${y}"]`
    );
    if (tileEl) {
        tileEl.classList.add(className);
    }
}

function updateSidePanel(state) {
    const metrics = state.metrics ?? {};

    // --- Dashboard on top ---
    dashboardGridEl.innerHTML = "";
    const metricCards = [
        ["Generated", metrics.tasksGenerated ?? 0, "total"],
        ["Completed", metrics.tasksCompleted ?? 0, "tasks"],
        ["Active", state.tasks.filter(t => t.status === "Assigned").length, "robots"],
        ["Pending", state.tasks.filter(t => t.status === "Pending").length, "queue"],
        ["Throughput", (metrics.throughputPerTick ?? 0).toFixed(2), "per tick"],
        ["Avg Cycle", (metrics.averageTaskCompletionTime ?? 0).toFixed(1), "ticks"],
        ["Blocked", (metrics.blockedTimeSeconds ?? 0).toFixed(1), "secs"],
        ["Replans", metrics.replanningCount ?? 0, "events"],
    ];
    metricCards.forEach(([title, value, detail]) => {
        dashboardGridEl.appendChild(createMetricCard(title, value, detail));
    });

    // --- Tasks directly below dashboard ---
    taskListEl.innerHTML = "";

    const activeTasks = state.tasks.filter(t => t.status === "Pending" || t.status === "Assigned");
    const recentDone = state.tasks
        .filter(t => t.status === "Completed" || t.status === "Failed")
        .sort((a, b) => (b.completedAt || 0) - (a.completedAt || 0))
        .slice(0, 5);

    const activeHeader = document.createElement("h3");
    activeHeader.className = "section-header";
    activeHeader.textContent = `Active Queue (${activeTasks.length})`;
    taskListEl.appendChild(activeHeader);

    if (activeTasks.length === 0) {
        const emptyMsg = document.createElement("div");
        emptyMsg.className = "empty-msg";
        emptyMsg.textContent = "No active tasks";
        taskListEl.appendChild(emptyMsg);
    } else {
        for (const task of activeTasks) {
            taskListEl.appendChild(createTaskRow(task));
        }
    }

    const historyHeader = document.createElement("h3");
    historyHeader.className = "section-header";
    historyHeader.textContent = `Recent History (${metrics.tasksCompleted} completed)`;
    taskListEl.appendChild(historyHeader);

    if (recentDone.length === 0) {
        const emptyMsg = document.createElement("div");
        emptyMsg.className = "empty-msg";
        emptyMsg.textContent = "No completed tasks yet";
        taskListEl.appendChild(emptyMsg);
    } else {
        for (const task of recentDone) {
            taskListEl.appendChild(createTaskRow(task, true));
        }
    }
}

function createTaskRow(task, isHistory = false) {
    const row = document.createElement("div");
    row.className = `task-row ${task.status.toLowerCase()} ${isHistory ? 'history' : ''}`;

    const badge = document.createElement("span");
    badge.className = `task-badge ${(task.taskType || "legacy").toLowerCase()}`;
    badge.textContent = (task.taskType || "?").substring(0, 4);

    const info = document.createElement("div");
    info.className = "task-info";

    const title = document.createElement("div");
    title.className = "task-title";
    title.textContent = `${task.pickup} → ${task.dropoff}`;

    const sub = document.createElement("div");
    sub.className = "task-sub";
    sub.textContent = task.assignedRobotId ? `${task.assignedRobotId} • ${task.phase}` : task.status;

    info.appendChild(title);
    info.appendChild(sub);

    row.appendChild(badge);
    row.appendChild(info);

    return row;
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