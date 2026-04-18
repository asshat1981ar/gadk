import inspect

from src.capabilities.contracts import CapabilityHandler, CapabilityRequest, CapabilityResult
from src.tools.smithery_bridge import call_smithery_tool


async def execute_smithery_capability(
    request: CapabilityRequest,
    handler: CapabilityHandler,
) -> CapabilityResult:
    """Execute a Smithery-backed capability via the bridge."""
    output = handler(request)
    if inspect.isawaitable(output):
        output = await output

    if isinstance(output, CapabilityResult):
        return output

    if not isinstance(output, dict):
        msg = "Smithery capability handlers must return a configuration dict"
        raise TypeError(msg)

    server_id = output["server_id"]
    tool_name = output["tool_name"]
    tool_args = output.get("tool_args", {})

    bridge_output = await call_smithery_tool(server_id, tool_name, tool_args)
    if bridge_output.startswith("Smithery Error:") or bridge_output.startswith("Bridge Error:"):
        return CapabilityResult.error(
            error=bridge_output,
            source_backend="smithery",
            retryable=True,
        )

    return CapabilityResult.ok(
        payload={"output": bridge_output},
        source_backend="smithery",
    )
