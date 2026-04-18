import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class StateManager:
    def __init__(self, storage_type="json", filename="state.json", event_filename="events.jsonl"):
        self.storage_type = storage_type
        self.filename = filename
        self.event_filename = event_filename
        self.data = {}
        if self.storage_type == "json" and os.path.exists(self.filename):
            with open(self.filename, "r") as f:
                try:
                    self.data = json.load(f)
                except json.JSONDecodeError:
                    self.data = {}

    def set_task(self, task_id: str, task_data: dict, agent: str = "") -> None:
        old = self.data.get(task_id, {})
        self.data[task_id] = task_data
        if self.storage_type == "json":
            with open(self.filename, "w") as f:
                json.dump(self.data, f, indent=2)
        self._append_event({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task_id": task_id,
            "agent": agent,
            "action": "SET",
            "diff": self._compute_diff(old, task_data),
        })

    def get_task(self, task_id: str) -> Optional[dict]:
        return self.data.get(task_id)

    def get_all_tasks(self) -> Dict[str, dict]:
        return dict(self.data)

    def delete_task(self, task_id: str, agent: str = "") -> None:
        old = self.data.pop(task_id, None)
        if self.storage_type == "json":
            with open(self.filename, "w") as f:
                json.dump(self.data, f, indent=2)
        self._append_event({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task_id": task_id,
            "agent": agent,
            "action": "DELETE",
            "diff": self._compute_diff(old, {}) if old else {},
        })

    def get_task_history(self, task_id: str) -> List[dict]:
        events = []
        if os.path.exists(self.event_filename):
            with open(self.event_filename, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        evt = json.loads(line)
                        if evt.get("task_id") == task_id:
                            events.append(evt)
                    except json.JSONDecodeError:
                        continue
        return events

    def get_all_events(self) -> List[dict]:
        events = []
        if os.path.exists(self.event_filename):
            with open(self.event_filename, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return events

    def _append_event(self, event: dict) -> None:
        with open(self.event_filename, "a") as f:
            f.write(json.dumps(event, default=str) + "\n")

    def _compute_diff(self, old: dict, new: dict) -> dict:
        diff = {}
        all_keys = set(old.keys()) | set(new.keys())
        for key in all_keys:
            old_val = old.get(key)
            new_val = new.get(key)
            if old_val != new_val:
                diff[key] = {"old": old_val, "new": new_val}
        return diff
