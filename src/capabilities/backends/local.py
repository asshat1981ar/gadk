import inspect

from src.capabilities.contracts import CapabilityHandler, CapabilityRequest, CapabilityResult


async def execute_local_capability(
    request: CapabilityRequest,
    handler: CapabilityHandler,
) -> CapabilityResult:
    """Execute a local capability handler and normalize its output."""
    output = handler(request)
    if inspect.isawaitable(output):
        output = await output

    if isinstance(output, CapabilityResult):
        return output

    payload = output if isinstance(output, dict) else {"value": output}
    return CapabilityResult.ok(payload=payload, source_backend="local")
