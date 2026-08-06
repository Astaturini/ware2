document.addEventListener("DOMContentLoaded", () => {
  const CELL_SIZE = 36;
  const POLL_INTERVAL_MS = 300;

  document.documentElement.style.setProperty("--cell-size", `${CELL_SIZE}px`);

  const warehouseEl = document.getElementById("warehouse");
  const robotListEl = document.getElementById("robot-list");
  const taskListEl = document.getElementById("task-list");
  const simulationStateEl = document.getElementById("simulation-state");

  const pauseBtn = document.getElementById("pause-btn");
  const resumeBtn = document.getElementById("resume-btn");
  const resetBtn = document.getElementById("reset-btn");

  const robotElements = new Map();

  let previousWarehouseKey = "";
  let updateInProgress = false;

  pauseBtn.addEventListener("click", async () => {
    await postCommand("/api/pause");
    await refresh();
  });

  resumeBtn.addEventListener("click", async () => {
    await postCommand("/api/resume");
    await refresh();
  });

  resetBtn.addEventListener("click", async () => {
    await postCommand("/api/reset");
    await refresh();
  });

  setInterval(refresh, POLL_INTERVAL_MS);
  refresh();

  async function refresh() {
    if (updateInProgress) {
      return;
    }

    updateInProgress = true;

    try {
      const state = await fetchState();
      render(state);
    } catch (error) {
      console.error(error);
      simulationStateEl.textContent = "Disconnected";
    } finally {
      updateInProgress = false;
    }
  }

  async function fetchState() {
    const response = await fetch("/api/state");

    if (!response.ok) {
      throw new Error(`State request failed with status ${response.status}`);
    }

    return response.json();
  }

  async function postCommand(url) {
    const response = await fetch(url, {
      method: "POST",
    });

    if (!response.ok) {
      throw new Error(`Command failed with status ${response.status}`);
    }
  }

  function render(state) {
    simulationStateEl.textContent = state.paused ? "Paused" : "Running";

    const warehouseKey = JSON.stringify(state.warehouse);

    if (warehouseKey !== previousWarehouseKey) {
      buildStaticLayer(state.warehouse);
      previousWarehouseKey = warehouseKey;
    }

    updateRobots(state.robots);
    updateSidePanel(state);
  }

  function buildStaticLayer(warehouse) {
    warehouseEl.innerHTML = "";
    robotElements.clear();

    warehouseEl.style.width = `${warehouse.width * CELL_SIZE}px`;
    warehouseEl.style.height = `${warehouse.height * CELL_SIZE}px`;

    if (Array.isArray(warehouse.layout)) {
      warehouse.layout.forEach((row, y) => {
        row.forEach((cellType, x) => {
          const cssClass = `cell tile ${cellType.toLowerCase()}`;
          addCell(x, y, cssClass);
        });
      });
    } else {
      // Fallback for the older simple warehouse format.
      for (const [x, y] of warehouse.obstacles) {
        addCell(x, y, "cell tile shelf");
      }

      addCell(warehouse.pickup[0], warehouse.pickup[1], "cell tile receiving");
      addCell(warehouse.dropoff[0], warehouse.dropoff[1], "cell tile packing");
    }

    addMarker(warehouse.pickup, "PU", "Pickup");
    addMarker(warehouse.dropoff, "DO", "Dropoff");
  }

  function addCell(x, y, className, label = "") {
    const cell = document.createElement("div");

    cell.className = className;
    cell.style.left = `${x * CELL_SIZE}px`;
    cell.style.top = `${y * CELL_SIZE}px`;
    cell.style.width = `${CELL_SIZE}px`;
    cell.style.height = `${CELL_SIZE}px`;

    if (label) {
      cell.textContent = label;
    }

    warehouseEl.appendChild(cell);
    return cell;
  }

  function addMarker([x, y], text, tooltip) {
    const marker = document.createElement("div");

    marker.className = "marker";
    marker.style.left = `${x * CELL_SIZE}px`;
    marker.style.top = `${y * CELL_SIZE}px`;
    marker.style.width = `${CELL_SIZE}px`;
    marker.style.height = `${CELL_SIZE}px`;
    marker.textContent = text;
    marker.title = tooltip;

    warehouseEl.appendChild(marker);
  }

  function updateRobots(robots) {
    const activeRobotIds = new Set();

    for (const robot of robots) {
      activeRobotIds.add(robot.id);

      let robotEl = robotElements.get(robot.id);

      if (!robotEl) {
        robotEl = document.createElement("div");
        robotEl.className = "robot";
        robotEl.textContent = robot.id;

        robotElements.set(robot.id, robotEl);
        warehouseEl.appendChild(robotEl);
      }

      robotEl.style.backgroundColor = robot.color;
      robotEl.style.left = `${robot.x * CELL_SIZE}px`;
      robotEl.style.top = `${robot.y * CELL_SIZE}px`;
      robotEl.classList.toggle("idle", robot.status === "Idle");
    }

    for (const [robotId, robotEl] of robotElements) {
      if (!activeRobotIds.has(robotId)) {
        robotEl.remove();
        robotElements.delete(robotId);
      }
    }
  }

  function updateSidePanel(state) {
    const tasksById = new Map(state.tasks.map((task) => [task.id, task]));

    robotListEl.innerHTML = "";

    for (const robot of state.robots) {
      const task = robot.currentTaskId ? tasksById.get(robot.currentTaskId) : null;

      const currentTarget = robot.currentTarget
        ? `(${robot.currentTarget[0]}, ${robot.currentTarget[1]})`
        : "-";

      const rows = [
        ["Status", robot.status],
        ["Position", `(${robot.x}, ${robot.y})`],
        ["Target", currentTarget],
        ["Task", task ? task.name : "None"],
      ];

      robotListEl.appendChild(
        createCard(robot.id, rows, `robot-${robot.status.toLowerCase()}`)
      );
    }

    taskListEl.innerHTML = "";

    for (const task of state.tasks) {
      const rows = [
        ["Status", task.status],
        ["Robot", task.assignedRobotId ?? "-"],
        ["Phase", task.phase],
        ["Pickup", `(${task.pickup[0]}, ${task.pickup[1]})`],
        ["Dropoff", `(${task.dropoff[0]}, ${task.dropoff[1]})`],
      ];

      taskListEl.appendChild(
        createCard(task.name, rows, `task-${task.status.toLowerCase()}`)
      );
    }
  }

  function createCard(title, rows, extraClass = "") {
    const card = document.createElement("div");
    card.className = `card ${extraClass}`.trim();

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
});