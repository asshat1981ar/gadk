# tests/webapp/test_integration.py
"""Integration tests for main webapp server with chat routes and static files."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.webapp.server import create_app


def test_chat_endpoints_exist():
    app = create_app()
    client = TestClient(app)
    resp = client.post("/chat/messages", json={"role": "user", "content": "Hello"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "user"
    assert data["content"] == "Hello"

    resp2 = client.get("/chat/messages")
    assert resp2.status_code == 200
    assert "messages" in resp2.json()


def test_static_files_served():
    app = create_app()
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "GADK" in resp.text
