# tests/webapp/test_chat_server.py
"""Tests for chat server REST and WebSocket endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.webapp.chat_server import ChatMessage, create_chat_app


@pytest.fixture
def client():
    app = create_chat_app()
    return TestClient(app)


def test_send_message(client):
    resp = client.post("/messages", json={"role": "user", "content": "Hello"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] is not None
    assert data["role"] == "user"
    assert data["content"] == "Hello"


def test_get_messages(client):
    client.post("/messages", json={"role": "user", "content": "Test message"})
    resp = client.get("/messages")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["messages"]) >= 1
    assert data["messages"][0]["role"] == "user"


def test_get_message_by_id(client):
    resp = client.post("/messages", json={"role": "assistant", "content": "By ID"})
    msg_id = resp.json()["id"]
    resp2 = client.get(f"/messages/{msg_id}")
    assert resp2.status_code == 200
    assert resp2.json()["content"] == "By ID"


def test_message_not_found(client):
    resp = client.get("/chat/messages/nonexistent")
    assert resp.status_code == 404


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_message_store_add_listener():
    """Unit test for MessageStore broadcast logic."""
    from src.webapp.chat_server import MessageStore

    store = MessageStore()
    msg = ChatMessage(role="system", content="test")
    added = store.add(msg)
    assert added.id is not None
    assert len(store.get_all()) == 1
