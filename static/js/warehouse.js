// =====================================================================
// Warehouse map rendering
// =====================================================================

function staticWarehouseKey(warehouse) {
    return JSON.stringify({
        width: warehouse?.width ?? 0,
        height: warehouse?.height ?? 0,
        layout: warehouse?.layout ?? [],
        racks: warehouse?.racks ?? {}
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

        el.classList.remove("has-task", "task-putaway", "task-pick", "task-pack", "task-ship",
            "low-battery", "to-charger", "waiting-for-charger", "charging", "failed");

        const mode = safeString(robot.mode);
        const battery = typeof robot.battery === "number" ? robot.battery : null;

        if (mode === "To charger") el.classList.add("to-charger");
        else if (mode === "Waiting for charger") el.classList.add("waiting-for-charger");
        else if (mode === "Charging") el.classList.add("charging");
        else if (mode === "Failed" || mode === "Repairing") el.classList.add("failed");

        if (battery !== null && battery <= 20) el.classList.add("low-battery");

        const task = robot.currentTaskId ? tasksById.get(robot.currentTaskId) : null;
        const batteryText = battery !== null ? `| battery ${battery.toFixed(1)}` : "";
        const modeText = mode && mode !== "Idle" && mode !== "Moving" ? `| ${mode}` : "";

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
        if (!seen.has(id)) { robotElements[id].remove(); delete robotElements[id]; }
    });
}

function updateTaskHighlights(state) {
    document.querySelectorAll(".task-pickup-active, .task-dropoff-active, .task-pickup-faint, .task-dropoff-faint")
        .forEach(el => el.classList.remove("task-pickup-active", "task-dropoff-active", "task-pickup-faint", "task-dropoff-faint"));

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
        ["Downtime", toNumber(metrics.failureDowntimeSeconds).toFixed(1), "secs"]
    ];

    cards.forEach(([title, value, detail]) => {
        dashboardGridEl.appendChild(createMetricCard(title, value, detail));
    });

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