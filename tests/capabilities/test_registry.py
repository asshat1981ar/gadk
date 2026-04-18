import pytest

from src.capabilities.contracts import CapabilityRequest, CapabilityResult
from src.capabilities.registry import CapabilityRegistry


class TestCapabilityRegistry:
    def test_registry_registers_and_resolves_capability(self):
        registry = CapabilityRegistry()

        def handler(request: CapabilityRequest) -> CapabilityResult:
            return CapabilityResult.ok(
                payload={"value": request.arguments["value"]},
                source_backend="local",
            )

        registry.register(
            name="swarm.status",
            description="Read swarm status",
            backend="local",
            handler=handler,
        )

        capability = registry.get("swarm.status")

        assert capability.name == "swarm.status"
        assert capability.backend == "local"

    def test_capability_result_error_preserves_retryable_flag(self):
        result = CapabilityResult.error(
            error="backend unavailable",
            source_backend="smithery",
            retryable=True,
        )

        assert result.status == "error"
        assert result.error == "backend unavailable"
        assert result.retryable is True

    def test_registry_rejects_duplicate_capability_names(self):
        registry = CapabilityRegistry()

        def handler(request: CapabilityRequest) -> CapabilityResult:
            return CapabilityResult.ok(
                payload={"value": request.arguments.get("value")},
                source_backend="local",
            )

        registry.register(
            name="swarm.status",
            description="Read swarm status",
            backend="local",
            handler=handler,
        )

        with pytest.raises(ValueError, match="already registered"):
            registry.register(
                name="swarm.status",
                description="Read swarm status again",
                backend="local",
                handler=handler,
            )
