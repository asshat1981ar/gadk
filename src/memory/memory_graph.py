"""High-level MemoryGraph API for agent workflow memory."""

from __future__ import annotations

from enum import Enum
from typing import Any

from src.memory.graph_store import GraphStore, NodeType


class TaskOutcome(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    ABORTED = "aborted"


class MemoryGraph:
    """Agent-facing memory API backed by graph persistence.

    Provides semantic operations (record_task, find_similar, get_agent_history)
    that translate to graph traversals.
    """

    def __init__(self, graph_store: GraphStore | str | None = None):
        if graph_store is None:
            self._store = GraphStore()
        elif isinstance(graph_store, str):
            self._store = GraphStore(persist_path=graph_store)
        else:
            self._store = graph_store

    def record_task(
        self,
        task_name: str,
        agent_name: str,
        outcome: TaskOutcome,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Record a task execution and its outcome in the graph.

        Creates: Task node, Agent node, Outcome node.
        Edges: Agent→Task (executed_by), Task→Outcome (produced).
        """
        task_id = self._store.add_node(
            NodeType.TASK, task_name, attrs={"status": "completed", **(metadata or {})}
        )
        # Find or create agent node
        agent_nodes = self._store.query_by_type(NodeType.AGENT)
        agent_id = None
        for an in agent_nodes:
            if an.get("name") == agent_name:
                agent_id = an["id"]
                break
        if agent_id is None:
            agent_id = self._store.add_node(NodeType.AGENT, agent_name)

        outcome_id = self._store.add_node(
            NodeType.OUTCOME, f"outcome:{task_name}", attrs={"result": outcome.value}
        )
        self._store.add_edge(agent_id, task_id, "executed_by")
        self._store.add_edge(task_id, outcome_id, "produced")
        return task_id

    def query_tasks(self) -> list[dict[str, Any]]:
        """Return all task nodes."""
        return self._store.query_by_type(NodeType.TASK)

    def get_agent_history(self, agent_name: str) -> list[dict[str, Any]]:
        """Get all task outcomes for a given agent, most recent first."""
        # Find agent node
        agents = self._store.query_by_type(NodeType.AGENT)
        agent_id = None
        for a in agents:
            if a.get("name") == agent_name:
                agent_id = a["id"]
                break
        if not agent_id:
            return []
        # Traverse agent → task → outcome
        tasks = self._store.query_related(agent_id, edge_label="executed_by")
        results = []
        for task in tasks:
            outcomes = self._store.query_related(task["id"], edge_label="produced")
            for oc in outcomes:
                results.append({
                    "task": task["name"],
                    "outcome": oc["attrs"].get("result", "unknown"),
                })
        return results

    def find_similar(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """Keyword-based similarity search across tasks.

        Splits on non-word characters for better matching against snake_case task names.
        Placeholder for semantic retrieval (Phase 3d).
        """
        import re
        query_terms = set(t for t in re.split(r"[\W_]+", query.lower()) if t)
        tasks = self._store.query_by_type(NodeType.TASK)
        scored = []
        for task in tasks:
            name_words = set(t for t in re.split(r"[\W_]+", task.get("name", "").lower()) if t)
            score = len(query_terms & name_words)
            if score > 0:
                scored.append((score, task))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [t for _, t in scored[:max_results]]

    def save(self) -> None:
        """Persist the graph."""
        self._store.save()


__all__ = ["MemoryGraph", "TaskOutcome"]
