"""Tests for the Pulse agent's health monitoring and metrics tools."""

from __future__ import annotations

import json
import os
import pytest
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from src.agents.pulse import (
    HealthReport,
    AlertSeverity,
    check_agent_health,
    get_system_metrics,
    check_api_rate_limits,
    monitor_queue_depth,
    send_alert,
    generate_health_report,
    log_metric,
    evaluate_alert_conditions,
    pulse_gate_payload,
)


class TestHealthReport:
    def test_health_report_creation(self) -> None:
        report = HealthReport(
            task_id="test-123",
            status="HEALTHY",
            agent_health={"Builder": {"status": "healthy", "last_seen": datetime.now(UTC).isoformat()}},
            system_metrics={"cpu_percent": 45.0, "memory_percent": 60.0, "disk_percent": 70.0},
            queue_depth=5,
            alerts=[],
            timestamp=datetime.now(UTC),
        )
        assert report.task_id == "test-123"
        assert report.status == "HEALTHY"
        assert report.queue_depth == 5

    def test_health_report_markdown_contains_all_sections(self) -> None:
        report = HealthReport(
            task_id="test-123",
            status="HEALTHY",
            agent_health={"Builder": {"status": "healthy"}},
            system_metrics={"cpu_percent": 45.0, "memory_percent": 60.0},
            queue_depth=5,
            alerts=[],
            timestamp=datetime.now(UTC),
        )
        md = report.as_markdown()
        assert "# Health Report" in md
        assert f"Task: `test-123`" in md
        assert "## Status" in md
        assert "## Agent Health" in md
        assert "## System Metrics" in md
        assert "## Queue Depth" in md


class TestCheckAgentHealth:
    def test_check_agent_health_returns_dict(self) -> None:
        # Mock state manager with some tasks
        mock_tasks = {
            "task-1": {"status": "RUNNING", "agent": "Builder", "updated_at": datetime.now(UTC).isoformat()},
            "task-2": {"status": "STALLED", "agent": "Critic", "updated_at": "2024-01-01T00:00:00Z"},
        }
        
        with patch("src.agents.pulse.StateManager") as MockStateManager:
            mock_instance = MagicMock()
            mock_instance.get_all_tasks.return_value = mock_tasks
            MockStateManager.return_value = mock_instance
            
            result = check_agent_health()
            
        assert isinstance(result, dict)
        assert "Builder" in result or "Critic" in result  # Should return agent health data

    def test_check_agent_health_handles_empty_state(self) -> None:
        with patch("src.agents.pulse.StateManager") as MockStateManager:
            mock_instance = MagicMock()
            mock_instance.get_all_tasks.return_value = {}
            MockStateManager.return_value = mock_instance
            
            result = check_agent_health()
            
        assert isinstance(result, dict)
        assert len(result) == 0 or result == {"total_agents": 0}


class TestGetSystemMetrics:
    def test_get_system_metrics_returns_expected_keys(self) -> None:
        result = get_system_metrics()
        
        assert isinstance(result, dict)
        assert "cpu_percent" in result
        assert "memory_percent" in result
        assert "disk_percent" in result
        assert "timestamp" in result

    def test_get_system_metrics_values_are_numeric(self) -> None:
        result = get_system_metrics()
        
        assert isinstance(result["cpu_percent"], (int, float))
        assert isinstance(result["memory_percent"], (int, float))
        assert isinstance(result["disk_percent"], (int, float))


class TestCheckApiRateLimits:
    def test_check_api_rate_limits_returns_dict(self) -> None:
        mock_metrics = {
            "agents": {},
            "tools": {},
            "token_usage": {"Ideator": 1000},
        }
        
        with patch("src.observability.metrics.registry.get_summary", return_value=mock_metrics):
            result = check_api_rate_limits()
            
        assert isinstance(result, dict)
        assert "token_usage" in result

    def test_check_api_rate_limits_calculates_percentages(self) -> None:
        with patch("src.observability.metrics.registry.get_summary") as mock_summary:
            mock_summary.return_value = {
                "agents": {},
                "tools": {},
                "token_usage": {"Ideator": 85000},  # Just under typical limit
            }
            
            result = check_api_rate_limits(token_limit=100000)
            
        assert "overall_usage_percent" in result
        assert isinstance(result["overall_usage_percent"], (int, float))


class TestMonitorQueueDepth:
    def test_monitor_queue_depth_returns_int(self) -> None:
        with patch("src.agents.pulse.StateManager") as MockStateManager:
            mock_instance = MagicMock()
            mock_instance.get_all_tasks.return_value = {
                "task-1": {"status": "PENDING"},
                "task-2": {"status": "PENDING"},
                "task-3": {"status": "RUNNING"},
            }
            MockStateManager.return_value = mock_instance
            
            result = monitor_queue_depth()
            
        assert isinstance(result, int)
        assert result >= 0

    def test_monitor_queue_depth_counts_pending_only(self) -> None:
        with patch("src.agents.pulse.StateManager") as MockStateManager:
            mock_instance = MagicMock()
            mock_instance.get_all_tasks.return_value = {
                "task-1": {"status": "PENDING"},
                "task-2": {"status": "PENDING"},
                "task-3": {"status": "COMPLETED"},
                "task-4": {"status": "PENDING"},
            }
            MockStateManager.return_value = mock_instance
            
            result = monitor_queue_depth()
            
        assert result == 3


class TestSendAlert:
    def test_send_alert_creates_alert_entry(self, tmp_path) -> None:
        # Create a temporary alerts file
        alerts_file = tmp_path / "alerts.jsonl"
        
        with patch("src.agents.pulse.ALERTS_FILE", str(alerts_file)):
            result = send_alert(
                severity=AlertSeverity.WARNING.value,
                message="Test alert",
                source="test",
            )
            
        assert result["sent"] is True
        assert result["severity"] == "warning"

    def test_send_alert_persists_to_file(self, tmp_path) -> None:
        alerts_file = tmp_path / "alerts.jsonl"
        
        with patch("src.agents.pulse.ALERTS_FILE", str(alerts_file)):
            send_alert(
                severity=AlertSeverity.ERROR.value,
                message="Critical test alert",
                source="test",
                task_id="task-123",
            )
            
        with open(alerts_file) as f:
            line = f.readline().strip()
            alert = json.loads(line)
            
        assert alert["severity"] == "error"
        assert alert["message"] == "Critical test alert"
        assert alert["task_id"] == "task-123"


class TestGenerateHealthReport:
    def test_generate_health_report_returns_dict(self) -> None:
        result = generate_health_report(task_id="test-report")
        
        assert isinstance(result, dict)
        assert result["task_id"] == "test-report"
        assert "status" in result
        assert "timestamp" in result

    def test_generate_health_report_status_determination(self) -> None:
        # Provide data that will trigger DEGRADED status due to high values
        result = generate_health_report(
            task_id="test-report-2",
            agent_health={"Builder": {"status": "degraded", "stalled_count": 1}},
            system_metrics={"cpu_percent": 85},  # Above DEFAULT_CPU_THRESHOLD
            queue_depth=75,  # Above DEFAULT_QUEUE_THRESHOLD
        )
            
        assert result["status"] == "DEGRADED"


class TestLogMetric:
    def test_log_metric_writes_to_file(self, tmp_path) -> None:
        metrics_file = tmp_path / "pulse_metrics.jsonl"
        
        with patch("src.agents.pulse.METRICS_FILE", str(metrics_file)):
            result = log_metric(
                metric_name="test_metric",
                value=42.0,
                labels={"agent": "Builder"},
            )
            
        assert result["logged"] is True
        
        with open(metrics_file) as f:
            line = f.readline().strip()
            metric = json.loads(line)
            
        assert metric["metric_name"] == "test_metric"
        assert metric["value"] == 42.0
        assert metric["labels"] == {"agent": "Builder"}


class TestEvaluateAlertConditions:
    def test_evaluate_detects_high_queue_depth(self) -> None:
        # Use a value higher than the default threshold of 50
        result = evaluate_alert_conditions(
            queue_depth=100,
            api_usage_percent=50,
            error_rate=0.1,
            agent_health={"Builder": {"status": "healthy"}},
        )
            
        assert any("queue depth" in alert["message"].lower() for alert in result)

    def test_evaluate_detects_high_api_usage(self) -> None:
        with patch.dict("os.environ", {"PULSE_API_THRESHOLD": "80"}):
            result = evaluate_alert_conditions(
                queue_depth=1,
                api_usage_percent=85,
                error_rate=0.1,
                agent_health={"Builder": {"status": "healthy"}},
            )
            
        assert any("API" in alert["message"] for alert in result)

    def test_evaluate_detects_unhealthy_agent(self) -> None:
        result = evaluate_alert_conditions(
            queue_depth=1,
            api_usage_percent=50,
            error_rate=0.1,
            agent_health={"Builder": {"status": "unresponsive"}},
        )
        
        assert any("Builder" in alert["message"] for alert in result)

    def test_evaluate_detects_high_error_rate(self) -> None:
        with patch.dict("os.environ", {"PULSE_ERROR_THRESHOLD": "0.15"}):
            result = evaluate_alert_conditions(
                queue_depth=1,
                api_usage_percent=50,
                error_rate=0.20,
                agent_health={"Builder": {"status": "healthy"}},
            )
            
        assert any("error rate" in alert["message"].lower() for alert in result)


class TestPulseGatePayload:
    def test_pulse_gate_payload_shape(self) -> None:
        report = {
            "task_id": "pulse-test",
            "status": "HEALTHY",
            "agent_health": {},
            "system_metrics": {"cpu_percent": 45.0},
            "queue_depth": 0,
            "alerts": [],
            "timestamp": datetime.now(UTC).isoformat(),
        }
        
        payload = pulse_gate_payload(report)
        
        assert payload["phase"] == "OPERATE"
        assert "body" in payload
        assert "pulse-test" in payload["body"]


class TestAlertSeverity:
    def test_alert_severity_values(self) -> None:
        assert AlertSeverity.INFO.value == "info"
        assert AlertSeverity.WARNING.value == "warning"
        assert AlertSeverity.ERROR.value == "error"
        assert AlertSeverity.CRITICAL.value == "critical"
