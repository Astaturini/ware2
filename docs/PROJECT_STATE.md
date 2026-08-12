# Project State

## Project Name
warehouse_simulator

## Current Version
v0.3.0

## Git Tag
v0.3.0

## Python Version
Python 3.13+

## Dependencies
Flask only

## Run Command
python app.py

## Where The Project Is Now
- v0.3.0 turns the fixed demo into an operational warehouse: tasks are
  generated during the run, queued, scheduled centrally, executed by the
  AMRs, and measured.
- The 26×21 layout, racks A–H, 64 named storage locations, receiving,
  buffer, pick stations, consolidation, packing, staging, shipping, charging,
  and maintenance areas remain unchanged.
- Task model now includes `task_type`, `priority`, `created_at`, and
  `completed_at` while preserving the existing id/name/pickup/dropoff/status/
  phase behavior.
- Runtime architecture is split into task generation, baseline cost-based
  scheduling, pathfinding, robot motion, and metrics collection.
- Multi-robot movement is still simple, but the engine now avoids obvious cell
  conflicts by reserving occupied cells during each tick.
- Frontend keeps the warehouse map intact and adds a compact operational
  dashboard for queue, throughput, completion, waiting time, and utilization.

## Works Right Now
- 4 AMRs begin with little or no work, receive generated tasks over time, and
  complete them end-to-end.
- The task queue grows and drains during the simulation instead of being fully
  preloaded at startup.
- Pause / resume / reset still work, and the UI polls the live state every
  300 ms.
- The dashboard shows task counts, throughput, average waiting/completion
  time, and robot utilization.

## Not Implemented Yet (extension points)
- Swarm intelligence / decentralized coordination — the scheduler is still
  centralized and deterministic.
- Battery / charging behavior (CHARGING); maintenance downtime (MAINTENANCE).
- Station processing delays or queues (PICK_STATION, PACKING, CONSOLIDATION,
  BUFFER, STAGING).
- Traffic control (INTERSECTION); priority routing (MAIN_AISLE).
- Advanced congestion avoidance and deadlock recovery.
- Metrics beyond the current aggregate counts, averages, and utilization.

## Next (recommendation, not a decision)
1. v0.4.0: battery/charging plus maintenance and richer lifecycle handling.
2. v0.5.0: more advanced congestion handling and optimization experiments.