import inspect
from collections.abc import Awaitable, Callable

from src.capabilities.backends import execute_local_capability, execute_smithery_capability
from src.capabilities.contracts import CapabilityHandler, CapabilityRequest, CapabilityResult
from src.capabilities.registry import CapabilityRegistry

BackendExecutor = Callable[..., Awaitable[CapabilityResult]]


class CapabilityService:
    def __init__(self, registry: CapabilityRegistry) -> None:
        self._registry = registry
        self._executors: dict[str, BackendExecutor] = {
            "local": execute_local_capability,
            "retrieval": self._execute_passthrough_capability,
            "smithery": execute_smithery_capability,
        }

    async def _execute_passthrough_capability(
        self,
        request: CapabilityRequest,
        handler: CapabilityHandler,
    ) -> CapabilityResult:
        """Execute a local in-process capability with an explicit backend label."""

        output = handler(request)
        if inspect.isawaitable(output):
            output = await output

        if isinstance(output, CapabilityResult):
            return output

        payload = output if isinstance(output, dict) else {"value": output}
        return CapabilityResult.ok(payload=payload, source_backend="retrieval")

    async def execute(self, name: str, **arguments: object) -> CapabilityResult:
        try:
            definition = self._registry.get(name)
        except KeyError:
            return CapabilityResult.error(
                error=f"Unknown capability: {name}",
                source_backend="registry",
                retryable=False,
            )

        capability_request = CapabilityRequest(name=name, arguments=dict(arguments))

        executor = self._executors.get(definition.backend)
        if executor is None:
            return CapabilityResult.error(
                error=f"Unsupported capability backend: {definition.backend}",
                source_backend=definition.backend,
                retryable=False,
            )

        try:
            return await executor(capability_request, definition.handler)
        except Exception as exc:
            return CapabilityResult.error(
                error=str(exc),
                source_backend=definition.backend,
                retryable=False,
            )
