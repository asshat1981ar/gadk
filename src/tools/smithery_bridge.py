import asyncio
import json

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

_SMITHERY_RETRY_WAIT = wait_exponential(multiplier=0.01, min=0, max=0.05)


class SmitheryCommandError(RuntimeError):
    """Raised when the Smithery CLI reports a retryable command failure."""


@retry(
    stop=stop_after_attempt(3),
    wait=_SMITHERY_RETRY_WAIT,
    retry=retry_if_exception_type(SmitheryCommandError),
    reraise=True,
)
async def _invoke_smithery_tool(server_id: str, tool_name: str, args: dict) -> str:
    """Run the Smithery CLI with narrow retry coverage around command failures."""
    args_json = json.dumps(args)
    cmd = ["smithery", "tool", "call", f"{server_id}", tool_name, args_json]

    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        error_msg = stderr.decode().strip() or stdout.decode().strip()
        raise SmitheryCommandError(error_msg)

    return stdout.decode().strip()


async def call_smithery_tool(server_id: str, tool_name: str, args: dict) -> str:
    """
    Dynamically calls an MCP tool from the Smithery marketplace.
    Args:
        server_id: The ID of the Smithery server (e.g., 'neon', 'slack').
        tool_name: The name of the tool to call.
        args: A dictionary of arguments for the tool.
    """
    # In some environments, server_id might be a full URL, but we use the ID for the CLI
    try:
        return await _invoke_smithery_tool(server_id, tool_name, args)
    except SmitheryCommandError as e:
        return f"Smithery Error: {e!s}"
    except Exception as e:
        return f"Bridge Error: {e!s}"
