const CELL_SIZE = 32;
const POLL_INTERVAL_MS = 300;

const warehouseEl = document.getElementById("warehouse");
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
    robotListEl.innerHTML = "";
    for (const robot of state.robots) {
        robotListEl.appendChild(createCard(robot.id, [
            ["Status", robot.status],
            ["Task", robot.currentTaskId ?? "—"],
            ["Target", robot.currentTarget ? robot.currentTarget.join(", ") : "—"],
        ]));
    }

    taskListEl.innerHTML = "";
    for (const task of state.tasks) {
        taskListEl.appendChild(createCard(task.name, [
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

pauseBtn.addEventListener("click", () => postCommand("/api/pause").then(refresh));
resumeBtn.addEventListener("click", () => postCommand("/api/resume").then(refresh));
resetBtn.addEventListener("click", () => postCommand("/api/reset").then(refresh));

refresh();
setInterval(refresh, POLL_INTERVAL_MS);