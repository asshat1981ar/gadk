"""Graph memory store using networkx with JSON persistence."""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any

import networkx as nx


class NodeType(Enum):
    AGENT = "agent"
    TASK = "task"
    OUTCOME = "outcome"
    CONCEPT = "concept"
    FILE = "file"


class GraphStore:
    """Persistent graph memory for agent workflows.

    Nodes store typed entities (agents, tasks, outcomes, concepts, files).
    Edges store relationships (executed_by, produced, depends_on, etc.).
    Persisted as JSON for hackability.
    """

    def __init__(self, persist_path: str | None = None):
        self._g = nx.DiGraph()
        self._persist_path = persist_path
        self._id_counter = 0
        if persist_path and Path(persist_path).exists():
            self.load()

    def _next_id(self) -> str:
        self._id_counter += 1
        return f"node_{self._id_counter}"

    def add_node(
        self,
        node_type: NodeType,
        name: str,
        attrs: dict[str, Any] | None = None,
    ) -> str:
        """Add a typed node and return its ID."""
        node_id = self._next_id()
        self._g.add_node(
            node_id,
            type=node_type.value,
            name=name,
            attrs=attrs or {},
        )
        return node_id

    def get_node(self, node_id: str) -> dict[str, Any]:
        """Get node attributes by ID."""
        data = self._g.nodes[node_id]
        return {"id": node_id, **data}

    def add_edge(
        self, source: str, target: str, label: str, attrs: dict[str, Any] | None = None
    ) -> None:
        """Add a labeled edge between two nodes."""
        self._g.add_edge(source, target, label=label, attrs=attrs or {})

    def edges_from(self, node_id: str) -> list[dict[str, Any]]:
        """Get all outgoing edges from a node."""
        return [
            {
                "source": u,
                "target": v,
                "label": d.get("label", ""),
                "attrs": d.get("attrs", {}),
            }
            for u, v, d in self._g.out_edges(node_id, data=True)
        ]

    def neighbors(self, node_id: str) -> list[dict[str, Any]]:
        """Get all neighboring nodes (out-edges only, for directed)."""
        result = []
        for _, v in self._g.out_edges(node_id):
            result.append(self.get_node(v))
        return result

    def save(self) -> None:
        """Serialize graph to JSON."""
        if not self._persist_path:
            return
        data = {
            "nodes": [{"id": n, **d} for n, d in self._g.nodes(data=True)],
            "edges": [{"source": u, "target": v, **d} for u, v, d in self._g.edges(data=True)],
            "id_counter": self._id_counter,
        }
        Path(self._persist_path).write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load(self) -> None:
        """Deserialize graph from JSON."""
        if not self._persist_path or not Path(self._persist_path).exists():
            return
        raw = Path(self._persist_path).read_text(encoding="utf-8").strip()
        if not raw:
            return
        data = json.loads(raw)
        self._id_counter = data.get("id_counter", 0)
        for node_data in data.get("nodes", []):
            node_id = node_data.pop("id")
            self._g.add_node(node_id, **node_data)
        for edge_data in data.get("edges", []):
            source = edge_data.pop("source")
            target = edge_data.pop("target")
            self._g.add_edge(source, target, **edge_data)

    def query_by_type(self, node_type: NodeType) -> list[dict[str, Any]]:
        """Return all nodes of a given type."""
        return [
            {"id": n, **d} for n, d in self._g.nodes(data=True) if d.get("type") == node_type.value
        ]

    def predecessors(self, node_id: str) -> list[dict[str, Any]]:
        """Get all nodes with incoming edges TO this node."""
        result = []
        for u, _ in self._g.in_edges(node_id):
            result.append(self.get_node(u))
        return result

    def query_related(
        self,
        node_id: str,
        edge_label: str | None = None,
        max_depth: int = 2,
    ) -> list[dict[str, Any]]:
        """BFS traversal from node, optionally filtering by edge label."""
        if node_id not in self._g:
            return []
        visited = {node_id}
        queue = [(node_id, 0)]
        results: list[dict[str, Any]] = []
        while queue:
            current, depth = queue.pop(0)
            if depth >= max_depth:
                continue
            for u, v, d in self._g.out_edges(current, data=True):
                if edge_label and d.get("label") != edge_label:
                    continue
                if v not in visited:
                    visited.add(v)
                    results.append(self.get_node(v))
                    queue.append((v, depth + 1))
        return results


__all__ = ["GraphStore", "NodeType"]
