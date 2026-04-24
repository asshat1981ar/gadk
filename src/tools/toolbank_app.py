"""REST API sidecar for the Toolbank MCP frontend.

Provides a lightweight HTTP interface to the internal tool registry so the
MCP frontend can query available tools without a stdio connection.
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(
    title="Toolbank API",
    description="REST sidecar for the Toolbank MCP frontend",
    version="1.0.0",
)


def _get_tool_registry() -> dict[str, Any]:
    """Lazily resolve the tool registry to avoid circular import chains at import time."""
    from src.tools.dispatcher import _TOOL_REGISTRY

    return _TOOL_REGISTRY


def _tool_to_dict(name: str, func: Any) -> dict[str, Any]:
    """Serialize a registered tool into a dict shape."""
    sigilin = getattr(func, "__doc__", None) or ""
    return {
        "name": name,
        "description": sigilin.strip().split("\n")[0] if sigilin.strip() else f"Tool: {name}",
    }


@app.get("/tools", response_model=list[dict[str, Any]])
def list_tools() -> list[dict[str, Any]]:
    """Return all registered tools from the dispatcher registry."""
    registry = _get_tool_registry()
    return [_tool_to_dict(name, func) for name, func in registry.items()]


@app.get("/tools/{tool_id}", response_model=dict[str, Any])
def get_tool(tool_id: str) -> JSONResponse:
    """Return a single tool by name, or 404 if not found."""
    registry = _get_tool_registry()
    if tool_id not in registry:
        return JSONResponse(status_code=404, content={"detail": f"Tool '{tool_id}' not found"})
    func = registry[tool_id]
    tool = _tool_to_dict(tool_id, func)
    tool["callable"] = True  # indicate the tool is available for invocation
    return JSONResponse(content=tool)


@app.get("/admin/drift", response_model=dict[str, Any])
def admin_drift() -> dict[str, Any]:
    """Report tool definitions that have drifted from their canonical source.

    For Phase 1 this is a stub that always reports an empty drift list, since
    the registry is the source of truth and drift detection requires a
    remote toolbank server (future work).
    """
    return {
        "drifted_tools": [],
        "note": "drift detection requires a remote toolbank server — Phase 2",
    }
