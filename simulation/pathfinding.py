from __future__ import annotations

import heapq
from collections import deque
from typing import Iterable, Protocol

from .warehouse import Warehouse


class PathPlanner(Protocol):
    """Interface for route planners.

    Return value contract:
        []       -> already at goal
        [...]    -> cells to traverse after start
        None     -> no path found
    """

    def find_path(
        self,
        warehouse: Warehouse,
        start: tuple[int, int],
        goal: tuple[int, int],
        blocked_cells: Iterable[tuple[int, int]] | None = None,
    ) -> list[tuple[int, int]] | None:
        ...


def _manhattan(
    a: tuple[int, int],
    b: tuple[int, int],
) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _reconstruct_path(
    came_from: dict[tuple[int, int], tuple[int, int] | None],
    start: tuple[int, int],
    goal: tuple[int, int],
) -> list[tuple[int, int]] | None:
    path: list[tuple[int, int]] = []
    current = goal

    while current != start:
        path.append(current)
        previous = came_from[current]

        if previous is None:
            return None

        current = previous

    path.reverse()
    return path


class BFSPathPlanner:
    """Existing v0.5 shortest-path planner."""

    def find_path(
        self,
        warehouse: Warehouse,
        start: tuple[int, int],
        goal: tuple[int, int],
        blocked_cells: Iterable[tuple[int, int]] | None = None,
    ) -> list[tuple[int, int]] | None:
        if not warehouse.in_bounds(*start) or warehouse.is_blocked(*start):
            return None

        if not warehouse.in_bounds(*goal) or warehouse.is_blocked(*goal):
            return None

        if start == goal:
            return []

        blocked = set(blocked_cells or ())
        blocked.discard(start)
        blocked.discard(goal)

        queue: deque[tuple[int, int]] = deque([start])
        came_from: dict[tuple[int, int], tuple[int, int] | None] = {
            start: None
        }

        while queue:
            current = queue.popleft()

            if current == goal:
                break

            x, y = current

            for neighbor in (
                (x + 1, y),
                (x - 1, y),
                (x, y + 1),
                (x, y - 1),
            ):
                if neighbor in came_from:
                    continue

                nx, ny = neighbor

                if not warehouse.in_bounds(nx, ny):
                    continue

                if warehouse.is_blocked(nx, ny):
                    continue

                if neighbor in blocked:
                    continue

                came_from[neighbor] = current
                queue.append(neighbor)

        if goal not in came_from:
            return None

        return _reconstruct_path(came_from, start, goal)


class AStarPathPlanner:
    """A* planner with optional weighting.

    weight = 1.0:
        Standard A* with Manhattan heuristic. On a uniform 4-connected grid,
        this returns shortest paths, like BFS, but may choose a different
        shortest path when ties exist.

    weight > 1.0:
        Weighted A*. Faster search, but paths may be suboptimal.
    """

    def __init__(self, weight: float = 1.0) -> None:
        if weight <= 0:
            raise ValueError("A* weight must be positive.")

        self._weight = float(weight)

    def find_path(
        self,
        warehouse: Warehouse,
        start: tuple[int, int],
        goal: tuple[int, int],
        blocked_cells: Iterable[tuple[int, int]] | None = None,
    ) -> list[tuple[int, int]] | None:
        if not warehouse.in_bounds(*start) or warehouse.is_blocked(*start):
            return None

        if not warehouse.in_bounds(*goal) or warehouse.is_blocked(*goal):
            return None

        if start == goal:
            return []

        blocked = set(blocked_cells or ())
        blocked.discard(start)
        blocked.discard(goal)

        came_from: dict[tuple[int, int], tuple[int, int] | None] = {
            start: None
        }

        g_score: dict[tuple[int, int], int] = {
            start: 0
        }

        counter = 0
        start_h = _manhattan(start, goal)
        start_f = g_score[start] + self._weight * start_h

        open_heap: list[tuple[float, int, int, tuple[int, int]]] = [
            (start_f, counter, g_score[start], start)
        ]
        counter += 1

        while open_heap:
            _, _, current_g, current = heapq.heappop(open_heap)

            if current_g != g_score.get(current):
                continue

            if current == goal:
                break

            x, y = current

            for neighbor in (
                (x + 1, y),
                (x - 1, y),
                (x, y + 1),
                (x, y - 1),
            ):
                nx, ny = neighbor

                if not warehouse.in_bounds(nx, ny):
                    continue

                if warehouse.is_blocked(nx, ny):
                    continue

                if neighbor in blocked:
                    continue

                tentative_g = current_g + 1

                if tentative_g < g_score.get(neighbor, float("inf")):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g

                    h = _manhattan(neighbor, goal)
                    f = tentative_g + self._weight * h

                    heapq.heappush(
                        open_heap,
                        (f, counter, tentative_g, neighbor),
                    )
                    counter += 1

        if goal not in came_from:
            return None

        return _reconstruct_path(came_from, start, goal)


_DEFAULT_BFS_PLANNER = BFSPathPlanner()


def find_shortest_path(
    warehouse: Warehouse,
    start: tuple[int, int],
    goal: tuple[int, int],
    blocked_cells: Iterable[tuple[int, int]] | None = None,
) -> list[tuple[int, int]] | None:
    """Backward-compatible helper.

    Existing modules that still import find_shortest_path will keep working.
    New code should use an injected PathPlanner instead.
    """
    return _DEFAULT_BFS_PLANNER.find_path(
        warehouse,
        start,
        goal,
        blocked_cells=blocked_cells,
    )