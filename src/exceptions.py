"""Structured exception classes for the Cognitive Foundry Swarm.

This module defines specific exception types for different failure modes,
enabling better error handling, debugging, and observability.
"""

from __future__ import annotations

from typing import Any


class SwarmError(Exception):
    """Base exception for all Swarm-related errors.

    Provides common functionality for error context preservation and structured logging.
    """

    def __init__(
        self,
        message: str,
        *,
        session_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.session_id = session_id
        self.context = context or {}

    def to_log_context(self) -> dict[str, Any]:
        """Return structured context for logging."""
        ctx = dict(self.context)
        if self.session_id:
            ctx["session_id"] = self.session_id
        return ctx


class SwarmStartupError(SwarmError):
    """Raised when the swarm fails to initialize.

    This includes failures during:
    - Service initialization (session service, etc.)
    - Session creation
    - Runner setup
    - Configuration validation
    - API key verification
    """

    def __init__(
        self,
        message: str,
        *,
        component: str | None = None,
        session_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, session_id=session_id, context=context)
        self.component = component


class ToolExecutionError(SwarmError):
    """Raised when a tool execution fails.

    This captures failures from:
    - Capability execution
    - Tool registration issues
    - Handler execution failures
    """

    def __init__(
        self,
        message: str,
        *,
        tool_name: str | None = None,
        tool_args: dict[str, Any] | None = None,
        session_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, session_id=session_id, context=context)
        self.tool_name = tool_name
        self.tool_args = tool_args or {}


class PromptProcessingError(SwarmError):
    """Raised when prompt processing fails.

    This includes failures during:
    - ADK runner execution
    - Event processing
    - Fallback to planner after JSON errors
    - Response generation
    """

    def __init__(
        self,
        message: str,
        *,
        prompt: str | None = None,
        stage: str | None = None,
        use_planner_fallback: bool = False,
        session_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, session_id=session_id, context=context)
        self.prompt = prompt
        self.stage = stage
        self.use_planner_fallback = use_planner_fallback


class ConfigurationError(SwarmError):
    """Raised when configuration validation fails.

    This includes:
    - Missing required environment variables
    - Invalid configuration values
    - Unsupported configuration combinations
    """

    def __init__(
        self,
        message: str,
        *,
        config_key: str | None = None,
        config_value: Any | None = None,
        session_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, session_id=session_id, context=context)
        self.config_key = config_key
        self.config_value = config_value


class SwarmLoopError(SwarmError):
    """Raised when the swarm loop encounters a critical error.

    This captures failures in the main autonomous loop:
    - Shutdown check failures
    - Prompt dequeue failures
    - Loop iteration crashes
    """

    def __init__(
        self,
        message: str,
        *,
        iteration: int | None = None,
        recoverable: bool = True,
        session_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, session_id=session_id, context=context)
        self.iteration = iteration
        self.recoverable = recoverable


class SelfPromptError(SwarmError):
    """Raised when the self-prompt background task fails.

    This captures failures in the self-prompt tick loop.
    """

    def __init__(
        self,
        message: str,
        *,
        tick_count: int | None = None,
        session_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, session_id=session_id, context=context)
        self.tick_count = tick_count
