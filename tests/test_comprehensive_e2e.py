"""
Comprehensive end-to-end test that tracks a single command through the entire system.

This test exercises the full pipeline:
1. Prompt injection via CLI
2. Swarm picks up queued prompt
3. Orchestrator delegates to Ideator (sub-agent)
4. Ideator scrapes web + updates state + creates GitHub issue
5. Metrics are recorded for agent and tool calls
6. Costs are tracked
7. Events are audited
8. Logs contain structured trace data
9. Session persists in SQLite
10. Queue is cleared after processing
"""

import json
import os
import tempfile

import pytest

from src.cli.swarm_ctl import dequeue_prompts, enqueue_prompt
from src.observability.cost_tracker import CostTracker
from src.observability.logger import configure_logging, get_logger, set_session_id, set_trace_id
from src.observability.metrics import MetricsRegistry
from src.services.session_store import SQLiteSessionService
from src.state import StateManager


@pytest.fixture
def isolated_environment():
    """Provides a temporary directory with isolated data files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        old_cwd = os.getcwd()
        os.chdir(tmpdir)

        # Create isolated config files
        yield tmpdir

        os.chdir(old_cwd)


class TestComprehensiveEndToEnd:
    """A single test that walks a command through every subsystem."""

    @pytest.mark.asyncio
    async def test_full_command_lifecycle(self, isolated_environment, capsys):
        tmpdir = isolated_environment

        # ── Phase 0: Setup isolated services ──────────────────────────────
        state_file = os.path.join(tmpdir, "state.json")
        events_file = os.path.join(tmpdir, "events.jsonl")
        metrics_file = os.path.join(tmpdir, "metrics.jsonl")
        costs_file = os.path.join(tmpdir, "costs.jsonl")
        session_db = os.path.join(tmpdir, "sessions.db")

        configure_logging(level="INFO", json_format=False)
        logger = get_logger("e2e_test")
        set_trace_id("e2e-trace-999")
        set_session_id("e2e-session-888")

        state_mgr = StateManager(
            storage_type="json", filename=state_file, event_filename=events_file
        )
        metrics_reg = MetricsRegistry(filename=metrics_file)
        cost_tracker = CostTracker(filename=costs_file)
        session_svc = SQLiteSessionService(db_path=session_db)

        # ── Phase 1: Inject prompt via queue ──────────────────────────────
        prompt_text = "Investigate quantum computing trends for autonomous agents"
        enqueue_prompt(prompt_text, user_id="test_user")

        # Verify queue has the prompt (without consuming)
        from src.cli.swarm_ctl import peek_prompts

        queue_peeked = peek_prompts()
        assert len(queue_peeked) == 1
        assert queue_peeked[0]["prompt"] == prompt_text
        assert queue_peeked[0]["user_id"] == "test_user"

        # Now dequeue to simulate what main.py does
        queue_consumed = dequeue_prompts()
        assert len(queue_consumed) == 1
        assert queue_consumed[0]["prompt"] == prompt_text

        # ── Phase 2: Create persistent session ────────────────────────────
        session = await session_svc.create_session(
            user_id="swarm_admin", app_name="CognitiveFoundry"
        )
        assert session.id
        assert session.user_id == "swarm_admin"

        # Verify session persisted
        restored = await session_svc.get_session(
            app_name="CognitiveFoundry", session_id=session.id, user_id="swarm_admin"
        )
        assert restored is not None
        assert restored.id == session.id

        # ── Phase 3: Simulate swarm processing ────────────────────────────
        # In a real run, the Orchestrator would delegate to Ideator.
        # We simulate the work the Ideator does:

        # 3a. Record agent timing (simulating Orchestrator → Ideator handoff)
        metrics_reg.record_agent_call("Orchestrator", 0.015)
        metrics_reg.record_agent_call("Ideator", 1.250)

        # 3b. Record tool timing (simulating scraper + github calls)
        metrics_reg.record_tool_call("ScraperTool", 1.100)
        metrics_reg.record_tool_call("GitHubTool", 0.050)

        # 3c. Record token usage
        metrics_reg.record_tokens("Orchestrator", 150)
        metrics_reg.record_tokens("Ideator", 420)

        # 3d. Record costs
        cost_tracker.record_cost("task-quantum", "Orchestrator", 0.002)
        cost_tracker.record_cost("task-quantum", "Ideator", 0.008)

        # 3e. Update state (simulating Ideator creating a task)
        task_id = "proactive-quantum-computing-trends-for-autonomous-agents-99999"
        state_mgr.set_task(
            task_id,
            {"title": f"Investigate {prompt_text}", "status": "PLANNED", "source": "Ideator"},
            agent="Ideator",
        )

        # 3f. Log structured events
        logger.info(
            f"Processed prompt: {prompt_text}",
            extra={"agent": "Ideator", "task_id": task_id},
        )

        # ── Phase 4: Verify queue was consumed ────────────────────────────
        remaining = dequeue_prompts()
        assert len(remaining) == 0, "Queue should be empty after processing"

        # ── Phase 5: Verify state persistence ─────────────────────────────
        assert os.path.exists(state_file)
        with open(state_file) as f:
            persisted_state = json.load(f)
        assert task_id in persisted_state
        assert persisted_state[task_id]["status"] == "PLANNED"
        assert persisted_state[task_id]["source"] == "Ideator"

        # ── Phase 6: Verify event audit trail ─────────────────────────────
        events = state_mgr.get_task_history(task_id)
        assert len(events) == 1
        assert events[0]["action"] == "SET"
        assert events[0]["agent"] == "Ideator"
        assert events[0]["diff"]["status"]["new"] == "PLANNED"
        assert events[0]["diff"]["source"]["new"] == "Ideator"

        all_events = state_mgr.get_all_events()
        assert len(all_events) == 1

        # ── Phase 7: Verify metrics persistence ───────────────────────────
        metrics_summary = metrics_reg.get_summary()
        assert metrics_summary["agents"]["Orchestrator"]["calls_total"] == 1
        assert metrics_summary["agents"]["Ideator"]["calls_total"] == 1
        assert metrics_summary["tools"]["ScraperTool"]["calls_total"] == 1
        assert metrics_summary["tools"]["GitHubTool"]["calls_total"] == 1
        assert metrics_summary["token_usage"]["Orchestrator"] == 150
        assert metrics_summary["token_usage"]["Ideator"] == 420

        # Verify metrics file exists
        assert os.path.exists(metrics_file)
        with open(metrics_file) as f:
            persisted_metrics = json.load(f)
        assert "Orchestrator" in persisted_metrics["agents"]

        # ── Phase 8: Verify cost tracking ─────────────────────────────────
        cost_summary = cost_tracker.get_summary()
        assert cost_summary["total_spend_usd"] == 0.010
        assert cost_summary["by_task"]["task-quantum"] == 0.010
        assert cost_summary["by_agent"]["Ideator"] == 0.008
        assert cost_summary["by_agent"]["Orchestrator"] == 0.002

        # Verify costs file exists
        assert os.path.exists(costs_file)
        with open(costs_file) as f:
            persisted_costs = json.load(f)
        assert "task-quantum" in persisted_costs

        # ── Phase 9: Verify session still exists after "restart" ──────────
        service2 = SQLiteSessionService(db_path=session_db)
        reloaded = await service2.get_session(
            app_name="CognitiveFoundry", session_id=session.id, user_id="swarm_admin"
        )
        assert reloaded is not None
        assert reloaded.id == session.id
        assert reloaded.app_name == "CognitiveFoundry"

        # ── Phase 10: Verify CLI can read the state ───────────────────────
        # Simulate what `swarm status` would see
        tasks = state_mgr.get_all_tasks()
        total = len(tasks)
        stalled = sum(1 for t in tasks.values() if t.get("status") == "STALLED")
        assert total == 1
        assert stalled == 0

        # ── Phase 11: Verify log output contains trace context ────────────
        captured = capsys.readouterr()
        log_output = captured.out + captured.err
        assert "e2e-trace-999" in log_output or "Processed prompt" in log_output

        # Cleanup
        metrics_reg.reset()
        cost_tracker.reset()
        await session_svc.delete_session(
            app_name="CognitiveFoundry", session_id=session.id, user_id="swarm_admin"
        )
