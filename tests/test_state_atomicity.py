"""Concurrent-writer tests for StateManager atomic helpers.

Spins up 8 processes that simultaneously mutate the same task and verifies:
  (a) state.json is always valid JSON (never a partial write)
  (b) no events are lost from events.jsonl
"""

import json
import multiprocessing
import time

import pytest

from src.state import StateManager

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

POLL_INTERVAL_SECONDS = 0.005  # how often to sample state.json during concurrent writes

# ---------------------------------------------------------------------------
# Workers run in each subprocess
# ---------------------------------------------------------------------------


def _writer_worker(state_json: str, events_jsonl: str, worker_id: int, n_writes: int) -> None:
    """Perform *n_writes* set_task calls (all on the same shared task key)."""
    sm = StateManager(storage_type="json", filename=state_json, event_filename=events_jsonl)
    for i in range(n_writes):
        sm.set_task(
            "shared-task",
            {"status": "PENDING", "worker": worker_id, "seq": i},
            agent=f"worker-{worker_id}",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_json_safely(path: str):
    """Return parsed JSON or raise if the file is not valid JSON."""
    with open(path, "r") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestStateAtomicity:
    def test_concurrent_writers_no_corruption(self, tmp_path):
        """state.json must be valid JSON after all concurrent writers finish.

        _atomic_write_json guarantees no torn partial writes. Because each
        process carries its own in-memory snapshot, the last writer wins for
        the in-memory state value — that is a separate lost-update concern
        beyond the scope of this fix. The invariant we assert here is simply
        that the file is always well-formed JSON.
        """
        state_json = str(tmp_path / "state.json")
        events_jsonl = str(tmp_path / "events.jsonl")
        n_workers = 8
        n_writes_each = 20

        processes = [
            multiprocessing.Process(
                target=_writer_worker,
                args=(state_json, events_jsonl, wid, n_writes_each),
            )
            for wid in range(n_workers)
        ]
        for p in processes:
            p.start()
        for p in processes:
            p.join(timeout=30)
            assert p.exitcode == 0, f"Worker process exited with code {p.exitcode}"

        # (a) state.json must parse as valid JSON
        state = _read_json_safely(state_json)
        assert isinstance(state, dict), "state.json must be a JSON object"
        # The shared task must be present (written by at least one worker)
        assert "shared-task" in state, "shared-task missing from state.json"

    def test_no_events_lost(self, tmp_path):
        """All events appended by concurrent writers must appear in events.jsonl."""
        state_json = str(tmp_path / "state.json")
        events_jsonl = str(tmp_path / "events.jsonl")
        n_workers = 8
        n_writes_each = 20

        processes = [
            multiprocessing.Process(
                target=_writer_worker,
                args=(state_json, events_jsonl, wid, n_writes_each),
            )
            for wid in range(n_workers)
        ]
        for p in processes:
            p.start()
        for p in processes:
            p.join(timeout=30)
            assert p.exitcode == 0, f"Worker process exited with code {p.exitcode}"

        # (b) Every line in events.jsonl must be valid JSON and the total count
        #     must equal n_workers * n_writes_each.
        events = []
        with open(events_jsonl, "r") as fh:
            for lineno, raw in enumerate(fh, start=1):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    events.append(json.loads(raw))
                except json.JSONDecodeError as exc:
                    pytest.fail(
                        f"events.jsonl line {lineno} is not valid JSON: {exc}\nContent: {raw!r}"
                    )

        expected_count = n_workers * n_writes_each
        assert len(events) == expected_count, f"Expected {expected_count} events, got {len(events)}"

    def test_mid_flight_state_json_is_valid(self, tmp_path):
        """state.json must be parseable while writers are still running."""
        state_json = str(tmp_path / "state.json")
        events_jsonl = str(tmp_path / "events.jsonl")
        # Seed the file so it exists before readers start
        StateManager(
            storage_type="json", filename=state_json, event_filename=events_jsonl
        ).set_task("seed", {"status": "PENDING"})

        n_workers = 8
        n_writes_each = 50  # more iterations so the test can sample mid-flight

        processes = [
            multiprocessing.Process(
                target=_writer_worker,
                args=(state_json, events_jsonl, wid, n_writes_each),
            )
            for wid in range(n_workers)
        ]
        for p in processes:
            p.start()

        # Poll state.json while writers are active
        errors = []
        read_count = 0
        deadline = time.monotonic() + 10  # cap at 10 s
        while any(p.is_alive() for p in processes) and time.monotonic() < deadline:
            try:
                _read_json_safely(state_json)
                read_count += 1
            except (json.JSONDecodeError, OSError) as exc:
                errors.append(str(exc))
            time.sleep(POLL_INTERVAL_SECONDS)

        for p in processes:
            p.join(timeout=30)

        assert read_count > 0, (
            "state.json was never successfully read while writers were active; "
            "the mid-flight check did not exercise any concurrent reads"
        )
        assert not errors, "state.json was invalid JSON during concurrent writes:\n" + "\n".join(
            errors
        )


def _distinct_writer_worker(
    state_json: str, events_jsonl: str, worker_id: int, n_writes: int
) -> None:
    """Perform *n_writes* set_task calls each on a *distinct* task ID.

    With 8 workers × 50 writes = 400 unique task IDs, all must be present
    in the final state.json once the cross-process lock is in place.
    """
    sm = StateManager(storage_type="json", filename=state_json, event_filename=events_jsonl)
    for i in range(n_writes):
        sm.set_task(
            f"task-w{worker_id}-{i}",
            {"status": "PENDING", "worker": worker_id, "seq": i},
            agent=f"worker-{worker_id}",
        )


class TestSetTaskNoLostUpdate:
    def test_set_task_no_lost_update(self, tmp_path):
        """8 processes × 50 distinct task IDs = 400 tasks must all survive.

        Without a cross-process lock around the read-modify-write the later
        ``os.replace`` silently drops the earlier writer's updates. This test
        asserts that the fix (``_locked_persist_json``) closes the race.
        """
        state_json = str(tmp_path / "state.json")
        events_jsonl = str(tmp_path / "events.jsonl")
        n_workers = 8
        n_writes_each = 50

        processes = [
            multiprocessing.Process(
                target=_distinct_writer_worker,
                args=(state_json, events_jsonl, wid, n_writes_each),
            )
            for wid in range(n_workers)
        ]
        for p in processes:
            p.start()
        # Reap each worker. If it's still alive after the timeout, terminate
        # (SIGTERM) then kill (SIGKILL) before asserting, so a deadlocked
        # worker doesn't leak into subsequent tests or block pytest shutdown.
        for p in processes:
            p.join(timeout=60)
            if p.is_alive():
                p.terminate()
                p.join(timeout=5)
                if p.is_alive():
                    p.kill()
                    p.join(timeout=5)
                raise AssertionError(
                    f"Worker process {p.pid} did not finish within 60s; killed for cleanup."
                )
            assert p.exitcode == 0, f"Worker process {p.pid} exited with code {p.exitcode}"

        with open(state_json) as f:
            state = json.load(f)

        expected_count = n_workers * n_writes_each
        assert len(state) == expected_count, (
            f"Expected {expected_count} tasks in state.json, got {len(state)}. "
            f"Missing: {expected_count - len(state)} tasks were lost due to a race."
        )
