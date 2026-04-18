from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.mcp.server import build_mcp_server as build_mcp_server

__all__ = ["build_mcp_server"]


def __getattr__(name: str) -> Any:
    if name == "build_mcp_server":
        from src.mcp.server import build_mcp_server

        return build_mcp_server
    msg = f"module 'src.mcp' has no attribute {name!r}"
    raise AttributeError(msg)
