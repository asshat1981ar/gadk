from unittest.mock import AsyncMock, patch

import pytest

from src.capabilities.contracts import CapabilityRequest, CapabilityResult
from src.capabilities.registry import CapabilityRegistry
from src.capabilities.service import CapabilityService


class TestCapabilityService:
    @pytest.mark.asyncio
    async def test_service_executes_local_capability(self):
        registry = CapabilityRegistry()

        def status_handler(request: CapabilityRequest) -> CapabilityResult:
            return CapabilityResult.ok(
                payload={"health": request.arguments.get("health", "HEALTHY")},
                source_backend="local",
            )

        registry.register("swarm.status", "Read swarm status", "local", status_handler)

        service = CapabilityService(registry)
        result = await service.execute("swarm.status")

        assert result.status == "success"
        assert result.payload == {"health": "HEALTHY"}
        assert result.error is None
        assert result.source_backend == "local"
        assert result.retryable is False

    @pytest.mark.asyncio
    async def test_service_executes_smithery_capability(self):
        registry = CapabilityRegistry()

        def smithery_handler(request: CapabilityRequest) -> dict[str, object]:
            return {
                "server_id": request.arguments["server_id"],
                "tool_name": "list_resources",
                "tool_args": {"limit": 5},
            }

        registry.register(
            "smithery.resources",
            "List Smithery resources",
            "smithery",
            smithery_handler,
        )

        service = CapabilityService(registry)

        with patch(
            "src.capabilities.backends.smithery.call_smithery_tool",
            new=AsyncMock(return_value='{"items": []}'),
        ) as mocked_call:
            result = await service.execute(
                "smithery.resources",
                server_id="demo-server",
            )

        mocked_call.assert_awaited_once_with("demo-server", "list_resources", {"limit": 5})
        assert result.status == "success"
        assert result.payload == {"output": '{"items": []}'}
        assert result.source_backend == "smithery"

    @pytest.mark.asyncio
    async def test_service_wraps_backend_errors(self):
        registry = CapabilityRegistry()

        def broken_handler(request: CapabilityRequest) -> CapabilityResult:
            raise RuntimeError("boom")

        registry.register("swarm.status", "Read swarm status", "local", broken_handler)

        service = CapabilityService(registry)
        result = await service.execute("swarm.status")

        assert result.status == "error"
        assert result.payload is None
        assert result.error == "boom"
        assert result.source_backend == "local"
        assert result.retryable is False

    @pytest.mark.asyncio
    async def test_service_wraps_unknown_capability_lookup(self):
        service = CapabilityService(CapabilityRegistry())

        result = await service.execute("missing.capability")

        assert result.status == "error"
        assert result.payload is None
        assert result.error == "Unknown capability: missing.capability"
        assert result.source_backend == "registry"
        assert result.retryable is False
