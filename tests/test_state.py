import json
import os

import pytest

from src.state import StateManager


class TestStateManager:
    def test_set_and_get_task(self):
        sm = StateManager(storage_type="memory")
        sm.set_task("task-1", {"status": "PENDING", "priority": 1})
        task = sm.get_task("task-1")
        assert task["status"] == "PENDING"

    def test_json_persistence(self):
        test_json = "test_state.json"
        test_events = "test_events.jsonl"
        for f in [test_json, test_events]:
            if os.path.exists(f):
                os.remove(f)

        sm = StateManager(storage_type="json", filename=test_json, event_filename=test_events)
        sm.set_task("task-2", {"status": "COMPLETED"})

        # Reload from file
        sm2 = StateManager(storage_type="json", filename=test_json, event_filename=test_events)
        task = sm2.get_task("task-2")
        assert task["status"] == "COMPLETED"

        for f in [test_json, test_events]:
            if os.path.exists(f):
                os.remove(f)

    def test_event_audit_trail(self):
        test_json = "test_state_audit.json"
        test_events = "test_events_audit.jsonl"
        for f in [test_json, test_events]:
            if os.path.exists(f):
                os.remove(f)

        sm = StateManager(storage_type="json", filename=test_json, event_filename=test_events)
        sm.set_task("task-a", {"status": "PLANNED", "source": "Ideator"}, agent="Ideator")
        sm.set_task("task-a", {"status": "COMPLETED", "source": "Ideator"}, agent="Builder")
        sm.delete_task("task-a", agent="Pulse")

        history = sm.get_task_history("task-a")
        assert len(history) == 3
        assert history[0]["action"] == "SET"
        assert history[0]["agent"] == "Ideator"
        assert history[1]["diff"]["status"]["old"] == "PLANNED"
        assert history[1]["diff"]["status"]["new"] == "COMPLETED"
        assert history[2]["action"] == "DELETE"

        for f in [test_json, test_events]:
            if os.path.exists(f):
                os.remove(f)

    def test_get_all_events(self):
        test_json = "test_state_all.json"
        test_events = "test_events_all.jsonl"
        for f in [test_json, test_events]:
            if os.path.exists(f):
                os.remove(f)

        sm = StateManager(storage_type="json", filename=test_json, event_filename=test_events)
        sm.set_task("x", {"status": "A"}, agent="A1")
        sm.set_task("y", {"status": "B"}, agent="A2")

        events = sm.get_all_events()
        assert len(events) == 2

        for f in [test_json, test_events]:
            if os.path.exists(f):
                os.remove(f)
