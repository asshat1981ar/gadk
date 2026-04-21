import json
import os
import tempfile
from datetime import UTC, datetime
from typing import Optional

from src.utils.file_lock import locked_append


class StateManager:
    def __init__(
        self,
        storage_type="json",
        filename="state.json",
        event_filename="events.jsonl",
        tenant_id: Optional[str] = None,
    ):
        self.storage_type = storage_type
        self.base_filename = filename
        self.base_event_filename = event_filename
        self.tenant_id = tenant_id or "default"

        # Compute tenant-specific filenames
        self.filename = self._get_tenant_filename(filename, self.tenant_id)
        self.event_filename = self._get_tenant_event_filename(event_filename, self.tenant_id)

        self.data = {}
        if self.storage_type == "json" and os.path.exists(self.filename):
            with open(self.filename) as f:
                try:
                    self.data = json.load(f)
                except json.JSONDecodeError:
                    self.data = {}

    def _get_tenant_filename(self, base_filename: str, tenant_id: str) -> str:
        """Generate tenant-specific state filename.

        For default tenant: state.json
        For other tenants: state.{tenant_id}.json
        """
        if tenant_id == "default":
            return base_filename
        # Insert tenant_id before the extension
        base, ext = os.path.splitext(base_filename)
        return f"{base}.{tenant_id}{ext}"

    def _get_tenant_event_filename(self, base_filename: str, tenant_id: str) -> str:
        """Generate tenant-specific events filename.

        For default tenant: events.jsonl
        For other tenants: events.{tenant_id}.jsonl
        """
        if tenant_id == "default":
            return base_filename
        # Insert tenant_id before the extension
        base, ext = os.path.splitext(base_filename)
        return f"{base}.{tenant_id}{ext}"

    def for_tenant(self, tenant_id: str) -> "StateManager":
        """Create a new StateManager instance for a specific tenant.

        This allows tenant-specific state operations while maintaining
        backward compatibility with single-tenant usage.

        Args:
            tenant_id: The tenant identifier

        Returns:
            New StateManager instance configured for the tenant
        """
        return StateManager(
            storage_type=self.storage_type,
            filename=self.base_filename,
            event_filename=self.base_event_filename,
            tenant_id=tenant_id,
        )

    # ------------------------------------------------------------------
    # Atomic / safe I/O helpers
    # ------------------------------------------------------------------

    def _atomic_write_json(self, path: str, data: dict) -> None:
        """Write *data* to *path* atomically using a temp-file + os.replace.

        If the write or rename fails the original file is left untouched.
        """
        dir_name = os.path.dirname(os.path.abspath(path)) or "."
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def _append_locked(self, path: str, line: str) -> None:
        """Append *line* to *path* under an exclusive advisory lock.

        Delegates to :func:`src.utils.file_lock.locked_append`, which
        flushes+fsyncs inside the critical section so concurrent
        processes never see torn writes. Safe no-op on Windows.
        """
        locked_append(path, line)

    # ------------------------------------------------------------------
    # Public mutators
    # ------------------------------------------------------------------

    def set_task(self, task_id: str, task_data: dict, agent: str = "") -> None:
        old = self.data.get(task_id, {})
        self.data[task_id] = task_data
        if self.storage_type == "json":
            self._atomic_write_json(self.filename, self.data)
        self._append_event(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "task_id": task_id,
                "agent": agent,
                "action": "SET",
                "diff": self._compute_diff(old, task_data),
            }
        )

    def get_task(self, task_id: str) -> dict | None:
        return self.data.get(task_id)

    def get_all_tasks(self) -> dict[str, dict]:
        return dict(self.data)

    def delete_task(self, task_id: str, agent: str = "") -> None:
        old = self.data.pop(task_id, None)
        if self.storage_type == "json":
            self._atomic_write_json(self.filename, self.data)
        self._append_event(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "task_id": task_id,
                "agent": agent,
                "action": "DELETE",
                "diff": self._compute_diff(old, {}) if old else {},
            }
        )

    def get_task_history(self, task_id: str) -> list[dict]:
        events = []
        if os.path.exists(self.event_filename):
            with open(self.event_filename) as f:
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

    def get_all_events(self) -> list[dict]:
        events = []
        if os.path.exists(self.event_filename):
            with open(self.event_filename) as f:
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
        self._append_locked(self.event_filename, json.dumps(event, default=str))

    def record_phase_transition(
        self,
        task_id: str,
        *,
        from_phase: str,
        to_phase: str,
        reason: str = "",
        gates: list[dict] | None = None,
    ) -> None:
        """Append a ``phase.transition`` event to the event log.

        Used by ``src.services.phase_controller.PhaseController`` to keep the
        SDLC phase ledger in the same audit stream as task-state changes.
        """
        self._append_event(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "task_id": task_id,
                "agent": "PhaseController",
                "action": "phase.transition",
                "from_phase": from_phase,
                "to_phase": to_phase,
                "reason": reason,
                "gates": list(gates or []),
            }
        )

    def _compute_diff(self, old: dict, new: dict) -> dict:
        diff = {}
        all_keys = set(old.keys()) | set(new.keys())
        for key in all_keys:
            old_val = old.get(key)
            new_val = new.get(key)
            if old_val != new_val:
                diff[key] = {"old": old_val, "new": new_val}
        return diff
