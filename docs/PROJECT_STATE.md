# Project State

## Project Name

warehouse_simulator

## Current Version

v0.3.1

## Git Tag

v0.3.1

## Python Version

Python 3.13+

## Dependencies

Flask only

## Run Command

python app.py

## Where The Project Is Now

v0.3.1 keeps the v0.3.0 operational warehouse and adds a local single-robot
traffic/conflict-resolution layer, seeded task generation, task pruning, and
a reworked dashboard UI.

The 26×21 layout, racks A–H, 64 named storage locations, receiving, buffer,
pick stations, consolidation, packing, staging, shipping, charging, and
maintenance areas remain unchanged.

The task model still includes `task_type`, `priority`, `created_at`, and
`completed_at` while preserving the existing id/name/pickup/dropoff/status/
phase behavior.

Runtime architecture is split into task generation, baseline cost-based
scheduling, pathfinding, robot motion, traffic resolution, and metrics
collection.

The major change from v0.3.0 is deadlock handling. When two robots block each
other, the simulation selects one yielding robot using a deterministic
priority score and freezes the other robot's route. The yielding robot takes
local safe moves (goal-directed step, backtrack through travel history, or
escape step), then resumes normal BFS routing. This replaces the v0.3.0
behavior where blocked robots could replan in ways that recreated the same
head-on conflict.

Task generation is now seedable for reproducible runs, and completed/failed
tasks are pruned from live state so long runs stay fast.

The frontend keeps the warehouse map intact, highlights robots and task
locations on the map, and replaces the long vertical card lists with a
compact dashboard plus a scrollable task queue.

## Works Right Now

4 AMRs begin with little or no work, receive generated tasks over time, and
complete them end-to-end.

The task queue grows and drains during the simulation instead of being fully
preloaded at startup.

Pause / resume / reset still work, and the UI polls the live state every
300 ms.

The dashboard shows task counts, throughput, average waiting/completion time,
blocked time, replan counts, and robot utilization.

Blocked robots are tracked with `blockedTicks`, aggregate blocked-time
metrics, and per-robot blocked-tick metrics.

When two robots create a blocking conflict, exactly one robot is selected as
the yielder and the other robot's route is frozen.

The yielder is selected by a deterministic score: idle robots yield first,
lower task priority numbers (more urgent) yield less, and robots blocked
longer yield more.

The yielding robot uses local safe moves: a step that still reaches its
route goal if possible, otherwise a backtrack step through its travel
history, otherwise an escape step away from the blocker.

If the preferred yielder is stationary or cannot act, the simulation forces
it to yield or falls back to the blocked robot, preventing long stalemates.

Normal routing resumes immediately after a conflict clears, without waiting
for replan cooldown.

Completed and failed tasks older than 100 ticks are pruned from live state,
so the JSON payload and the UI stay small during long runs.

Task generation accepts an optional seed. With a seed, location selection is
random but reproducible; without a seed, the old deterministic round-robin
behavior is preserved. Reset re-seeds, so the same seed reproduces the same
task stream.

The map shows each robot's current task type as a colored ring (putaway
orange, pick blue, pack purple, ship green) while keeping the robot's
identity color.

Active task pickup and dropoff locations are highlighted on the map per task
phase, and highlights clear automatically when tasks complete.

The sidebar shows the metrics dashboard on top and a scrollable compact task
list below (Active Queue plus Recent History). The old per-robot card list
was removed.

## Traffic / Replanning Rules (v0.3.1)

A robot becomes eligible for conflict resolution after being blocked for
`blocked_replan_seconds` (default 0.9 s, about 3 ticks at 0.3 s).

After a yield maneuver, the robot gets a short `replan_cooldown_ticks`
(default 2) that limits repeated yielding but does not block normal route
resumption.

For each blocking pair, only one robot may replan at a time. The selected
yielder is stored in `_active_conflict_yielder`.

The non-yielding robot is frozen: its path is not replaced and it does not
start conflict replanning. It continues as soon as its next cell is free.

Yield moves must be in bounds, not shelves, not occupied, and not claimed by
another robot's immediate next target.

If the yielder's current yield step becomes blocked, it retries a different
local step after 2 blocked ticks.

If the active yielder appears inactive for too long, the blocked robot takes
over yielding.

Priority convention: lower `task.priority` value = higher urgency. The
current generator maps SHIP=0, PACK=1, PICK=2, PUTAWAY=3.

## UI / Visualization (v0.3.1)

Robot body color = robot identity. Robot ring/glow = current task type.
Tile highlight = task location.

Phase `To pickup`: strong amber highlight on the pickup cell/access, faint
green highlight on the dropoff.

Phase `To dropoff`: strong green highlight on the dropoff cell/access.

Highlights and rings are derived from `/api/state` on every poll, so they
reset automatically. No timers or manual cleanup.

Dashboard is a compact 4-column metric grid at the top of the sidebar.

Task list uses compact rows with type badges and status borders, grouped
into Active Queue and Recent History, and scrolls inside the sidebar so the
page no longer grows with the queue.

## Not Implemented Yet

Swarm intelligence / decentralized coordination — the scheduler is still
centralized and deterministic.

Battery / charging behavior (CHARGING); maintenance downtime (MAINTENANCE).

Station processing delays or queues (PICK_STATION, PACKING, CONSOLIDATION,
BUFFER, STAGING).

Formal intersection traffic control (INTERSECTION); priority routing
(MAIN_AISLE).

Reservation-based / time-windowed multi-agent pathfinding.

Congestion prediction before robots become blocked.

Metrics beyond the current aggregates, blocked time, replan counts, and
utilization.


## Next (recommendation, not a decision)

v0.4.0: battery/charging plus maintenance and richer lifecycle handling.

v0.5.0: reservation-based traffic control, intersection rules, priority
routing, and optimization experiments.