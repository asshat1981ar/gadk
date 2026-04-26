"""Pulse agent — owner of the OPERATE SDLC phase.

Monitors swarm health, system metrics, API usage, and task queue depth.
Generates health reports and sends alerts when thresholds are exceeded.
Responsible for operational monitoring and observability during the
OPERATE phase.

Design choices:
- Pure functions at module scope; ADK agent is optional and gated on
  ``google.adk`` being importable (mirrors architect.py and governor.py).
- Integrates with existing observability stack: metrics registry, structured
  logging, and state management.
- Alert conditions are configurable via environment variables with sensible
  defaults.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from src.config import Config
from src.observability.logger import get_logger
from src.services.sdlc_phase import Phase
from src.state import StateManager

logger = get_logger("pulse")

# Default thresholds for alert conditions
DEFAULT_QUEUE_THRESHOLD = int(os.getenv("PULSE_QUEUE_THRESHOLD", "50"))
DEFAULT_API_THRESHOLD = int(os.getenv("PULSE_API_THRESHOLD", "80"))
DEFAULT_ERROR_THRESHOLD = float(os.getenv("PULSE_ERROR_THRESHOLD", "0.10"))
DEFAULT_CPU_THRESHOLD = int(os.getenv("PULSE_CPU_THRESHOLD", "80"))
DEFAULT_MEMORY_THRESHOLD = int(os.getenv("PULSE_MEMORY_THRESHOLD", "85"))
DEFAULT_DISK_THRESHOLD = int(os.getenv("PULSE_DISK_THRESHOLD", "90"))

# File paths for persistent storage
ALERTS_FILE = os.getenv("PULSE_ALERTS_FILE", "alerts.jsonl")
METRICS_FILE = os.getenv("PULSE_METRICS_FILE", "pulse_metrics.jsonl")


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class HealthReport:
    """Health report payload produced by Pulse at the OPERATE phase."""

    task_id: str
    status: str  # HEALTHY, DEGRADED, CRITICAL
    agent_health: dict[str, Any]
    system_metrics: dict[str, Any]
    queue_depth: int
    alerts: list[dict[str, Any]] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def as_markdown(self) -> str:
        """Render this report as markdown for human consumption."""
        lines = [
            "# Health Report",
            "",
            f"_Task: `{self.task_id}` · Status: {self.status} · Generated: {self.timestamp.isoformat()}_",
            "",
            "## Status",
            self.status,
            "",
            "## Agent Health",
        ]
        if self.agent_health:
            for agent, info in self.agent_health.items():
                lines.append(f"- **{agent}**: {info}")
        else:
            lines.append("- No agent health data available")
        lines.append("")

        lines.extend(
            [
                "## System Metrics",
                f"- CPU: {self.system_metrics.get('cpu_percent', 'N/A')}%",
                f"- Memory: {self.system_metrics.get('memory_percent', 'N/A')}%",
                f"- Disk: {self.system_metrics.get('disk_percent', 'N/A')}%",
                "",
            ]
        )

        lines.extend(
            [
                "## Queue Depth",
                str(self.queue_depth),
                "",
            ]
        )

        if self.alerts:
            lines.extend(
                [
                    "## Active Alerts",
                    f"*Total: {len(self.alerts)} alerts*",
                    "",
                ]
            )
            for alert in self.alerts:
                lines.append(
                    f"- [{alert.get('severity', 'unknown').upper()}] {alert.get('message', 'No message')}"
                )
        else:
            lines.extend(
                [
                    "## Active Alerts",
                    "No active alerts.",
                    "",
                ]
            )

        return "\n".join(lines).rstrip() + "\n"

    def model_dump(self) -> dict[str, Any]:
        """Serialize the health report to a dictionary."""
        return {
            "task_id": self.task_id,
            "status": self.status,
            "agent_health": self.agent_health,
            "system_metrics": self.system_metrics,
            "queue_depth": self.queue_depth,
            "alerts": self.alerts,
            "timestamp": self.timestamp.isoformat(),
        }


def _get_state_manager() -> StateManager:
    """Get or create a StateManager instance."""
    return StateManager()


def check_agent_health() -> dict[str, Any]:
    """Check if other agents are responsive based on task state.

    Returns a dictionary mapping agent names to their health status,
    including last seen timestamp, task counts, and any error conditions.
    """
    state_manager = _get_state_manager()
    tasks = state_manager.get_all_tasks()

    agent_health: dict[str, dict[str, Any]] = {}

    for task_id, task_data in tasks.items():
        agent = task_data.get("agent", "unknown")
        status = task_data.get("status", "UNKNOWN")
        updated_at = task_data.get("updated_at", datetime.now(UTC).isoformat())

        if agent not in agent_health:
            agent_health[agent] = {
                "status": "healthy",
                "task_count": 0,
                "stalled_count": 0,
                "last_seen": updated_at,
            }

        agent_health[agent]["task_count"] += 1

        if status == "STALLED":
            agent_health[agent]["stalled_count"] += 1

        # Always track the most recent timestamp
        if updated_at > agent_health[agent]["last_seen"]:
            agent_health[agent]["last_seen"] = updated_at

    # Mark agents as unhealthy if they have many stalled tasks
    for agent, health in agent_health.items():
        if health["stalled_count"] > 0:
            health["status"] = "degraded"
        if health["stalled_count"] > 5:
            health["status"] = "unresponsive"

    logger.info(
        "pulse.health.agents total=%d agents=%s", len(agent_health), list(agent_health.keys())
    )
    return agent_health


def get_system_metrics() -> dict[str, Any]:
    """Get current system metrics: CPU, memory, and disk usage.

    Returns a dictionary with usage percentages and timestamps.
    Safe to call on any platform; returns zero values if psutil is unavailable
    or fails for any reason.
    """
    try:
        import psutil

        # Try to get CPU percent without blocking (interval=0 or None for non-blocking)
        try:
            cpu_percent = psutil.cpu_percent(interval=None)
        except Exception:
            cpu_percent = 0.0

        # Get memory info
        try:
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used_gb = round(memory.used / (1024**3), 2)
            memory_total_gb = round(memory.total / (1024**3), 2)
        except Exception:
            memory_percent = 0.0
            memory_used_gb = 0.0
            memory_total_gb = 0.0

        # Get disk info
        try:
            disk = psutil.disk_usage("/")
            disk_percent = disk.percent
            disk_used_gb = round(disk.used / (1024**3), 2)
            disk_total_gb = round(disk.total / (1024**3), 2)
        except Exception:
            disk_percent = 0.0
            disk_used_gb = 0.0
            disk_total_gb = 0.0

        metrics = {
            "cpu_percent": round(cpu_percent, 2),
            "memory_percent": round(memory_percent, 2),
            "memory_used_gb": memory_used_gb,
            "memory_total_gb": memory_total_gb,
            "disk_percent": round(disk_percent, 2),
            "disk_used_gb": disk_used_gb,
            "disk_total_gb": disk_total_gb,
            "timestamp": datetime.now(UTC).isoformat(),
        }
    except (ImportError, Exception) as e:
        logger.debug("psutil not available or failed: %s", e)
        metrics = {
            "cpu_percent": 0.0,
            "memory_percent": 0.0,
            "memory_used_gb": 0.0,
            "memory_total_gb": 0.0,
            "disk_percent": 0.0,
            "disk_used_gb": 0.0,
            "disk_total_gb": 0.0,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    logger.info(
        "pulse.metrics.system cpu=%.1f memory=%.1f disk=%.1f",
        metrics.get("cpu_percent", 0),
        metrics.get("memory_percent", 0),
        metrics.get("disk_percent", 0),
    )
    return metrics


def check_api_rate_limits(token_limit: int = 100000) -> dict[str, Any]:
    """Check API usage and rate limits.

    Args:
        token_limit: The total token limit to check against (default: 100000)

    Returns a dictionary with token usage and percentage of limit used.
    """
    try:
        from src.observability.metrics import registry

        summary = registry.get_summary()
        token_usage = summary.get("token_usage", {})

        total_tokens = sum(token_usage.values())
        usage_percent = (total_tokens / token_limit) * 100 if token_limit > 0 else 0

        result = {
            "token_usage": token_usage,
            "total_tokens": total_tokens,
            "token_limit": token_limit,
            "overall_usage_percent": round(usage_percent, 2),
            "status": "OK" if usage_percent < DEFAULT_API_THRESHOLD else "WARNING",
        }
    except Exception as e:
        logger.error("Failed to check API rate limits: %s", e)
        result = {
            "token_usage": {},
            "total_tokens": 0,
            "token_limit": token_limit,
            "overall_usage_percent": 0.0,
            "status": "ERROR",
            "error": str(e),
        }

    logger.info(
        "pulse.metrics.api tokens=%d percent=%.1f status=%s",
        result.get("total_tokens", 0),
        result.get("overall_usage_percent", 0),
        result.get("status", "unknown"),
    )
    return result


def monitor_queue_depth(status_filter: list[str] | None = None) -> int:
    """Monitor task queue depth by counting tasks matching status filter.

    Args:
        status_filter: List of statuses to count (default: ['PENDING', 'RUNNING'])

    Returns the number of tasks matching the filter criteria.
    """
    if status_filter is None:
        status_filter = ["PENDING", "RUNNING"]

    state_manager = _get_state_manager()
    tasks = state_manager.get_all_tasks()

    depth = sum(1 for task in tasks.values() if task.get("status", "UNKNOWN") in status_filter)

    logger.info("pulse.queue.depth depth=%d filter=%s", depth, status_filter)
    return depth


def send_alert(
    severity: str,
    message: str,
    source: str,
    task_id: str = "",
    labels: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Send an alert by persisting it to the alerts log.

    Args:
        severity: Alert severity (info, warning, error, critical)
        message: Human-readable alert message
        source: Component that generated the alert
        task_id: Optional associated task ID
        labels: Optional key-value labels for filtering

    Returns a dictionary confirming the alert was sent.
    """
    alert = {
        "timestamp": datetime.now(UTC).isoformat(),
        "severity": severity,
        "message": message,
        "source": source,
        "task_id": task_id,
        "labels": labels or {},
    }

    # Append to alerts log file
    try:
        with open(ALERTS_FILE, "a") as f:
            f.write(json.dumps(alert) + "\n")
    except (IOError, OSError) as e:
        logger.error("Failed to write alert to file: %s", e)

    # Also log via structured logger
    log_level = {
        AlertSeverity.INFO: logger.info,
        AlertSeverity.WARNING: logger.warning,
        AlertSeverity.ERROR: logger.error,
        AlertSeverity.CRITICAL: logger.critical,
    }.get(AlertSeverity(severity), logger.info)

    log_level(
        "pulse.alert severity=%s source=%s message=%s",
        severity,
        source,
        message,
    )

    return {
        "sent": True,
        "severity": severity,
        "message": message,
        "source": source,
    }


def log_metric(
    metric_name: str,
    value: float,
    unit: str = "",
    labels: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Log a structured metric to the metrics log file.

    Args:
        metric_name: Name of the metric
        value: Numeric value
        unit: Optional unit string (e.g., "ms", "bytes")
        labels: Optional key-value labels for dimensionality

    Returns a dictionary confirming the metric was logged.
    """
    metric = {
        "timestamp": datetime.now(UTC).isoformat(),
        "metric_name": metric_name,
        "value": value,
        "unit": unit,
        "labels": labels or {},
    }

    try:
        with open(METRICS_FILE, "a") as f:
            f.write(json.dumps(metric) + "\n")
    except (IOError, OSError) as e:
        logger.error("Failed to write metric to file: %s", e)

    logger.info(
        "pulse.metric name=%s value=%.2f unit=%s",
        metric_name,
        value,
        unit,
    )

    return {
        "logged": True,
        "metric_name": metric_name,
        "value": value,
    }


def evaluate_alert_conditions(
    queue_depth: int,
    api_usage_percent: float,
    error_rate: float,
    agent_health: dict[str, Any],
) -> list[dict[str, Any]]:
    """Evaluate all alert conditions and return any triggered alerts.

    Checks:
    - Queue depth above threshold
    - API usage above threshold (default 80%)
    - Agent unresponsiveness
    - Error rate above threshold (default 10%)

    Args:
        queue_depth: Current queue depth
        api_usage_percent: Current API usage percentage
        error_rate: Current error rate (0.0 to 1.0)
        agent_health: Dictionary of agent health statuses

    Returns a list of alert dictionaries.
    """
    alerts = []

    # Check queue depth
    if queue_depth > DEFAULT_QUEUE_THRESHOLD:
        alerts.append(
            send_alert(
                severity=AlertSeverity.WARNING.value,
                message=f"Queue depth ({queue_depth}) exceeds threshold ({DEFAULT_QUEUE_THRESHOLD})",
                source="pulse.monitor.queue",
            )
        )

    # Check API usage
    if api_usage_percent > DEFAULT_API_THRESHOLD:
        alerts.append(
            send_alert(
                severity=AlertSeverity.WARNING.value,
                message=f"API usage ({api_usage_percent:.1f}%) exceeds threshold ({DEFAULT_API_THRESHOLD}%)",
                source="pulse.monitor.api",
            )
        )

    # Check for unresponsive agents
    for agent_name, health in agent_health.items():
        if isinstance(health, dict) and health.get("status") in ("unresponsive", "error"):
            alerts.append(
                send_alert(
                    severity=AlertSeverity.ERROR.value,
                    message=f"Agent '{agent_name}' is unresponsive or in error state",
                    source="pulse.monitor.agent",
                )
            )

    # Check error rate
    if error_rate > DEFAULT_ERROR_THRESHOLD:
        alerts.append(
            send_alert(
                severity=AlertSeverity.ERROR.value,
                message=f"Error rate ({error_rate:.2%}) exceeds threshold ({DEFAULT_ERROR_THRESHOLD:.2%})",
                source="pulse.monitor.errors",
            )
        )

    logger.info("pulse.alerts.evaluated triggered=%d", len(alerts))
    return alerts


def generate_health_report(
    task_id: str,
    agent_health: dict[str, Any] | None = None,
    system_metrics: dict[str, Any] | None = None,
    queue_depth: int | None = None,
) -> dict[str, Any]:
    """Generate a comprehensive health report.

    Collects metrics, evaluates alert conditions, and produces a full
    health report ready for the OPERATE phase.

    Args:
        task_id: Identifier for this health check/report
        agent_health: Optional pre-computed agent health (will compute if None)
        system_metrics: Optional pre-computed system metrics (will compute if None)
        queue_depth: Optional pre-computed queue depth (will compute if None)

    Returns a dictionary representing the health report.
    """
    if agent_health is None:
        agent_health = check_agent_health()

    if system_metrics is None:
        system_metrics = get_system_metrics()

    if queue_depth is None:
        queue_depth = monitor_queue_depth()

    # Get API usage
    api_metrics = check_api_rate_limits()

    # Get error rate from metrics registry if available
    try:
        from src.observability.metrics import registry

        summary = registry.get_summary()
        total_calls = sum(a.get("calls_total", 0) for a in summary.get("agents", {}).values())
        total_errors = sum(a.get("errors_total", 0) for a in summary.get("agents", {}).values())
        error_rate = total_errors / total_calls if total_calls > 0 else 0.0
    except Exception:
        error_rate = 0.0

    # Evaluate alert conditions
    alerts = evaluate_alert_conditions(
        queue_depth=queue_depth,
        api_usage_percent=api_metrics.get("overall_usage_percent", 0),
        error_rate=error_rate,
        agent_health=agent_health,
    )

    # Determine overall status
    if alerts:
        critical_count = sum(1 for a in alerts if a.get("severity") == AlertSeverity.CRITICAL.value)
        error_count = sum(1 for a in alerts if a.get("severity") == AlertSeverity.ERROR.value)

        if critical_count > 0:
            status = "CRITICAL"
        elif error_count > 0:
            status = "DEGRADED"
        else:
            status = "DEGRADED"
    else:
        status = "HEALTHY"

    report = HealthReport(
        task_id=task_id,
        status=status,
        agent_health=agent_health,
        system_metrics=system_metrics,
        queue_depth=queue_depth,
        alerts=alerts,
    )

    logger.info(
        "pulse.report task=%s status=%s queue_depth=%d alerts=%d",
        task_id,
        status,
        queue_depth,
        len(alerts),
    )

    return report.model_dump()


def pulse_gate_payload(report: dict[str, Any]) -> dict[str, Any]:
    """Shape a health report payload for the OPERATE-phase content gate.

    Returns ``{"body": <markdown>}`` so ``ContentGuardGate`` can inspect
    the report's body field.
    """
    # Create a HealthReport from the dict for markdown rendering
    health_report = HealthReport(
        task_id=report.get("task_id", "unknown"),
        status=report.get("status", "UNKNOWN"),
        agent_health=report.get("agent_health", {}),
        system_metrics=report.get("system_metrics", {}),
        queue_depth=report.get("queue_depth", 0),
        alerts=report.get("alerts", []),
        timestamp=datetime.fromisoformat(report.get("timestamp", datetime.now(UTC).isoformat())),
    )
    return {"body": health_report.as_markdown(), "phase": Phase.OPERATE.value}


# ---------------------------------------------------------------------------
# Optional ADK wiring — only activates when google-adk is present
# ---------------------------------------------------------------------------

pulse_agent: Any = None

try:  # pragma: no cover — ADK wiring is exercised by integration tests
    from google.adk.agents import Agent

    if Config.TEST_MODE:
        from src.testing.mock_llm import MockLiteLlm as LiteLlm
    else:
        from google.adk.models.lite_llm import LiteLlm

    _model = LiteLlm(
        model=Config.LLM_MODEL,
        api_key=Config.LLM_API_KEY,
        api_base=Config.LLM_API_BASE,
    )

    pulse_agent = Agent(
        name="Pulse",
        model=_model,
        description="Owns OPERATE phase: monitors swarm health, system metrics, and generates reports.",
        instruction="""You are the Pulse of the Cognitive Foundry.

Your job is to monitor swarm health during the OPERATE phase. Use the provided
tools to:
1. Check agent health with `check_agent_health`
2. Monitor system resources with `get_system_metrics`
3. Track API usage with `check_api_rate_limits`
4. Monitor task queue depth with `monitor_queue_depth`
5. Send alerts with `send_alert` when thresholds are exceeded
6. Generate comprehensive health reports with `generate_health_report`
7. Log metrics with `log_metric` for observability

Phase under your ownership: """
        + Phase.OPERATE.value,
        tools=[
            check_agent_health,
            get_system_metrics,
            check_api_rate_limits,
            monitor_queue_depth,
            send_alert,
            generate_health_report,
            log_metric,
            evaluate_alert_conditions,
            pulse_gate_payload,
        ],
    )
except ImportError as exc:
    logger.debug("ADK unavailable; pulse_agent disabled: %s", exc)


__all__ = [
    "AlertSeverity",
    "HealthReport",
    "pulse_agent",
    "check_agent_health",
    "get_system_metrics",
    "check_api_rate_limits",
    "monitor_queue_depth",
    "send_alert",
    "generate_health_report",
    "log_metric",
    "evaluate_alert_conditions",
    "pulse_gate_payload",
    "DEFAULT_QUEUE_THRESHOLD",
    "DEFAULT_API_THRESHOLD",
    "DEFAULT_ERROR_THRESHOLD",
    "ALERTS_FILE",
    "METRICS_FILE",
]
