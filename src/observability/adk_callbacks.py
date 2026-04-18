import time
from typing import Any, Dict, Optional

from src.observability.logger import get_logger
from src.observability.metrics import registry

logger = get_logger("adk_callbacks")


class ObservabilityCallback:
    """ADK callback plugin that auto-logs and auto-records metrics."""

    def __init__(self):
        self._tool_start_times: Dict[str, float] = {}
        self._agent_start_times: Dict[str, float] = {}

    def before_agent(self, agent_name: str, instruction: str) -> None:
        self._agent_start_times[agent_name] = time.perf_counter()
        logger.info(f"Agent {agent_name} started", extra={"agent": agent_name})

    def after_agent(self, agent_name: str, instruction: str, response: Any) -> None:
        start = self._agent_start_times.pop(agent_name, None)
        duration = time.perf_counter() - start if start else 0.0

        # Best-effort cost extraction from LiteLLM response
        cost = 0.0
        try:
            from litellm import completion_cost
            # ADK wraps the response; try common attributes
            raw = getattr(response, "_raw_response", response)
            if raw is not None:
                cost = completion_cost(raw)
        except (ImportError, AttributeError, TypeError, ValueError) as exc:
            logger.debug(
                "cost extraction failed for agent %s: %s", agent_name, exc
            )
            cost = 0.0

        if cost > 0:
            from src.observability.cost_tracker import CostTracker
            CostTracker().record_cost("global", agent_name, cost)

        registry.record_agent_call(agent_name, duration)
        logger.info(f"Agent {agent_name} finished", extra={"agent": agent_name, "cost_usd": cost})

    def before_tool_call(self, tool_name: str, tool_args: Dict[str, Any]) -> None:
        self._tool_start_times[tool_name] = time.perf_counter()
        logger.info(f"Tool {tool_name} called", extra={"tool": tool_name})

    def after_tool_call(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        result: Any,
        error: Optional[Exception] = None,
    ) -> None:
        start = self._tool_start_times.pop(tool_name, None)
        duration = time.perf_counter() - start if start else 0.0
        registry.record_tool_call(tool_name, duration, error)
        if error:
            logger.error(f"Tool {tool_name} failed: {error}", extra={"tool": tool_name})
        else:
            logger.info(f"Tool {tool_name} succeeded", extra={"tool": tool_name})
