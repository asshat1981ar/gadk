"""Shared control mechanisms for the Cognitive Foundry swarm.

Provides inter-process communication via sentinel files and queues:
- Shutdown sentinel: .swarm_shutdown
- Prompt queue: prompt_queue.jsonl
- PID file: swarm.pid
"""

import json
import os
import sys
from datetime import datetime, timezone
from typing import List, Optional

SENTINEL_PATH = ".swarm_shutdown"
QUEUE_PATH = "prompt_queue.jsonl"
PID_PATH = "swarm.pid"


def is_shutdown_requested() -> bool:
    return os.path.exists(SENTINEL_PATH)


def request_shutdown() -> None:
    with open(SENTINEL_PATH, "w") as f:
        f.write(datetime.now(timezone.utc).isoformat())


def clear_shutdown() -> None:
    if os.path.exists(SENTINEL_PATH):
        os.remove(SENTINEL_PATH)


def write_pid() -> None:
    with open(PID_PATH, "w") as f:
        f.write(str(os.getpid()))


def clear_pid() -> None:
    if os.path.exists(PID_PATH):
        os.remove(PID_PATH)


def get_swarm_pid() -> Optional[int]:
    if not os.path.exists(PID_PATH):
        return None
    try:
        with open(PID_PATH) as f:
            return int(f.read().strip())
    except (ValueError, OSError):
        return None


def enqueue_prompt(prompt: str, user_id: str = "cli_user") -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "prompt": prompt,
    }
    with open(QUEUE_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def dequeue_prompts() -> List[dict]:
    if not os.path.exists(QUEUE_PATH):
        return []
    entries = []
    with open(QUEUE_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    # Clear queue after reading
    os.remove(QUEUE_PATH)
    return entries


def peek_prompts() -> List[dict]:
    if not os.path.exists(QUEUE_PATH):
        return []
    entries = []
    with open(QUEUE_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries
