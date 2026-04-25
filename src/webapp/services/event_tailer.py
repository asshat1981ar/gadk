"""Async event tailer for SSE streaming.

Tails events.jsonl and yields new events as they appear.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path


class EventTailer:
    """Async event tailer for SSE streaming."""

    def __init__(self, event_file: str = "events.jsonl"):
        self.event_file = Path(event_file)
        self.position = 0

    async def tail(self):
        """Yields new events as they appear."""
        while True:
            if self.event_file.exists():
                current_size = self.event_file.stat().st_size
                if current_size > self.position:
                    with open(self.event_file) as f:
                        f.seek(self.position)
                        for line in f:
                            if line.strip():
                                yield json.loads(line)
                        self.position = f.tell()
            await asyncio.sleep(0.5)
