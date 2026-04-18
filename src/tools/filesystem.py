"""Filesystem tools with path sandboxing guardrails for agent use."""

import fnmatch
import os
from pathlib import Path
from typing import List

from src.observability.logger import get_logger
from src.observability.metrics import tool_timer

logger = get_logger("filesystem_tools")

# Project root is the directory containing this file's package (src/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Denylist: sensitive files that should never be read or written
_DENYLIST_PATTERNS = [
    ".env",
    ".env.*",
    "*.key",
    "*.pem",
    "*.p12",
    "*.crt",
    "*.secret",
    "sessions.db",
    "prompt_queue.jsonl",
]

# Write allowlist: directories where agents are permitted to write
_WRITE_ALLOWED_DIRS = [
    "src",
    "tests",
    "docs",
    "staged_agents",
]

_READ_MAX_BYTES = 100_000
_WRITE_MAX_BYTES = 500_000


class FilesystemGuardrailError(Exception):
    """Raised when a filesystem operation violates guardrails."""
    pass


def _resolve_path(path: str) -> Path:
    """Resolve a path relative to the project root, blocking traversal escapes."""
    if not path:
        raise FilesystemGuardrailError("Path cannot be empty.")

    # Reject absolute paths outside the project
    raw = Path(path)
    if raw.is_absolute():
        try:
            raw.relative_to(_PROJECT_ROOT)
        except ValueError:
            raise FilesystemGuardrailError(
                f"Absolute paths outside the project root are not allowed: {path}"
            )
        resolved = raw.resolve()
    else:
        resolved = (_PROJECT_ROOT / path).resolve()

    # Block traversal above project root
    try:
        resolved.relative_to(_PROJECT_ROOT)
    except ValueError:
        raise FilesystemGuardrailError(
            f"Path traversal outside project root is not allowed: {path}"
        )

    return resolved


def _check_denylist(resolved: Path) -> None:
    """Check if the resolved path matches any denylist pattern."""
    name = resolved.name
    for pattern in _DENYLIST_PATTERNS:
        if fnmatch.fnmatch(name, pattern):
            raise FilesystemGuardrailError(
                f"Access to '{resolved.name}' is blocked by security policy."
            )


def _check_write_allowlist(resolved: Path) -> None:
    """Ensure the resolved path is within an allowed write directory."""
    try:
        rel = resolved.relative_to(_PROJECT_ROOT)
    except ValueError:
        raise FilesystemGuardrailError(
            f"Write outside project root is not allowed: {resolved}"
        )

    top_level = rel.parts[0] if rel.parts else ""
    if top_level not in _WRITE_ALLOWED_DIRS:
        raise FilesystemGuardrailError(
            f"Writes are only permitted under these directories: {_WRITE_ALLOWED_DIRS}. "
            f"Attempted write to: {top_level}/"
        )


@tool_timer("ReadFile")
def read_file(path: str) -> str:
    """
    Read the contents of a text file within the project.

    Args:
        path: Relative path from the project root (e.g., 'src/main.py').

    Returns:
        The file contents as a string.
    """
    resolved = _resolve_path(path)
    _check_denylist(resolved)

    if not resolved.exists():
        raise FilesystemGuardrailError(f"File not found: {path}")
    if not resolved.is_file():
        raise FilesystemGuardrailError(f"Path is not a file: {path}")

    size = resolved.stat().st_size
    if size > _READ_MAX_BYTES:
        raise FilesystemGuardrailError(
            f"File size ({size} bytes) exceeds read limit of {_READ_MAX_BYTES} bytes."
        )

    content = resolved.read_text(encoding="utf-8")
    logger.info(
        f"read_file: {path}",
        extra={"tool": "read_file", "agent": ""},
    )
    return content


@tool_timer("WriteFile")
def write_file(path: str, content: str) -> str:
    """
    Write text content to a file within the project.

    Args:
        path: Relative path from the project root (e.g., 'src/staged_agents/my_tool.py').
        content: The text content to write.

    Returns:
        Confirmation message with the written path.
    """
    resolved = _resolve_path(path)
    _check_denylist(resolved)
    _check_write_allowlist(resolved)

    if len(content.encode("utf-8")) > _WRITE_MAX_BYTES:
        raise FilesystemGuardrailError(
            f"Content size ({len(content.encode('utf-8'))} bytes) exceeds write limit of {_WRITE_MAX_BYTES} bytes."
        )

    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content, encoding="utf-8")

    logger.info(
        f"write_file: {path}",
        extra={"tool": "write_file", "agent": ""},
    )
    return f"Successfully wrote {len(content)} characters to {path}"


@tool_timer("ListDirectory")
def list_directory(path: str = ".") -> List[dict]:
    """
    List files and directories at the given path.

    Args:
        path: Relative path from the project root. Defaults to project root.

    Returns:
        List of dicts with 'name', 'type' ('file' or 'directory'), and 'size' (for files).
    """
    resolved = _resolve_path(path)

    if not resolved.exists():
        raise FilesystemGuardrailError(f"Directory not found: {path}")
    if not resolved.is_dir():
        raise FilesystemGuardrailError(f"Path is not a directory: {path}")

    entries = []
    for entry in sorted(resolved.iterdir(), key=lambda e: e.name):
        item = {"name": entry.name, "type": "directory" if entry.is_dir() else "file"}
        if entry.is_file():
            item["size"] = entry.stat().st_size
        entries.append(item)

    logger.info(
        f"list_directory: {path}",
        extra={"tool": "list_directory", "agent": ""},
    )
    return entries
