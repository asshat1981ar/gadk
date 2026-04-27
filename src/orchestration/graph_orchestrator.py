"""Graph-based autonomous workflow orchestrator.

Builds a LangGraph workflow when LANGGRAPH_ENABLED=true:
  plan → build → review → reflect → deliver
                          ↑          ↓
                          ← ← ← ← ← ← ←

The reflect node routes to build (rework) or deliver (success), implementing
bounded self-correction without a phase machine.

When LANGGRAPH_ENABLED=false, falls back to a pure-Python dict-based workflow
with identical semantics.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict

from src.config import Config

LANGGRAPH_AVAILABLE = False
if Config.LANGGRAPH_ENABLED:
    try:
        from langgraph.graph import END, StateGraph  # type: ignore[import]  # noqa: F401

        LANGGRAPH_AVAILABLE = True
    except ImportError:
        pass

if TYPE_CHECKING:
    from langgraph.graph import StateGraph  # noqa: F401


class AgentState(TypedDict, total=False):
    """Full agent state carried through the autonomous workflow graph."""

    task: str
    phase: str
    memory: dict[str, Any]
    reflection: list[str]
    blueprint: dict[str, Any]
    build_output: dict[str, Any]
    review_output: dict[str, Any]
    status: str  # "running" | "done" | "error"


class GraphOrchestrator:
    """Graph-based autonomous workflow orchestrator.

    Builds a LangGraph workflow when LANGGRAPH_ENABLED=true:
      plan → build → review → reflect → deliver
                              ↑          ↓
                              ← ← ← ← ← ← ←

    The reflect node routes to build (rework) or deliver (success),
    implementing bounded self-correction without a phase machine.
    """

    def build_workflow(self):
        if LANGGRAPH_AVAILABLE:
            return self._build_langgraph_workflow()
        return self._build_python_workflow()

    def _build_python_workflow(self) -> dict[str, Any]:
        """Pure-Python fallback — same node structure, no LangGraph dependency."""
        return {
            "nodes": ["plan", "build", "review", "reflect", "deliver"],
            "edges": [
                ("plan", "build"),
                ("build", "review"),
                ("review", "reflect"),
                ("reflect", "build"),  # rework edge
                ("reflect", "deliver"),  # success edge
            ],
        }

    def _build_langgraph_workflow(self):
        from langgraph.graph import StateGraph

        workflow = StateGraph(AgentState)

        # Node implementations
        def plan_node(state: AgentState) -> AgentState:
            return {
                **state,
                "phase": "PLAN",
                "blueprint": {"planned": True, "steps": []},
            }

        def build_node(state: AgentState) -> AgentState:
            return {
                **state,
                "phase": "BUILD",
                "build_output": {"built": True, "artifacts": []},
            }

        def review_node(state: AgentState) -> AgentState:
            return {
                **state,
                "phase": "REVIEW",
                "review_output": {"status": "pass"},
            }

        def reflect_node(state: AgentState) -> AgentState:
            # Route: if build succeeded AND review passed → deliver, else → build (rework)
            build_ok = state.get("build_output", {}).get("built", False)
            review_pass = state.get("review_output", {}).get("status") == "pass"
            reflection = state.get("reflection", [])
            reflection.append(f"Reflection: build_ok={build_ok}, review_pass={review_pass}")
            return {
                **state,
                "reflection": reflection,
                "status": "done" if (build_ok and review_pass) else "running",
            }

        def deliver_node(state: AgentState) -> AgentState:
            return {**state, "phase": "DELIVER", "status": "done"}

        # Add nodes
        workflow.add_node("plan", plan_node)
        workflow.add_node("build", build_node)
        workflow.add_node("review", review_node)
        workflow.add_node("reflect", reflect_node)
        workflow.add_node("deliver", deliver_node)

        # Linear edges
        workflow.set_entry_point("plan")
        workflow.add_edge("plan", "build")
        workflow.add_edge("build", "review")
        workflow.add_edge("review", "reflect")

        # Conditional: reflect → build (rework) or reflect → deliver (done)
        def should_rework(state: AgentState) -> str:
            if state.get("status") == "done":
                return "deliver"
            return "build"

        workflow.add_conditional_edges("reflect", should_rework)
        workflow.add_edge("deliver", END)

        return workflow.compile()


__all__ = ["AgentState", "GraphOrchestrator", "LANGGRAPH_AVAILABLE"]
