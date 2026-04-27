"""Tests for the high-level MemoryGraph API."""

import pytest

from src.memory.memory_graph import MemoryGraph, TaskOutcome
from src.memory.graph_store import NodeType


def test_record_task_execution():
    mg = MemoryGraph()
    mg.record_task(
        task_name="fix_bug_123",
        agent_name="Builder",
        outcome=TaskOutcome.SUCCESS,
        metadata={"files_changed": ["src/foo.py"]},
    )
    tasks = mg.query_tasks()
    assert len(tasks) == 1
    assert tasks[0]["name"] == "fix_bug_123"


def test_find_similar_tasks():
    mg = MemoryGraph()
    mg.record_task("implement_auth", "Builder", TaskOutcome.SUCCESS)
    mg.record_task("implement_oauth", "Builder", TaskOutcome.SUCCESS)
    mg.record_task("fix_typo", "Builder", TaskOutcome.FAILURE)

    similar = mg.find_similar("implement login system")  # "implement" is common
    assert len(similar) >= 2
    names = {t["name"] for t in similar}
    assert "implement_auth" in names
    assert "implement_oauth" in names


def test_get_agent_history():
    mg = MemoryGraph()
    mg.record_task("task_a", "Builder", TaskOutcome.SUCCESS)
    mg.record_task("task_b", "Critic", TaskOutcome.SUCCESS)
    mg.record_task("task_c", "Builder", TaskOutcome.FAILURE)

    history = mg.get_agent_history("Builder")
    assert len(history) == 2
    assert history[0]["outcome"] == "success"
    assert history[1]["outcome"] == "failure"


def test_find_similar_skips_unrelated():
    mg = MemoryGraph()
    mg.record_task("database_migrate", "Builder", TaskOutcome.SUCCESS)
    mg.record_task("ui_button", "Builder", TaskOutcome.SUCCESS)

    similar = mg.find_similar("auth system")
    assert len(similar) == 0


def test_record_task_deduplicates_agents():
    mg = MemoryGraph()
    mg.record_task("task_a", "Builder", TaskOutcome.SUCCESS)
    mg.record_task("task_b", "Builder", TaskOutcome.SUCCESS)

    from src.memory.graph_store import GraphStore
    gs = mg._store
    agents = gs.query_by_type(NodeType.AGENT)
    assert len(agents) == 1  # Only one "Builder" agent


def test_persistence():
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        mg1 = MemoryGraph(path)
        mg1.record_task("persist_test", "Builder", TaskOutcome.SUCCESS)
        mg1.save()

        mg2 = MemoryGraph(path)
        tasks = mg2.query_tasks()
        assert len(tasks) == 1
        assert tasks[0]["name"] == "persist_test"
    finally:
        os.remove(path)


def test_get_agent_history_no_agent():
    mg = MemoryGraph()
    history = mg.get_agent_history("NonExistent")
    assert history == []
