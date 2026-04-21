"""Tests for the RefactorAgentNode stub (v2 components pending)."""

from __future__ import annotations

import pytest

from src.agents.refactor_agent import RefactorAgentNode


class TestRefactorAgentStub:
    """Verify the stub returns a valid response envelope."""

    def test_invoke_returns_blueprint_key(self) -> None:
        agent = RefactorAgentNode()
        result = agent.invoke({"task": "Reduce complexity in retrieval_context"})
        assert "blueprint" in result

    def test_invoke_returns_reflection_key(self) -> None:
        agent = RefactorAgentNode()
        result = agent.invoke({"task": "Reduce complexity"})
        assert "reflection" in result
        assert isinstance(result["reflection"], list)

    def test_invoke_returns_agent_key(self) -> None:
        agent = RefactorAgentNode()
        result = agent.invoke({})
        assert result.get("agent") == "refactor"

    def test_invoke_returns_pending_action(self) -> None:
        agent = RefactorAgentNode()
        result = agent.invoke({})
        assert result.get("next_action") == "pending_implementation"

    def test_invoke_includes_note(self) -> None:
        agent = RefactorAgentNode()
        result = agent.invoke({"task": "Test task"})
        assert "note" in result
        assert "awaiting v2 components" in result["note"]

    def test_invoke_with_empty_state(self) -> None:
        agent = RefactorAgentNode()
        result = agent.invoke({})
        assert isinstance(result, dict)
        assert "blueprint" in result
        assert "reflection" in result
