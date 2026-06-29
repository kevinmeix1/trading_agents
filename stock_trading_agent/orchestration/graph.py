"""A tiny dependency-graph execution engine.

Agents are wired as nodes with explicit dependencies. The graph resolves a
topological order, runs each node, and threads a shared mutable ``state`` dict
through the run. This mirrors frameworks like LangGraph but is dependency-free,
transparent and easy to test.

The engine can execute independent nodes (those sharing the same dependency
"level") **concurrently** via a thread pool. This is a real win when nodes do
I/O-bound work such as live LLM calls, while staying *deterministic*: updates
returned by a level are merged back into the shared state in a stable,
name-sorted order regardless of the order in which threads finish.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

# A node is any callable that receives the shared state and returns a dict of
# updates to merge back into the state (or ``None``).
NodeFn = Callable[[dict[str, Any]], dict[str, Any] | None]


@dataclass
class Node:
    name: str
    fn: NodeFn
    deps: list[str] = field(default_factory=list)


class Graph:
    """A small DAG of named nodes executed in dependency order.

    Parameters
    ----------
    max_workers:
        Maximum number of nodes to run concurrently within a single dependency
        level. ``1`` (the default) preserves the original sequential behaviour;
        values ``> 1`` enable a thread pool.
    """

    def __init__(self, *, max_workers: int = 1) -> None:
        self._nodes: dict[str, Node] = {}
        self.max_workers = max(1, max_workers)

    def add(self, name: str, fn: NodeFn, deps: list[str] | None = None) -> Graph:
        if name in self._nodes:
            raise ValueError(f"Duplicate node: {name!r}")
        self._nodes[name] = Node(name=name, fn=fn, deps=list(deps or []))
        return self

    def _topo_order(self) -> list[str]:
        visited: dict[str, int] = {}  # 0=visiting, 1=done
        order: list[str] = []

        def visit(name: str, stack: tuple[str, ...]) -> None:
            state = visited.get(name)
            if state == 1:
                return
            if state == 0:
                cycle = " -> ".join((*stack, name))
                raise ValueError(f"Cycle detected: {cycle}")
            if name not in self._nodes:
                raise KeyError(f"Unknown dependency: {name!r}")
            visited[name] = 0
            for dep in self._nodes[name].deps:
                visit(dep, (*stack, name))
            visited[name] = 1
            order.append(name)

        for node_name in self._nodes:
            visit(node_name, ())
        return order

    def _levels(self) -> list[list[str]]:
        """Group nodes into dependency levels for parallel execution.

        Level ``k`` contains every node whose dependencies are all satisfied by
        levels ``< k``. Nodes within a level are mutually independent and may be
        run concurrently. The topological sort runs first so cycles / unknown
        dependencies are reported with a helpful message.
        """

        self._topo_order()  # validates the graph (raises on cycle/missing dep)
        resolved: set[str] = set()
        levels: list[list[str]] = []
        remaining = set(self._nodes)
        while remaining:
            ready = sorted(
                name
                for name in remaining
                if all(dep in resolved for dep in self._nodes[name].deps)
            )
            if not ready:  # pragma: no cover - guarded by _topo_order above
                raise ValueError("Unable to resolve graph levels (cyclic dependency).")
            levels.append(ready)
            resolved.update(ready)
            remaining.difference_update(ready)
        return levels

    def run(self, initial_state: dict[str, Any] | None = None) -> dict[str, Any]:
        state: dict[str, Any] = dict(initial_state or {})

        if self.max_workers == 1:
            for name in self._topo_order():
                updates = self._nodes[name].fn(state)
                if updates:
                    state.update(updates)
            return state

        for level in self._levels():
            if len(level) == 1:
                updates = self._nodes[level[0]].fn(state)
                if updates:
                    state.update(updates)
                continue
            with ThreadPoolExecutor(max_workers=min(self.max_workers, len(level))) as pool:
                mapped = pool.map(lambda n: self._nodes[n].fn(state), level)
                results = dict(zip(level, mapped, strict=True))
            # Merge in stable (name-sorted) order so the run is deterministic
            # regardless of thread completion order.
            for name in level:
                updates = results[name]
                if updates:
                    state.update(updates)
        return state

    @property
    def node_names(self) -> list[str]:
        return list(self._nodes)

    @property
    def levels(self) -> list[list[str]]:
        """Public, read-only view of the dependency levels (for diagnostics)."""

        return self._levels()
