"""SSE connection lifecycle manager.

Manages SSE client connections and broadcasts events to all connected clients.
"""

from __future__ import annotations

import asyncio


class SSEManager:
    """Manages SSE client connections."""

    def __init__(self):
        self.clients: list[asyncio.Queue] = []

    def add_client(self) -> asyncio.Queue:
        """Returns a queue for a new client."""
        q = asyncio.Queue()
        self.clients.append(q)
        return q

    async def broadcast(self, event: dict):
        """Push event to all connected clients."""
        for client in self.clients:
            await client.put(event)

    def remove_client(self, q: asyncio.Queue):
        self.clients.remove(q)
