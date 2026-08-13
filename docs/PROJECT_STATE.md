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
traffic/conflict-resolution layer.

The 26×21 layout, racks A–H, 64 named storage locations, receiving, buffer,
pick stations, consolidation, packing, staging, shipping, charging, and
maintenance areas remain unchanged.

Tasks are still generated during the run, queued, scheduled centrally,
executed by AMRs, and measured.

The major change is deadlock handling. When two robots block each other, the
simulation now selects one robot as the yielding robot and freezes the other
robot's route. Only the yielding robot may temporarily replan. The yielding
robot evaluates local next moves, may backtrack through previously visited
cells, and then resumes normal BFS routing toward its task goal.

This is still not full multi-agent pathfinding or reservation-based traffic
control, but it prevents the previous failure mode where both blocked robots
replanned simultaneously and repeatedly recreated the same head-on conflict.

## Works Right Now

4 AMRs begin with little or no work, receive generated tasks over time, and
complete them end-to-end.

The task queue grows and drains during the simulation instead of being fully
preloaded at startup.

Pause / resume / reset still work, and the UI polls the live state every
300 ms.

The dashboard shows task counts, throughput, average waiting/completion time,
and robot utilization.

Blocked robots are tracked with `blockedTicks`, blocked-time metrics, and
per-robot blocked-tick metrics.

When two robots create a blocking conflict, the simulation chooses one
yielding robot using deterministic rules.

The non-yielding robot's route is frozen while the yielding robot performs a
temporary local maneuver.

The yielding robot can choose a locally safe alternative step or backtrack
toward a previously visited safe cell.

The yielding robot's temporary path does not incorrectly trigger task arrival.

When the blocked robot becomes unblocked, the conflict state is cleared and
normal routing resumes.

If a conflict remains active for too long, a watchdog swaps the yielding
robot to avoid infinite stalemates.

Metrics expose blocked time, replanning count, deadlock resolutions,
per-robot blocked ticks, and per-robot replan events.

## Traffic / Replanning Rules Added In v0.3.1

A robot becomes eligible for conflict resolution only after being blocked for
a configurable number of ticks.

For a blocking pair, only one robot may replan at a time.

The yielder is selected deterministically:

1. If one robot has no task and the other has a task, prefer the idle robot.
2. Otherwise, prefer the robot that has been blocked longer.
3. If still tied, prefer the lower robot ID.

The non-yielding robot is frozen:

- its current path is not replaced,
- it does not start a new task route because of the conflict,
- it continues normally as soon as its next cell becomes available.

The yielding robot uses local movement rules:

- the next move must be in bounds,
- the next move must not be a shelf or blocked cell,
- the next move must not be occupied,
- the next move should not immediately recreate the same conflict,
- if possible, the move should still allow reaching the current task goal,
- otherwise, the robot may backtrack through its travel history,
- as a last resort, it may choose any locally safe escape cell.

The yielding robot uses a temporary path. Temporary paths are internal and do
not change task assignment.

When the conflict is cleared, the temporary yielding state is reset and the
robot resumes normal BFS routing toward its current route goal.

## Not Implemented Yet

Swarm intelligence / decentralized coordination — the scheduler is still
centralized and deterministic.

Battery / charging behavior (`CHARGING`).

Maintenance downtime (`MAINTENANCE`).

Station processing delays or queues (`PICK_STATION`, `PACKING`,
`CONSOLIDATION`, `BUFFER`, `STAGING`).

Formal intersection traffic control (`INTERSECTION`).

Main-aisle priority routing (`MAIN_AISLE`).

Time-windowed reservations or true multi-agent pathfinding.

Advanced congestion prediction before robots become blocked.

Priority-based yielding beyond the current deterministic rules.

Metrics beyond the current aggregate counts, averages, blocked time, replan
counts, and utilization.

## Next

Recommendation, not a decision:

v0.4.0: battery/charging plus maintenance and richer lifecycle handling.

v0.5.0: stronger traffic control, intersection rules, priority routing, and
optimization experiments.