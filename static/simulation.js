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
        .finally(() => {
            updateInProgress = false;
        });
}

function fetchState() {
    return fetch("/api/state").then((response) => response.json());
}

function postCommand(url) {
    return fetch(url, { method: "POST" });
}

function safeString(value) {
    return value == null ? "" : String(value).trim();
}

function toNumber(value, fallback = 0) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
}

function staticWarehouseKey(warehouse) {
    /*
    v0.4 compatibility:

    The simulation may add temporary RESUME-* locations to warehouse.locations
    when a loaded task is interrupted.

    We intentionally do NOT include locations in the static warehouse key.
    Otherwise every interruption could force a full map rebuild.
    */
    return JSON.stringify({
        width: warehouse?.width ?? 0,
        height: warehouse?.height ?? 0,
        layout: warehouse?.layout ?? [],
        racks: warehouse?.racks ?? {},
    });
}

function render(state) {
    const warehouse = state.warehouse ?? {};

    const warehouseKey = staticWarehouseKey(warehouse);

    if (warehouseKey !== previousWarehouseKey) {
        buildStaticLayer(warehouse);
        previousWarehouseKey = warehouseKey;
    }

    updateRobots(state.robots ?? [], state.tasks ?? []);
    updateTaskHighlights(state);
    updateSidePanel(state);

    simulationStateEl.textContent = state.paused
        ? "Paused"
        : `Tick ${state.tick}`;
}

function buildStaticLayer(warehouse) {
    warehouseEl.innerHTML = "";

    const width = toNumber(warehouse?.width, 0);
    const height = toNumber(warehouse?.height, 0);

    warehouseEl.style.width = `${width * CELL_SIZE}px`;
    warehouseEl.style.height = `${height * CELL_SIZE}px`;

    const layout = warehouse?.layout ?? [];

    layout.forEach((row, y) => {
        row.forEach((cell, x) => {
            /*
            Defensive trim/lowercase:

            If the backend ever sends "EMPTY " or "CHARGING" instead of
            "EMPTY"/"CHARGING", the UI will still match CSS classes.
            */
            const className = safeString(cell).toLowerCase();
            addCell(x, y, className);
        });
    });

    for (const [rack, [x, y]] of Object.entries(warehouse?.racks ?? {})) {
        const label = document.createElement("div");
        label.className = "rack-label";
        label.textContent = rack;
        label.style.left = `${(toNumber(x) + 0.5) * CELL_SIZE}px`;
        label.style.top = `${(toNumber(y) + 0.5) * CELL_SIZE}px`;
        warehouseEl.appendChild(label);
    }
}

function shortLabel(name) {
    const parts = safeString(name).split("-");
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

    if (label) {
        cell.textContent = label;
    }

    warehouseEl.appendChild(cell);
}

function addMarker([x, y], text, tooltip) {
    const marker = document.createElement("div");
    marker.className = "marker";
    marker.textContent = text;
    marker.title = tooltip ?? "";
    marker.style.left = `${(toNumber(x) + 0.5) * CELL_SIZE}px`;
    marker.style.top = `${(toNumber(y) + 0.5) * CELL_SIZE}px`;
    warehouseEl.appendChild(marker);
}

function updateRobots(robots, tasks) {
    const seen = new Set();
    const tasksById = new Map(tasks.map((task) => [task.id, task]));

    for (const robot of robots) {
        seen.add(robot.id);

        let el = robotElements[robot.id];

        if (!el) {
            el = document.createElement("div");
            el.className = "robot";
            warehouseEl.appendChild(el);
            robotElements[robot.id] = el;
        }

        el.style.backgroundColor = safeString(robot.color) || "#888888";
        el.style.left = `${toNumber(robot.x) * CELL_SIZE}px`;
        el.style.top = `${toNumber(robot.y) * CELL_SIZE}px`;

        el.classList.toggle("idle", safeString(robot.status) === "Idle");

        el.classList.remove(
            "has-task",
            "task-putaway",
            "task-pick",
            "task-pack",
            "task-ship",
            "low-battery",
            "to-charger",
            "waiting-for-charger",
            "charging",
            "failed"
        );

        const mode = safeString(robot.mode);
        const battery =
            typeof robot.battery === "number" ? robot.battery : null;

        // v0.4 robot mode classes.
        if (mode === "To charger") {
            el.classList.add("to-charger");
        } else if (mode === "Waiting for charger") {
            el.classList.add("waiting-for-charger");
        } else if (mode === "Charging") {
            el.classList.add("charging");
        } else if (mode === "Failed" || mode === "Repairing") {
            el.classList.add("failed");
        }

        // v0.4 battery warning.
        if (battery !== null && battery <= 20) {
            el.classList.add("low-battery");
        }

        const task = robot.currentTaskId
            ? tasksById.get(robot.currentTaskId)
            : null;

        const batteryText =
            battery !== null ? ` | battery ${battery.toFixed(1)}` : "";

        const modeText =
            mode && mode !== "Idle" && mode !== "Moving"
                ? ` | ${mode}`
                : "";

        if (task) {
            el.classList.add("has-task");

            const taskType = safeString(task.taskType).toLowerCase();

            if (taskType === "putaway") {
                el.classList.add("task-putaway");
            } else if (taskType === "pick") {
                el.classList.add("task-pick");
            } else if (taskType === "pack") {
                el.classList.add("task-pack");
            } else if (taskType === "ship") {
                el.classList.add("task-ship");
            }

            el.title =
                `${safeString(robot.id)} | ` +
                `${safeString(task.name)} | ` +
                `${safeString(task.pickup)} → ${safeString(task.dropoff)}` +
                `${batteryText}${modeText}`;
        } else {
            const idleMode = mode || "Idle";

            el.title =
                `${safeString(robot.id)} | ${idleMode}${batteryText}`;
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
    document
        .querySelectorAll(
            ".task-pickup-active, .task-dropoff-active, .task-pickup-faint, .task-dropoff-faint"
        )
        .forEach((el) => {
            el.classList.remove(
                "task-pickup-active",
                "task-dropoff-active",
                "task-pickup-faint",
                "task-dropoff-faint"
            );
        });

    const tasks = state.tasks ?? [];
    const warehouseLocations = state.warehouse?.locations ?? {};

    const activeTasks = tasks.filter(
        (task) =>
            safeString(task.status) === "Assigned" && task.assignedRobotId
    );

    for (const task of activeTasks) {
        const phase = safeString(task.phase);

        if (phase === "To pickup") {
            highlightLocation(warehouseLocations, task.pickup, "task-pickup-active");
            highlightLocation(warehouseLocations, task.dropoff, "task-dropoff-faint");
        } else if (phase === "To dropoff") {
            highlightLocation(warehouseLocations, task.dropoff, "task-dropoff-active");
        }
    }

    /*
    Optional v0.4 behavior:

    Show interrupted tasks faintly so the user can see that work is preserved
    even though no robot is currently assigned.
    */
    const interruptedTasks = tasks.filter(
        (task) => safeString(task.status) === "Interrupted"
    );

    for (const task of interruptedTasks) {
        highlightLocation(warehouseLocations, task.pickup, "task-pickup-faint");
        highlightLocation(warehouseLocations, task.dropoff, "task-dropoff-faint");
    }
}

function highlightLocation(locations, locationName, className) {
    const name = safeString(locationName);

    if (!name) return;

    const location = locations[name];

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
    const tasks = state.tasks ?? [];

    dashboardGridEl.innerHTML = "";

    const assignedCount = tasks.filter(
        (t) => safeString(t.status) === "Assigned"
    ).length;

    const pendingCount = tasks.filter(
        (t) => safeString(t.status) === "Pending"
    ).length;

    const interruptedCount = tasks.filter(
        (t) => safeString(t.status) === "Interrupted"
    ).length;

    const averageBatteryPercent = toNumber(metrics.averageBatteryPercent, 0);
    const averageChargerWaitTicks = toNumber(metrics.averageChargerWaitTicks, 0);

    const metricCards = [
        ["Generated", metrics.tasksGenerated ?? 0, "total"],
        ["Completed", metrics.tasksCompleted ?? 0, "tasks"],
        ["Active", assignedCount, "robots"],
        ["Pending", pendingCount, "queue"],
        ["Interrupted", interruptedCount, "tasks"],
        ["Throughput", toNumber(metrics.throughputPerTick).toFixed(2), "per tick"],
        ["Avg Cycle", toNumber(metrics.averageTaskCompletionTime).toFixed(1), "ticks"],
        ["Blocked", toNumber(metrics.blockedTimeSeconds).toFixed(1), "secs"],
        ["Replans", metrics.replanningCount ?? 0, "events"],
        ["Battery", averageBatteryPercent.toFixed(1), "% avg"],
        ["Charging", metrics.chargingEvents ?? 0, "events"],
        ["Charger Wait", averageChargerWaitTicks.toFixed(1), "ticks avg"],
        ["Batt Stops", metrics.batteryTaskInterruptions ?? 0, "interrupts"],
        ["Reassigned", metrics.taskReassignments ?? 0, "tasks"],
        ["Failures", metrics.failedRobotEvents ?? 0, "robots"],
        ["Downtime", toNumber(metrics.failureDowntimeSeconds).toFixed(1), "secs"],
    ];

    metricCards.forEach(([title, value, detail]) => {
        dashboardGridEl.appendChild(createMetricCard(title, value, detail));
    });

    taskListEl.innerHTML = "";

    /*
    v0.4 compatibility:

    Interrupted tasks must remain visible in the active queue.
    They are not completed/failed; they are waiting for recovery/reassignment.
    */
    const activeTasks = tasks.filter((t) =>
        ["Pending", "Assigned", "Interrupted"].includes(safeString(t.status))
    );

    const recentDone = tasks
        .filter((t) =>
            ["Completed", "Failed"].includes(safeString(t.status))
        )
        .sort((a, b) => toNumber(b.completedAt) - toNumber(a.completedAt))
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
    historyHeader.textContent = `Recent History (${metrics.tasksCompleted ?? 0} completed)`;
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

    const statusClass = safeString(task.status).toLowerCase();

    row.className = `task-row ${statusClass} ${isHistory ? "history" : ""}`;

    const badge = document.createElement("span");
    badge.className = `task-badge ${safeString(task.taskType).toLowerCase() || "legacy"}`;
    badge.textContent = (safeString(task.taskType) || "?").substring(0, 4);

    const info = document.createElement("div");
    info.className = "task-info";

    const title = document.createElement("div");
    title.className = "task-title";
    title.textContent =
        `${safeString(task.pickup)} → ${safeString(task.dropoff)}`;

    const sub = document.createElement("div");
    sub.className = "task-sub";

    const assignedRobotId = safeString(task.assignedRobotId);
    const phase = safeString(task.phase);
    const loadState = safeString(task.loadState);

    const loadText =
        loadState && loadState.toLowerCase() !== "on shelf"
            ? ` • ${loadState}`
            : "";

    if (assignedRobotId) {
        sub.textContent = `${assignedRobotId} • ${phase}${loadText}`;
    } else {
        sub.textContent = `${safeString(task.status)}${phase ? ` • ${phase}` : ""}${loadText}`;
    }

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