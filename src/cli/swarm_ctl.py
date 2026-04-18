"""Shared control mechanisms for the Cognitive Foundry swarm.

Provides inter-process communication via sentinel files and queues:
- Shutdown sentinel: .swarm_shutdown
- Prompt queue: prompt_queue.jsonl
- PID file: swarm.pid
"""

import json
import os
from datetime import UTC, datetime

from src.utils.file_lock import locked_file

SENTINEL_PATH = ".swarm_shutdown"
QUEUE_PATH = "prompt_queue.jsonl"
PID_PATH = "swarm.pid"


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
    with locked_file(QUEUE_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def dequeue_prompts() -> list[dict]:
    """Read all queued prompts and clear the file in one locked operation.

    Uses ``r+`` + in-place truncate instead of read-then-unlink because
    Windows raises ``PermissionError`` on ``os.remove`` of an open file
    (and our fcntl lock is a no-op there, so the race against concurrent
    enqueuers is real). Truncating in place keeps the file's inode
    stable so the advisory lock still serializes enqueuers correctly.
    """
    if not os.path.exists(QUEUE_PATH):
        return []
    entries: list[dict] = []
    try:
        with locked_file(QUEUE_PATH, "r+") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            # Still under the exclusive lock — any blocked enqueuer
            # waits and sees an empty file after we return.
            f.seek(0)
            f.truncate()
    except FileNotFoundError:
        return []
    return entries


def peek_prompts() -> list[dict]:
    if not os.path.exists(QUEUE_PATH):
        return []
    entries: list[dict] = []
    try:
        with locked_file(QUEUE_PATH, "r") as f:
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
