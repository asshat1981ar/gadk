"""Cross-process file-append lock helper.

`fcntl.flock`-based exclusive lock context manager used by every writer
of the shared `events.jsonl`, `prompt_queue.jsonl`, and state files.
The pattern was previously duplicated across three modules:

- ``src.state.StateManager._append_locked``
- ``src.cli.swarm_ctl._queue_lock``
- ``src.services.self_prompt.dispatch`` (inline lock block)

This utility is the single implementation; callers import it via
:func:`locked_append`. On POSIX the lock is exclusive and the buffer
is `flush`-ed + `fsync`-ed *inside* the critical section so a concurrent
process acquiring the lock can't observe partial writes. On Windows
(`fcntl` unavailable) the lock is skipped with a one-shot warning and
the caller gets best-effort appends; still correct under single-process
use.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from typing import IO

from src.observability.logger import get_logger

logger = get_logger("file_lock")

try:
    import fcntl as _fcntl

    _FLOCK_AVAILABLE = True
except ImportError:  # Windows
    _fcntl = None  # type: ignore[assignment]
    _FLOCK_AVAILABLE = False

#: One-shot guard so the "fcntl unavailable" warning fires at most once
#: per process on first use, not at import time.
_FLOCK_WARNED = False


def _warn_once_if_unavailable(path: str) -> None:
    global _FLOCK_WARNED
    if _FLOCK_AVAILABLE or _FLOCK_WARNED:
        return
    logger.warning(
        "fcntl unavailable on this platform; concurrent appends to %s " "will not be serialized",
        path,
    )
    _FLOCK_WARNED = True


@contextmanager
def locked_file(path: str, mode: str) -> Generator[IO, None, None]:
    """Open ``path`` in ``mode`` holding an exclusive ``fcntl.flock`` for
    the duration of the context.

    Any write mode (``"w"``, ``"a"``, ``"r+"``, ``"w+"``) triggers a
    ``flush()`` + ``fsync()`` inside the critical section so the file's
    on-disk state is consistent before the lock is released. Read-only
    modes skip the flush.

    Subtle race avoidance:

    - Truncating modes (``"w"``, ``"w+"``) are rewritten internally as
      ``"r+"`` (or ``"w+"`` if the file doesn't yet exist) so the file
      is **not** truncated before the lock is held. The truncate happens
      after ``flock`` acquires, inside the critical section — otherwise a
      sibling process holding the lock would have its in-progress data
      blown away by the open() call.
    - Flush + fsync now runs inside a ``finally`` after ``yield`` so a
      caller exception can't bypass the durability step and leave
      buffered writes visible to the next lock holder. Harmless no-op
      when nothing was written.

    On platforms without ``fcntl`` the lock is a no-op; see module
    docstring.
    """
    _warn_once_if_unavailable(path)

    write_mode = any(ch in mode for ch in ("w", "a", "+"))
    truncate_after_lock = False
    effective_mode = mode
    if mode == "w":
        # `open(path, "w")` truncates *before* the lock is acquired.
        # Defer the truncate until we're inside the critical section.
        effective_mode = "r+" if os.path.exists(path) else "w+"
        truncate_after_lock = True
    elif mode == "w+":
        effective_mode = "r+" if os.path.exists(path) else "w+"
        truncate_after_lock = True

    f = open(path, effective_mode)  # noqa: SIM115 — context manager yields the handle
    try:
        if _FLOCK_AVAILABLE:
            _fcntl.flock(f, _fcntl.LOCK_EX)
        try:
            if truncate_after_lock:
                f.seek(0)
                f.truncate()
            yield f
        finally:
            # Flush + fsync *before* releasing the lock — even on
            # exception paths. Ensures the next lock holder never
            # observes partially-buffered writes from us.
            if write_mode:
                try:
                    f.flush()
                    os.fsync(f.fileno())
                except (OSError, ValueError):
                    # fsync on a read-mode fd or a closed fd is harmless
                    # to ignore; re-raising would mask the original
                    # exception that got us into this finally block.
                    pass
            if _FLOCK_AVAILABLE:
                _fcntl.flock(f, _fcntl.LOCK_UN)
    finally:
        f.close()


def locked_append(path: str, line: str) -> None:
    """Append ``line + \\n`` to ``path`` under an exclusive lock.

    Convenience wrapper around :func:`locked_file` for the common
    append-a-JSONL-record pattern used by ``events.jsonl`` /
    ``prompt_queue.jsonl``.
    """
    with locked_file(path, "a") as f:
        f.write(line + "\n")


__all__ = ["locked_append", "locked_file"]
