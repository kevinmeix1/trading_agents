"""A tiny dependency-graph execution engine.

Agents are wired as nodes with explicit dependencies. The graph resolves a
topological order, runs each node, and threads a shared mutable ``state`` dict
through the run. This mirrors frameworks like LangGraph but is dependency-free,
transparent and easy to test.
"""

from __future__ import annotations

from collections.abc import Callable
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
    """A small DAG of named nodes executed in dependency order."""

    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {}

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

    def run(self, initial_state: dict[str, Any] | None = None) -> dict[str, Any]:
        state: dict[str, Any] = dict(initial_state or {})
        for name in self._topo_order():
            updates = self._nodes[name].fn(state)
            if updates:
                state.update(updates)
        return state

    @property
    def node_names(self) -> list[str]:
        return list(self._nodes)
