import json
import os
import tempfile

import pytest

from src.cli import swarm_cli
from src.cli.swarm_ctl import (
    clear_pid,
    clear_shutdown,
    dequeue_prompts,
)
from src.observability.metrics import registry
from src.state import StateManager


class TestSwarmCli:
    def setup_method(self):
        registry.reset()
        for f in [".swarm_shutdown", "prompt_queue.jsonl", "swarm.pid", "test_state.json", "test_events.jsonl"]:
            if os.path.exists(f):
                os.remove(f)

    def teardown_method(self):
        for f in [".swarm_shutdown", "prompt_queue.jsonl", "swarm.pid", "test_state.json", "test_events.jsonl"]:
            if os.path.exists(f):
                os.remove(f)

    def test_status_no_swarm(self, capsys):
        ret = swarm_cli.main(["status"])
        assert ret == 0
        out = capsys.readouterr().out
        assert "Not running" in out or "No tasks" in out

    def test_prompt(self, capsys):
        ret = swarm_cli.main(["prompt", "Build", "a", "feature"])
        assert ret == 0
        out = capsys.readouterr().out
        assert "Prompt enqueued" in out
        entries = dequeue_prompts()
        assert len(entries) == 1
        assert entries[0]["prompt"] == "Build a feature"

    def test_prompt_empty(self, capsys):
        ret = swarm_cli.main(["prompt"])
        assert ret == 1
        out = capsys.readouterr().out
        assert "No prompt message" in out

    def test_stop(self, capsys):
        ret = swarm_cli.main(["stop"])
        assert ret == 0
        out = capsys.readouterr().out
        assert "Shutdown sentinel created" in out
        assert os.path.exists(".swarm_shutdown")

    def test_tasks_empty(self, capsys):
        ret = swarm_cli.main(["tasks", "--state-file", "test_state.json", "--events-file", "test_events.jsonl"])
        assert ret == 0
        out = capsys.readouterr().out
        # With empty state, should show no tasks message
        assert "No tasks found" in out

    def test_tasks_with_data(self, capsys):
        sm = StateManager(storage_type="json", filename="test_state.json", event_filename="test_events.jsonl")
        sm.set_task("t1", {"status": "PLANNED", "source": "Ideator"})
        sm.set_task("t2", {"status": "COMPLETED", "source": "Builder"})

        ret = swarm_cli.main(["tasks", "--state-file", "test_state.json", "--events-file", "test_events.jsonl"])
        assert ret == 0
        out = capsys.readouterr().out
        assert "t1" in out
        assert "t2" in out

    def test_tasks_filter(self, capsys):
        sm = StateManager(storage_type="json", filename="test_state.json", event_filename="test_events.jsonl")
        sm.set_task("t1", {"status": "PLANNED", "source": "Ideator"})
        sm.set_task("t2", {"status": "COMPLETED", "source": "Builder"})

        ret = swarm_cli.main(["tasks", "--status", "PLANNED", "--state-file", "test_state.json", "--events-file", "test_events.jsonl"])
        assert ret == 0
        out = capsys.readouterr().out
        assert "t1" in out
        assert "t2" not in out

    def test_metrics_empty(self, capsys):
        ret = swarm_cli.main(["metrics"])
        assert ret == 0
        out = capsys.readouterr().out
        assert "No metrics recorded yet" in out

    def test_events(self, capsys):
        sm = StateManager(storage_type="json", filename="test_state.json", event_filename="test_events.jsonl")
        sm.set_task("t1", {"status": "PLANNED"}, agent="Ideator")

        ret = swarm_cli.main(["events", "--tail", "5", "--state-file", "test_state.json", "--events-file", "test_events.jsonl"])
        assert ret == 0
        out = capsys.readouterr().out
        assert "Ideator" in out

    def test_queue_empty(self, capsys):
        ret = swarm_cli.main(["queue"])
        assert ret == 0
        out = capsys.readouterr().out
        assert "empty" in out
