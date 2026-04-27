"""WebSocket chat server for GADK UI Shell.

Provides REST endpoints for message history and WebSocket for real-time
agent streaming responses. Supports code blocks, file attachments, and
agent status updates.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel


class ChatMessage(BaseModel):
    id: str | None = None
    role: str  # user, assistant, system
    content: str
    code_blocks: list[dict[str, Any]] | None = None
    file_refs: list[str] | None = None
    agent_status: str | None = None  # e.g., "planning", "coding", "reviewing"


class MessageStore:
    """In-memory message store with optional persistence."""

    def __init__(self) -> None:
        self._messages: list[ChatMessage] = []
        self._listeners: list[WebSocket] = []

    def add(self, msg: ChatMessage) -> ChatMessage:
        msg.id = msg.id or str(uuid.uuid4())[:8]
        self._messages.append(msg)
        return msg

    def get_all(self, limit: int = 100) -> list[ChatMessage]:
        return self._messages[-limit:]

    def get_by_id(self, msg_id: str) -> ChatMessage | None:
        for m in self._messages:
            if m.id == msg_id:
                return m
        return None

    async def broadcast(self, msg: ChatMessage) -> None:
        disconnected: list[WebSocket] = []
        for ws in self._listeners:
            try:
                await ws.send_json(msg.model_dump(mode="json"))
            except Exception:  # noqa: BLE001
                disconnected.append(ws)
        for ws in disconnected:
            while ws in self._listeners:
                self._listeners.remove(ws)

    def add_listener(self, ws: WebSocket) -> None:
        self._listeners.append(ws)

    def remove_listener(self, ws: WebSocket) -> None:
        if ws in self._listeners:
            self._listeners.remove(ws)


# Global store
_message_store = MessageStore()


def create_chat_app() -> FastAPI:
    app = FastAPI(title="GADK Chat Server", version="0.2.0")

    @app.post("/messages")
    async def post_message(msg: ChatMessage) -> dict[str, Any]:
        saved = _message_store.add(msg)
        await _message_store.broadcast(saved)
        return saved.model_dump(mode="json")

    @app.get("/messages")
    def get_messages(limit: int = 100) -> dict[str, Any]:
        return {"messages": [m.model_dump(mode="json") for m in _message_store.get_all(limit)]}

    @app.get("/messages/{msg_id}")
    def get_message(msg_id: str) -> dict[str, Any]:
        msg = _message_store.get_by_id(msg_id)
        if not msg:
            raise HTTPException(status_code=404, detail="Message not found")
        return msg.model_dump(mode="json")

    @app.websocket("/ws")
    async def chat_websocket(websocket: WebSocket) -> None:
        await websocket.accept()
        _message_store.add_listener(websocket)
        try:
            while True:
                data = await websocket.receive_json()
                msg = ChatMessage(**data)
                saved = _message_store.add(msg)
                await _message_store.broadcast(saved)
        except WebSocketDisconnect:
            _message_store.remove_listener(websocket)

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "messages": len(_message_store._messages)}

    return app


def run_chat_server(host: str = "127.0.0.1", port: int = 8081) -> None:
    import uvicorn

    app = create_chat_app()
    uvicorn.run(app, host=host, port=port)


__all__ = ["create_chat_app", "ChatMessage", "MessageStore", "run_chat_server"]
