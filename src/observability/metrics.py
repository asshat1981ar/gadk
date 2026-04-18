import asyncio
import functools
import json
import os
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class AgentMetrics:
    calls_total: int = 0
    errors_total: int = 0
    duration_seconds_sum: float = 0.0
    duration_seconds_count: int = 0
    last_error: str = ""


@dataclass
class ToolMetrics:
    calls_total: int = 0
    errors_total: int = 0
    duration_seconds_sum: float = 0.0
    duration_seconds_count: int = 0
    last_error: str = ""


class MetricsRegistry:
    def __init__(self, filename: str = "metrics.jsonl") -> None:
        self.filename = filename
        self._agent_metrics: dict[str, AgentMetrics] = defaultdict(AgentMetrics)
        self._tool_metrics: dict[str, ToolMetrics] = defaultdict(ToolMetrics)
        self._token_usage: dict[str, int] = defaultdict(int)
        self._load()

    def record_agent_call(
        self, agent_name: str, duration: float, error: Exception | None = None
    ) -> None:
        m = self._agent_metrics[agent_name]
        m.calls_total += 1
        m.duration_seconds_sum += duration
        m.duration_seconds_count += 1
        if error:
            m.errors_total += 1
            m.last_error = str(error)
        self._persist()

    def record_tool_call(
        self, tool_name: str, duration: float, error: Exception | None = None
    ) -> None:
        m = self._tool_metrics[tool_name]
        m.calls_total += 1
        m.duration_seconds_sum += duration
        m.duration_seconds_count += 1
        if error:
            m.errors_total += 1
            m.last_error = str(error)
        self._persist()

    def record_tokens(self, agent_name: str, tokens: int) -> None:
        self._token_usage[agent_name] += tokens
        self._persist()

    def get_summary(self) -> dict[str, Any]:
        def avg_duration(m: AgentMetrics | ToolMetrics) -> float:
            if m.duration_seconds_count == 0:
                return 0.0
            return m.duration_seconds_sum / m.duration_seconds_count

        return {
            "agents": {
                name: {
                    "calls_total": m.calls_total,
                    "errors_total": m.errors_total,
                    "avg_duration_seconds": avg_duration(m),
                    "last_error": m.last_error,
                }
                for name, m in self._agent_metrics.items()
            },
            "tools": {
                name: {
                    "calls_total": m.calls_total,
                    "errors_total": m.errors_total,
                    "avg_duration_seconds": avg_duration(m),
                    "last_error": m.last_error,
                }
                for name, m in self._tool_metrics.items()
            },
            "token_usage": dict(self._token_usage),
        }

    def reset(self) -> None:
        self._agent_metrics.clear()
        self._tool_metrics.clear()
        self._token_usage.clear()
        if os.path.exists(self.filename):
            os.remove(self.filename)

    def _persist(self) -> None:
        payload = {
            "agents": {name: asdict(m) for name, m in self._agent_metrics.items()},
            "tools": {name: asdict(m) for name, m in self._tool_metrics.items()},
            "token_usage": dict(self._token_usage),
        }
        with open(self.filename, "w") as f:
            json.dump(payload, f, indent=2)

    def _load(self) -> None:
        if not os.path.exists(self.filename):
            return
        try:
            with open(self.filename) as f:
                payload = json.load(f)
            for name, data in payload.get("agents", {}).items():
                self._agent_metrics[name] = AgentMetrics(**data)
            for name, data in payload.get("tools", {}).items():
                self._tool_metrics[name] = ToolMetrics(**data)
            for name, count in payload.get("token_usage", {}).items():
                self._token_usage[name] = count
        except (json.JSONDecodeError, TypeError):
            pass


# Global registry
registry = MetricsRegistry()


def agent_timer(agent_name: str) -> Callable:
    """Decorator to time agent method calls."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            error = None
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error = e
                raise
            finally:
                duration = time.perf_counter() - start
                registry.record_agent_call(agent_name, duration, error)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            error = None
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error = e
                raise
            finally:
                duration = time.perf_counter() - start
                registry.record_agent_call(agent_name, duration, error)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def tool_timer(tool_name: str) -> Callable:
    """Decorator to time tool method calls."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            error = None
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error = e
                raise
            finally:
                duration = time.perf_counter() - start
                registry.record_tool_call(tool_name, duration, error)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            error = None
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error = e
                raise
            finally:
                duration = time.perf_counter() - start
                registry.record_tool_call(tool_name, duration, error)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
