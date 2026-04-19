import json
import os
import tempfile
import threading
from datetime import UTC, datetime

from src.observability.logger import get_logger
from src.utils.file_lock import locked_append, locked_file

logger = get_logger("state")


class StateManager:
    def __init__(self, storage_type="json", filename="state.json", event_filename="events.jsonl"):
        self.storage_type = storage_type
        self.filename = filename
        self.event_filename = event_filename
        self.data = {}
        self._lock = threading.Lock()
        if self.storage_type == "json" and os.path.exists(self.filename):
            with open(self.filename) as f:
                try:
                    self.data = json.load(f)
                except json.JSONDecodeError:
                    self.data = {}

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

    def _locked_persist_json(self, mutate_fn) -> dict:
        """Apply *mutate_fn* to the on-disk state under a cross-process exclusive lock.

        Holds an exclusive ``fcntl.flock`` (on a companion ``.lock`` file) for
        the entire read-modify-write cycle so concurrent processes never
        silently drop each other's updates.  ``_atomic_write_json`` is used
        for the write step so readers always see a complete JSON file — never
        an empty or partially-written one.

        **Failure semantics** — on a read/parse failure the exception is
        logged and re-raised; the write is aborted. ``set_task``/
        ``delete_task`` do NOT catch these — the process-level caller is
        expected to handle the rare transient case, because silently
        continuing on corrupted on-disk state would destroy the audit
        trail. (Prior docstring mentioning caller-side in-memory fallback
        was misleading; corrected to reflect the propagate-and-log
        behavior actually implemented here.)

        *mutate_fn* receives the on-disk ``dict`` and must mutate it in place.
        Returns the merged ``dict`` so the caller can sync its in-memory view.
        """
        lock_path = self.filename + ".lock"

        # locked_file("a") creates the companion file if missing and holds
        # LOCK_EX for the duration of the context.  We don't write anything
        # to the lock file — it is purely a serialisation token.
        with locked_file(lock_path, "a"):
            on_disk: dict = {}
            if os.path.exists(self.filename):
                try:
                    with open(self.filename) as sf:
                        raw = sf.read()
                    if raw.strip():
                        loaded = json.loads(raw)
                        if not isinstance(loaded, dict):
                            raise ValueError(f"state file {self.filename!r} contains non-dict JSON")
                        on_disk = loaded
                except (OSError, json.JSONDecodeError, ValueError) as exc:
                    # Log and re-raise. Silent fallback to empty dict would
                    # destroy on-disk state on a transient I/O hiccup.
                    logger.error(
                        "state.persist.read_failed path=%s reason=%s",
                        self.filename,
                        exc,
                        exc_info=True,
                    )
                    raise

            mutate_fn(on_disk)
            # Atomic write via tmpfile + os.replace so readers outside the
            # lock never observe a partially-written or empty file.
            self._atomic_write_json(self.filename, on_disk)

        return on_disk

    # ------------------------------------------------------------------
    # Public mutators
    # ------------------------------------------------------------------

    def set_task(self, task_id: str, task_data: dict, agent: str = "") -> None:
        with self._lock:
            old = self.data.get(task_id, {})
            if self.storage_type == "json":
                merged = self._locked_persist_json(lambda d: d.update({task_id: task_data}))
                self.data = merged
            else:
                self.data[task_id] = task_data
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
        with self._lock:
            old = self.data.get(task_id)
            if self.storage_type == "json":
                merged = self._locked_persist_json(lambda d: d.pop(task_id, None))
                self.data = merged
            else:
                self.data.pop(task_id, None)
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
