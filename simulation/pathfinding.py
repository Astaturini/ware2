from collections import deque
from typing import Iterable

from .warehouse import Warehouse


def find_shortest_path(
    warehouse: Warehouse,
    start: tuple[int, int],
    goal: tuple[int, int],
    blocked_cells: Iterable[tuple[int, int]] | None = None,
) -> list[tuple[int, int]] | None:
    """Find a shortest path on the warehouse grid using BFS.

    Returns:
        A list of cells to traverse after the start cell.
        [] if start is already the goal.
        None if the goal is unreachable.
    """
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
    came_from: dict[tuple[int, int], tuple[int, int] | None] = {start: None}

    while queue:
        current = queue.popleft()

        if current == goal:
            break

        x, y = current

        # Extension point: replace BFS with A*, weighted routing,
        # or reservation-based pathfinding in later versions.
        for neighbor in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
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