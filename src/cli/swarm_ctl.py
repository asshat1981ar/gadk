"""Shared control mechanisms for the Cognitive Foundry swarm.

Provides inter-process communication via sentinel files and queues:
- Shutdown sentinel: .swarm_shutdown
- Prompt queue: prompt_queue.jsonl
- PID file: swarm.pid
"""

import json
import os
from contextlib import contextmanager
from datetime import UTC, datetime

try:
    import fcntl as _fcntl

    _QUEUE_FLOCK_AVAILABLE = True
except ImportError:  # Windows — best-effort without locking
    _fcntl = None  # type: ignore[assignment]
    _QUEUE_FLOCK_AVAILABLE = False

SENTINEL_PATH = ".swarm_shutdown"
QUEUE_PATH = "prompt_queue.jsonl"
PID_PATH = "swarm.pid"


@contextmanager
def _queue_lock(mode: str):
    """Open ``QUEUE_PATH`` in ``mode`` holding an exclusive ``fcntl`` lock.

    All ``prompt_queue.jsonl`` accessors (enqueue + dequeue + peek) route
    through this so the self-prompt background thread's appends cannot
    race with the main loop's read-then-unlink in ``dequeue_prompts``.
    """
    f = open(QUEUE_PATH, mode)
    try:
        if _QUEUE_FLOCK_AVAILABLE:
            _fcntl.flock(f, _fcntl.LOCK_EX)
        try:
            yield f
            if "w" in mode or "a" in mode:
                f.flush()
                os.fsync(f.fileno())
        finally:
            if _QUEUE_FLOCK_AVAILABLE:
                _fcntl.flock(f, _fcntl.LOCK_UN)
    finally:
        f.close()


def is_shutdown_requested() -> bool:
    return os.path.exists(SENTINEL_PATH)


def request_shutdown() -> None:
    with open(SENTINEL_PATH, "w") as f:
        f.write(datetime.now(UTC).isoformat())


def clear_shutdown() -> None:
    if os.path.exists(SENTINEL_PATH):
        os.remove(SENTINEL_PATH)


def write_pid() -> None:
    with open(PID_PATH, "w") as f:
        f.write(str(os.getpid()))


def clear_pid() -> None:
    if os.path.exists(PID_PATH):
        os.remove(PID_PATH)


def get_swarm_pid() -> int | None:
    if not os.path.exists(PID_PATH):
        return None
    try:
        with open(PID_PATH) as f:
            return int(f.read().strip())
    except (ValueError, OSError):
        return None


def enqueue_prompt(prompt: str, user_id: str = "cli_user") -> None:
    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "user_id": user_id,
        "prompt": prompt,
    }
    with _queue_lock("a") as f:
        f.write(json.dumps(entry) + "\n")


def dequeue_prompts() -> list[dict]:
    """Read all queued prompts and clear the file in one locked operation.

    Must hold the queue lock across read + ``os.remove`` so a concurrent
    enqueue (from the self-prompt background thread) can't land in a
    file we're about to unlink and silently lose the prompt.
    """
    if not os.path.exists(QUEUE_PATH):
        return []
    entries: list[dict] = []
    try:
        with _queue_lock("r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            # Still under the exclusive lock — any blocked enqueuer waits
            # and opens a fresh file once we release.
            try:
                os.remove(QUEUE_PATH)
            except FileNotFoundError:
                pass
    except FileNotFoundError:
        return []
    return entries


def peek_prompts() -> list[dict]:
    if not os.path.exists(QUEUE_PATH):
        return []
    entries: list[dict] = []
    try:
        with _queue_lock("r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except FileNotFoundError:
        return []
    return entries
