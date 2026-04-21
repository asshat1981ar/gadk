"""Tests for the FinOps agent's cost tracking and budget management tools."""

from __future__ import annotations

import json
import os
import pytest
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch, Mock

from src.agents.finops import (
    get_current_costs,
    get_cost_breakdown,
    estimate_task_cost,
    check_budget_status,
    set_budget_alert,
    get_budget_recommendations,
    track_model_usage,
    suggest_cheaper_alternative,
    flag_expensive_operation,
    recommend_caching_strategy,
    BudgetAlert,
    ModelUsage,
)


@pytest.fixture
def mock_cost_tracker():
    """Fixture providing a mock CostTracker."""
    with patch("src.agents.finops.tracker") as mock_tracker:
        mock_tracker.get_summary.return_value = {
            "total_spend_usd": 5.50,
            "by_task": {"task-1": 2.50, "task-2": 3.00},
            "by_agent": {"Ideator": 3.00, "Builder": 2.50},
        }
        mock_tracker.get_total_spend.return_value = 5.50
        mock_tracker.get_task_spend.side_effect = lambda task_id: {
            "task-1": 2.50,
            "task-2": 3.00,
        }.get(task_id, 0.0)
        yield mock_tracker


class TestBudgetAlert:
    def test_budget_alert_creation(self) -> None:
        alert = BudgetAlert(
            threshold_amount=10.0,
            alert_type="daily",
            current_spend=5.50,
            is_triggered=False,
            created_at=datetime.now(UTC),
        )
        assert alert.threshold_amount == 10.0
        assert alert.alert_type == "daily"
        assert alert.current_spend == 5.50
        assert alert.is_triggered is False

    def test_budget_alert_triggers_when_exceeded(self) -> None:
        alert = BudgetAlert(
            threshold_amount=5.0,
            alert_type="task",
            current_spend=5.50,
            is_triggered=True,
            created_at=datetime.now(UTC),
        )
        assert alert.is_triggered is True


class TestModelUsage:
    def test_model_usage_creation(self) -> None:
        usage = ModelUsage(
            model_name="openrouter/openai/gpt-4o",
            agent_name="Ideator",
            token_count=1000,
            cost_usd=0.005,
            timestamp=datetime.now(UTC),
        )
        assert usage.model_name == "openrouter/openai/gpt-4o"
        assert usage.agent_name == "Ideator"
        assert usage.token_count == 1000
        assert usage.cost_usd == 0.005


class TestGetCurrentCosts:
    def test_get_current_costs_returns_expected_keys(self, mock_cost_tracker) -> None:
        result = get_current_costs()
        
        assert isinstance(result, dict)
        assert "current_total_usd" in result
        assert "by_task" in result
        assert "by_agent" in result
        assert "timestamp" in result

    def test_get_current_costs_values_from_tracker(self, mock_cost_tracker) -> None:
        result = get_current_costs()
        
        assert result["current_total_usd"] == 5.50
        assert result["by_task"]["task-1"] == 2.50
        assert result["by_agent"]["Ideator"] == 3.00


class TestGetCostBreakdown:
    def test_get_cost_breakdown_by_agent(self, mock_cost_tracker) -> None:
        result = get_cost_breakdown(group_by="agent")
        
        assert isinstance(result, dict)
        assert "breakdown_by_agent" in result
        assert result["breakdown_by_agent"]["Ideator"] == 3.00
        assert result["breakdown_by_agent"]["Builder"] == 2.50

    def test_get_cost_breakdown_by_task(self, mock_cost_tracker) -> None:
        result = get_cost_breakdown(group_by="task")
        
        assert isinstance(result, dict)
        assert "breakdown_by_task" in result
        assert result["breakdown_by_task"]["task-1"] == 2.50

    def test_get_cost_breakdown_default(self, mock_cost_tracker) -> None:
        """Default grouping should be by agent."""
        result = get_cost_breakdown()
        
        assert "breakdown_by_agent" in result


class TestEstimateTaskCost:
    def test_estimate_task_cost_basic(self) -> None:
        result = estimate_task_cost(
            task_description="Generate ideas for a new feature",
            expected_agents=["Ideator"],
            expected_complexity="medium",
        )
        
        assert isinstance(result, dict)
        assert "estimated_cost_usd" in result
        assert "confidence" in result
        assert "breakdown" in result
        assert result["estimated_cost_usd"] > 0

    def test_estimate_task_cost_high_complexity(self) -> None:
        result = estimate_task_cost(
            task_description="Refactor entire codebase",
            expected_agents=["Ideator", "Builder", "Critic"],
            expected_complexity="high",
        )
        
        # High complexity should produce higher estimates
        assert result["estimated_cost_usd"] > 0.01
        assert len(result["breakdown"]) >= 3  # Multiple agents

    def test_estimate_task_cost_low_complexity(self) -> None:
        result = estimate_task_cost(
            task_description="Simple documentation update",
            expected_agents=["Builder"],
            expected_complexity="low",
        )
        
        # Low complexity should produce lower estimates
        assert result["estimated_cost_usd"] < 0.10


class TestCheckBudgetStatus:
    def test_check_budget_status_within_limit(self, mock_cost_tracker) -> None:
        with patch("src.agents.finops.budget_usd", 100.0):
            result = check_budget_status()
        
        assert isinstance(result, dict)
        assert result["status"] == "WITHIN_BUDGET"
        assert result["current_spend_usd"] == 5.50
        assert result["budget_usd"] == 100.0
        assert result["remaining_usd"] == 94.50

    def test_check_budget_status_approaching_limit(self, mock_cost_tracker) -> None:
        with patch("src.agents.finops.budget_usd", 6.0):
            result = check_budget_status()
        
        assert result["status"] == "APPROACHING_LIMIT"
        assert "percent_used" in result
        assert result["percent_used"] > 80

    def test_check_budget_status_exceeded(self, mock_cost_tracker) -> None:
        with patch("src.agents.finops.budget_usd", 4.0):
            result = check_budget_status()
        
        assert result["status"] == "BUDGET_EXCEEDED"
        assert result["percent_used"] > 100


class TestSetBudgetAlert:
    def test_set_budget_alert_daily(self, tmp_path) -> None:
        alerts_file = tmp_path / "budget_alerts.jsonl"
        
        with patch("src.agents.finops.BUDGET_ALERTS_FILE", str(alerts_file)):
            result = set_budget_alert(
                threshold_amount=50.0,
                alert_type="daily",
            )
        
        assert isinstance(result, dict)
        assert result["created"] is True
        assert result["threshold_amount"] == 50.0
        assert result["alert_type"] == "daily"

    def test_set_budget_alert_task(self, tmp_path) -> None:
        alerts_file = tmp_path / "budget_alerts.jsonl"
        
        with patch("src.agents.finops.BUDGET_ALERTS_FILE", str(alerts_file)):
            result = set_budget_alert(
                threshold_amount=10.0,
                alert_type="task",
                task_id="task-123",
            )
        
        assert result["task_id"] == "task-123"
        assert result["alert_type"] == "task"


class TestGetBudgetRecommendations:
    def test_get_budget_recommendations_returns_list(self, mock_cost_tracker) -> None:
        result = get_budget_recommendations()
        
        assert isinstance(result, list)
        assert len(result) > 0
        
        for rec in result:
            assert "category" in rec
            assert "recommendation" in rec
            assert "potential_savings_percent" in rec

    def test_get_budget_recommendations_high_spend(self, mock_cost_tracker) -> None:
        # Set high spend relative to budget
        mock_cost_tracker.get_total_spend.return_value = 80.0
        
        with patch("src.agents.finops.budget_usd", 100.0):
            result = get_budget_recommendations()
        
        # Should include optimization recommendations
        categories = [r["category"] for r in result]
        assert any(c in categories for c in ["model_selection", "caching", "agent_optimization"])


class TestTrackModelUsage:
    def test_track_model_usage_records_entry(self, tmp_path) -> None:
        usage_file = tmp_path / "model_usage.jsonl"
        
        with patch("src.agents.finops.MODEL_USAGE_FILE", str(usage_file)):
            result = track_model_usage(
                model_name="openrouter/openai/gpt-4o",
                agent_name="Ideator",
                token_count=1000,
                cost_usd=0.005,
            )
        
        assert isinstance(result, dict)
        assert result["recorded"] is True
        assert result["model_name"] == "openrouter/openai/gpt-4o"
        assert result["agent_name"] == "Ideator"

        # Verify file was written
        with open(usage_file) as f:
            line = f.readline().strip()
            record = json.loads(line)
            
        assert record["model_name"] == "openrouter/openai/gpt-4o"
        assert record["token_count"] == 1000


class TestSuggestCheaperAlternative:
    def test_suggest_cheaper_alternative_for_expensive_model(self) -> None:
        result = suggest_cheaper_alternative(
            model_name="openrouter/openai/gpt-4o",
            task_type="code_generation",
        )
        
        assert isinstance(result, dict)
        assert "current_model" in result
        assert "suggested_alternatives" in result
        assert result["current_model"] == "openrouter/openai/gpt-4o"
        assert len(result["suggested_alternatives"]) > 0
        
        for alt in result["suggested_alternatives"]:
            assert "model" in alt
            assert "estimated_savings_percent" in alt
            assert "tradeoffs" in alt

    def test_suggest_alternative_already_cheapest(self) -> None:
        result = suggest_cheaper_alternative(
            model_name="openrouter/google/gemini-flash",
            task_type="simple_analysis",
        )
        
        # Should indicate current model is already economical
        assert "message" in result or len(result.get("suggested_alternatives", [])) == 0


class TestFlagExpensiveOperation:
    def test_flag_expensive_operation_high_cost(self) -> None:
        result = flag_expensive_operation(
            operation_type="embedding",
            estimated_cost_usd=5.00,
            task_id="task-123",
        )
        
        assert isinstance(result, dict)
        assert "is_flagged" in result
        assert result["is_flagged"] is True
        assert "flag_reason" in result
        assert "cost_threshold_usd" in result

    def test_flag_expensive_operation_low_cost(self) -> None:
        result = flag_expensive_operation(
            operation_type="llm_call",
            estimated_cost_usd=0.01,
            task_id="task-123",
        )
        
        assert result["is_flagged"] is False


class TestRecommendCachingStrategy:
    def test_recommend_caching_strategy_for_repeated_calls(self) -> None:
        result = recommend_caching_strategy(
            operation_type="api_response",
            repeat_frequency="high",
            data_size_mb=1.0,
        )
        
        assert isinstance(result, dict)
        assert "strategy" in result
        assert "estimated_savings_percent" in result
        assert "implementation" in result

    def test_recommend_caching_strategy_low_frequency(self) -> None:
        result = recommend_caching_strategy(
            operation_type="unique_analysis",
            repeat_frequency="low",
            data_size_mb=10.0,
        )
        
        # Should indicate caching may not be beneficial
        assert "recommendation" in result
        assert result["estimated_savings_percent"] < 20
