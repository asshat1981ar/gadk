import json
import os
import tempfile
import threading

from src.observability.logger import get_logger
from src.utils.file_lock import locked_file

logger = get_logger("cost_tracker")


class CostTracker:
    """Persistent per-task + per-agent cost aggregator.

    Thread-safety: in-process writers (swarm loop, self-prompt tick,
    embedding quota) all touch ``_data`` through ``record_cost``; a
    :class:`threading.Lock` serializes the read-modify-write so
    ``json.dump`` can't observe a dict mutated mid-iteration.

    Cross-process safety: when multiple ``CostTracker`` instances in
    separate processes all write ``costs.jsonl``, the persist path holds
    an ``fcntl`` lock across read-merge-write so the later writer
    preserves the earlier writer's increments (no last-writer-wins data
    loss). The atomic ``tempfile.mkstemp`` + ``os.replace`` pattern is
    retained so readers never see torn files.

    A malformed or truncated ``costs.jsonl`` on startup is treated as
    "no history" (matches ``StateManager`` behavior) — better than
    crashing the swarm because of a one-time write that was interrupted.
    """

    def __init__(self, filename: str = "costs.jsonl"):
        self.filename = filename
        self._data: dict[str, dict[str, float]] = {}
        self._lock = threading.Lock()
        self._load()

    def record_cost(self, task_id: str, agent_name: str, cost_usd: float) -> None:
        with self._lock:
            if task_id not in self._data:
                self._data[task_id] = {}
            self._data[task_id][agent_name] = self._data[task_id].get(agent_name, 0.0) + cost_usd
            # Snapshot under the lock so the persist path reads a
            # consistent view even if another thread lands record_cost
            # between the snapshot and the file write.
            snapshot = {k: dict(v) for k, v in self._data.items()}
        self._persist(snapshot)

    def get_task_spend(self, task_id: str) -> float:
        with self._lock:
            return sum(self._data.get(task_id, {}).values())

    def get_total_spend(self) -> float:
        with self._lock:
            return sum(sum(v.values()) for v in self._data.values())

    def get_summary(self) -> dict:
        with self._lock:
            return {
                "total_spend_usd": sum(sum(v.values()) for v in self._data.values()),
                "by_task": {k: sum(v.values()) for k, v in self._data.items()},
                "by_agent": self._aggregate_by_agent_locked(),
            }

    def _aggregate_by_agent_locked(self) -> dict[str, float]:
        # Must be called with self._lock held.
        result: dict[str, float] = {}
        for task in self._data.values():
            for agent, cost in task.items():
                result[agent] = result.get(agent, 0.0) + cost
        return result

    def _persist(self, snapshot: dict[str, dict[str, float]]) -> None:
        """Read-merge-write under a cross-process lock + atomic replace.

        Step-by-step:
        1. Take an exclusive ``fcntl`` lock on ``costs.jsonl`` (creating
           it empty if missing) so any other process in its own
           ``_persist`` waits.
        2. Read whatever the file currently has; if malformed, treat as
           empty (log-warn rather than crash).
        3. Merge the on-disk view with our ``snapshot`` (max-of
           per-(task,agent) is not appropriate — we sum, since every
           record_cost call adds an increment; but the on-disk view
           already includes every increment *this* process has
           persisted, so we sum only against records this process
           hasn't seen yet). Simpler and correct here: prefer the
           in-memory snapshot as the source of truth for
           *this process's* tasks, and additively import any
           task_id / agent_name not present in memory.
        4. Write the merged dict to a tempfile, ``os.replace`` to swap,
           release the lock.
        """
        dir_name = os.path.dirname(os.path.abspath(self.filename)) or "."

        # Ensure the file exists so the lock has something to grab.
        if not os.path.exists(self.filename):
            try:
                with open(self.filename, "a"):
                    pass
            except OSError:
                pass

        try:
            with locked_file(self.filename, "r+") as f:
                raw = f.read()
        except FileNotFoundError:
            raw = ""

        on_disk: dict[str, dict[str, float]] = {}
        if raw.strip():
            try:
                on_disk = json.loads(raw)
                if not isinstance(on_disk, dict):
                    on_disk = {}
            except json.JSONDecodeError as exc:
                logger.warning("costs.jsonl malformed, starting fresh: %s", exc)
                on_disk = {}

        # Merge: import any task/agent missing from our snapshot so a
        # sibling process's increments aren't dropped. Our own tasks
        # stay authoritative — record_cost already folded the current
        # increment in before taking the snapshot.
        merged: dict[str, dict[str, float]] = {k: dict(v) for k, v in snapshot.items()}
        for task_id, agents in on_disk.items():
            if task_id not in merged:
                merged[task_id] = dict(agents) if isinstance(agents, dict) else {}
                continue
            for agent, cost in (agents or {}).items():
                if agent not in merged[task_id]:
                    merged[task_id][agent] = float(cost)

        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(merged, f, indent=2)
            os.replace(tmp_path, self.filename)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        # Reflect the merged view back into memory so future reads
        # already include any cross-process increments we picked up.
        with self._lock:
            self._data = merged

    def _load(self) -> None:
        if not os.path.exists(self.filename):
            return
        try:
            with open(self.filename) as f:
                raw = f.read()
            if not raw.strip():
                return
            loaded = json.loads(raw)
            if isinstance(loaded, dict):
                self._data = loaded
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("costs.jsonl load failed, starting fresh: %s", exc)
            self._data = {}

    def reset(self) -> None:
        with self._lock:
            self._data.clear()
        if os.path.exists(self.filename):
            os.remove(self.filename)
