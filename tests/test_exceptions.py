"""Tests for structured exception classes."""

import json

import pytest

from src.exceptions import (
    ConfigurationError,
    PromptProcessingError,
    SelfPromptError,
    SwarmError,
    SwarmLoopError,
    SwarmStartupError,
    ToolExecutionError,
)


class TestSwarmError:
    """Tests for the base SwarmError class."""

    def test_basic_exception(self):
        """Test basic exception creation."""
        exc = SwarmError("test message")
        assert str(exc) == "test message"
        assert exc.session_id is None
        assert exc.context == {}

    def test_with_session_id(self):
        """Test exception with session_id."""
        exc = SwarmError("test", session_id="session-123")
        assert exc.session_id == "session-123"
        ctx = exc.to_log_context()
        assert ctx["session_id"] == "session-123"

    def test_with_context(self):
        """Test exception with context."""
        exc = SwarmError("test", context={"key": "value", "count": 42})
        assert exc.context == {"key": "value", "count": 42}
        ctx = exc.to_log_context()
        assert ctx["key"] == "value"
        assert ctx["count"] == 42

    def test_log_context_combined(self):
        """Test log context combines session_id and context."""
        exc = SwarmError("test", session_id="session-123", context={"key": "value"})
        ctx = exc.to_log_context()
        assert ctx["session_id"] == "session-123"
        assert ctx["key"] == "value"


class TestSwarmStartupError:
    """Tests for SwarmStartupError."""

    def test_with_component(self):
        """Test startup error with component info."""
        exc = SwarmStartupError(
            "Failed to initialize",
            component="session_service",
            session_id="session-123",
        )
        assert exc.component == "session_service"
        assert exc.session_id == "session-123"
        assert str(exc) == "Failed to initialize"

    def test_without_component(self):
        """Test startup error without component."""
        exc = SwarmStartupError("Generic failure")
        assert exc.component is None


class TestToolExecutionError:
    """Tests for ToolExecutionError."""

    def test_with_tool_info(self):
        """Test tool error with tool name and args."""
        exc = ToolExecutionError(
            "Tool failed",
            tool_name="execute_capability",
            tool_args={"capability": "search", "query": "test"},
            session_id="session-123",
        )
        assert exc.tool_name == "execute_capability"
        assert exc.tool_args == {"capability": "search", "query": "test"}
        ctx = exc.to_log_context()
        assert ctx["session_id"] == "session-123"

    def test_default_tool_args(self):
        """Test tool error defaults empty args."""
        exc = ToolExecutionError("Tool failed")
        assert exc.tool_args == {}


class TestPromptProcessingError:
    """Tests for PromptProcessingError."""

    def test_with_prompt_details(self):
        """Test prompt error with full details."""
        exc = PromptProcessingError(
            "Processing failed",
            prompt="What is the weather?",
            stage="adk_execution",
            use_planner_fallback=True,
            session_id="session-123",
        )
        assert exc.prompt == "What is the weather?"
        assert exc.stage == "adk_execution"
        assert exc.use_planner_fallback is True

    def test_defaults(self):
        """Test prompt error defaults."""
        exc = PromptProcessingError("Failed")
        assert exc.prompt is None
        assert exc.stage is None
        assert exc.use_planner_fallback is False


class TestConfigurationError:
    """Tests for ConfigurationError."""

    def test_with_config_details(self):
        """Test config error with key and value."""
        exc = ConfigurationError(
            "Invalid configuration",
            config_key="OPENROUTER_API_KEY",
            config_value="invalid",
        )
        assert exc.config_key == "OPENROUTER_API_KEY"
        assert exc.config_value == "invalid"


class TestSwarmLoopError:
    """Tests for SwarmLoopError."""

    def test_with_iteration(self):
        """Test loop error with iteration count."""
        exc = SwarmLoopError(
            "Loop iteration failed",
            iteration=42,
            recoverable=True,
            session_id="session-123",
        )
        assert exc.iteration == 42
        assert exc.recoverable is True

    def test_not_recoverable(self):
        """Test non-recoverable loop error."""
        exc = SwarmLoopError("Critical failure", recoverable=False)
        assert exc.recoverable is False


class TestSelfPromptError:
    """Tests for SelfPromptError."""

    def test_with_tick_count(self):
        """Test self-prompt error with tick count."""
        exc = SelfPromptError(
            "Tick failed",
            tick_count=100,
            session_id="session-123",
        )
        assert exc.tick_count == 100


class TestExceptionChaining:
    """Tests for exception chaining behavior."""

    def test_raise_from_cause(self):
        """Test that exceptions can be chained with 'from'."""
        original = ValueError("Original error")
        with pytest.raises(SwarmStartupError) as exc_info:
            try:
                raise original
            except ValueError as e:
                raise SwarmStartupError("Startup failed") from e

        assert exc_info.value.__cause__ is original
        assert str(exc_info.value) == "Startup failed"

    def test_tool_error_chain(self):
        """Test tool error chaining."""
        original = RuntimeError("Network failure")
        with pytest.raises(ToolExecutionError) as exc_info:
            try:
                raise original
            except RuntimeError as e:
                raise ToolExecutionError(
                    "Tool execution failed",
                    tool_name="web_search",
                ) from e

        assert exc_info.value.__cause__ is original
        assert exc_info.value.tool_name == "web_search"

    def test_prompt_error_chain(self):
        """Test prompt error chaining with fallback indication."""
        original = json.JSONDecodeError("Invalid JSON", "doc", 0)
        with pytest.raises(PromptProcessingError) as exc_info:
            try:
                raise original
            except json.JSONDecodeError as e:
                raise PromptProcessingError(
                    "ADK failed, planner fallback available",
                    use_planner_fallback=True,
                ) from e

        assert isinstance(exc_info.value.__cause__, json.JSONDecodeError)
        assert exc_info.value.use_planner_fallback is True


class TestInheritance:
    """Tests for exception inheritance."""

    def test_all_inherit_from_swarm_error(self):
        """Test all exceptions inherit from SwarmError."""
        errors = [
            SwarmStartupError("test"),
            ToolExecutionError("test"),
            PromptProcessingError("test"),
            ConfigurationError("test"),
            SwarmLoopError("test"),
            SelfPromptError("test"),
        ]
        for exc in errors:
            assert isinstance(exc, SwarmError)

    def test_catch_base_exception(self):
        """Test that all exceptions can be caught as SwarmError."""
        caught = []
        for exc_class in [
            SwarmStartupError,
            ToolExecutionError,
            PromptProcessingError,
            ConfigurationError,
            SwarmLoopError,
            SelfPromptError,
        ]:
            try:
                raise exc_class("test")
            except SwarmError as e:
                caught.append(type(e).__name__)

        assert len(caught) == 6
