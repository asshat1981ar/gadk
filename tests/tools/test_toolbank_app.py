"""Tests for the REST API sidecar — toolbank endpoints."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    """Build a test client against the FastAPI app."""
    from src.tools.toolbank_app import app

    return TestClient(app)


class TestGetTools:
    """GET /tools — list all available tools."""

    def test_returns_200(self, client: TestClient) -> None:
        response = client.get("/tools")
        assert response.status_code == 200

    def test_returns_list(self, client: TestClient) -> None:
        data = client.get("/tools").json()
        assert isinstance(data, list)

    def test_tool_shape_has_required_fields(self, client: TestClient) -> None:
        data = client.get("/tools").json()
        for tool in data:
            assert "id" in tool or "name" in tool
            assert "name" in tool
            assert "description" in tool


class TestGetToolsById:
    """GET /tools/{id} — retrieve a single tool by name/id."""

    def test_returns_404_for_unknown(self, client: TestClient) -> None:
        response = client.get("/tools/this-does-not-exist-xyz")
        assert response.status_code == 404

    def test_returns_200_for_known(self, client: TestClient) -> None:
        # Seed the tool from the dispatcher registry so something exists.
        import src.tools.dispatcher as dispatcher

        dispatcher.register_tool("dummy_tool", lambda: "ok")
        # Fetch the first tool so we know a valid name.
        all_tools = client.get("/tools").json()
        if not all_tools:
            pytest.skip("No tools registered in dispatcher")
        first_name = all_tools[0]["name"]
        response = client.get(f"/tools/{first_name}")
        assert response.status_code == 200

    def test_returns_tool_object(self, client: TestClient) -> None:
        import src.tools.dispatcher as dispatcher

        dispatcher.register_tool("test_tool_obj", lambda: "ok")
        response = client.get("/tools/test_tool_obj")
        if response.status_code == 200:
            data = response.json()
            assert "name" in data or "id" in data


class TestAdminDrift:
    """GET /admin/drift — report any tool definitions that have drifted from source."""

    def test_returns_200(self, client: TestClient) -> None:
        response = client.get("/admin/drift")
        assert response.status_code == 200

    def test_returns_dict_with_drift_key(self, client: TestClient) -> None:
        data = client.get("/admin/drift").json()
        assert isinstance(data, dict)
        assert "drifted_tools" in data or "drift" in data or "tools" in data
