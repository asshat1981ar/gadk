import json
import os
import tempfile


class CostTracker:
    def __init__(self, filename: str = "costs.jsonl"):
        self.filename = filename
        self._data: dict[str, dict[str, float]] = {}
        self._load()

    def record_cost(self, task_id: str, agent_name: str, cost_usd: float) -> None:
        if task_id not in self._data:
            self._data[task_id] = {}
        self._data[task_id][agent_name] = self._data[task_id].get(agent_name, 0.0) + cost_usd
        self._persist()

    def get_task_spend(self, task_id: str) -> float:
        return sum(self._data.get(task_id, {}).values())

    def get_total_spend(self) -> float:
        return sum(sum(v.values()) for v in self._data.values())

    def get_summary(self) -> dict:
        return {
            "total_spend_usd": self.get_total_spend(),
            "by_task": {k: sum(v.values()) for k, v in self._data.items()},
            "by_agent": self._aggregate_by_agent(),
        }

    def _aggregate_by_agent(self) -> dict[str, float]:
        result: dict[str, float] = {}
        for task in self._data.values():
            for agent, cost in task.items():
                result[agent] = result.get(agent, 0.0) + cost
        return result

    def _persist(self) -> None:
        """Atomic write via tempfile + os.replace.

        Cost records land here on every LLM call from the swarm loop, the
        self-prompt tick, and any other concurrent agent path. A plain
        ``open(..., "w")`` would truncate + partially-rewrite under
        concurrent writers, leaking cost data. The tempfile + replace
        pattern mirrors ``StateManager._atomic_write_json``.
        """
        dir_name = os.path.dirname(os.path.abspath(self.filename)) or "."
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(self._data, f, indent=2)
            os.replace(tmp_path, self.filename)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def _load(self) -> None:
        if os.path.exists(self.filename):
            with open(self.filename) as f:
                self._data = json.load(f)

    def reset(self) -> None:
        self._data.clear()
        if os.path.exists(self.filename):
            os.remove(self.filename)
