"""FinOps Agent — owner of cost tracking and budget management during the OPERATE phase.

Manages LLM costs, token usage, budget alerts, and cost optimization recommendations.
Integrates with the existing CostTracker infrastructure for persistent cost aggregation.

Design choices:
- Pure functions at module scope so tests can import this module without google-adk present;
  the ``finops_agent`` ADK wrapper is gated on a successful ADK import.
- Integrates with existing observability stack: CostTracker, structured logging.
- Budget thresholds are configurable via environment variables with sensible defaults.
- Cost optimization includes model alternatives, caching strategies, and usage tracking.

Example:
    # Check current spending
    costs = get_current_costs()

    # Set a budget alert
    set_budget_alert(threshold_amount=50.0, alert_type="daily")

    # Get cost optimization recommendations
    recommendations = get_budget_recommendations()
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from src.observability.cost_tracker import CostTracker
from src.observability.logger import get_logger

logger = get_logger("finops")

# Default budget from environment
budget_usd = float(os.getenv("BUDGET_USD", "50.0"))
daily_budget_usd = float(
    os.getenv("DAILY_BUDGET_USD", str(budget_usd / 30))
)  # Default to monthly/30

# File paths for persistent storage
BUDGET_ALERTS_FILE = os.getenv("BUDGET_ALERTS_FILE", "budget_alerts.jsonl")
MODEL_USAGE_FILE = os.getenv("MODEL_USAGE_FILE", "model_usage.jsonl")

# Cost thresholds for flagging expensive operations
EXPENSIVE_OPERATION_THRESHOLD_USD = float(os.getenv("EXPENSIVE_OPERATION_THRESHOLD", "1.00"))
HIGH_COST_THRESHOLD_USD = float(os.getenv("HIGH_COST_THRESHOLD", "5.00"))

# Model cost estimates (per 1K tokens) - approximate values
MODEL_COSTS = {
    "ollama/kimi-k2.6:cloud": {"input": 0.005, "output": 0.015, "category": "premium"},
    "ollama/kimi-k2.6:cloud-mini": {"input": 0.00015, "output": 0.0006, "category": "economy"},
    "ollama/glm-5.1:cloud": {
        "input": 0.008,
        "output": 0.024,
        "category": "premium",
    },
    "ollama/gemma4:cloud": {
        "input": 0.0005,
        "output": 0.0015,
        "category": "standard",
    },
    "ollama/qwen3.5:cloud": {
        "input": 0.0004,
        "output": 0.0012,
        "category": "standard",
    },
    "ollama/minimax-m2.7:cloud": {"input": 0.002, "output": 0.006, "category": "standard"},
}

# Cheaper model alternatives for cost optimization
CHEAPER_ALTERNATIVES = {
    "ollama/kimi-k2.6:cloud": [
        "ollama/kimi-k2.6:cloud-mini",
        "ollama/gemma4:cloud",
    ],
    "ollama/glm-5.1:cloud": [
        "ollama/kimi-k2.6:cloud-mini",
        "ollama/gemma4:cloud",
        "ollama/minimax-m2.7:cloud",
    ],
    "ollama/gemma4:cloud": [
        "ollama/kimi-k2.6:cloud-mini",
    ],
    "ollama/minimax-m2.7:cloud": [
        "ollama/kimi-k2.6:cloud-mini",
        "ollama/qwen3.5:cloud",
    ],
}

# Initialize CostTracker for use by the FinOps agent
tracker = CostTracker()


@dataclass
class BudgetAlert:
    """Budget alert configuration."""

    threshold_amount: float
    alert_type: str  # "daily", "task", "total"
    current_spend: float = 0.0
    is_triggered: bool = False
    task_id: str | None = None
    message: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    triggered_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "threshold_amount": self.threshold_amount,
            "alert_type": self.alert_type,
            "current_spend": self.current_spend,
            "is_triggered": self.is_triggered,
            "task_id": self.task_id,
            "message": self.message,
            "created_at": self.created_at.isoformat(),
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
        }


@dataclass
class ModelUsage:
    """Model usage tracking entry."""

    model_name: str
    agent_name: str
    token_count: int
    cost_usd: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "model_name": self.model_name,
            "agent_name": self.agent_name,
            "token_count": self.token_count,
            "cost_usd": self.cost_usd,
            "timestamp": self.timestamp.isoformat(),
        }


# === Cost Tracking Tools ===


def get_current_costs() -> dict[str, Any]:
    """
    Get current LLM costs across all tasks and agents.

    Returns a summary of total spend, breakdown by task, and breakdown by agent.
    """
    summary = tracker.get_summary()
    logger.info(
        "Retrieved current costs",
        extra={
            "total_spend_usd": summary["total_spend_usd"],
            "task_count": len(summary.get("by_task", {})),
            "agent_count": len(summary.get("by_agent", {})),
        },
    )
    return {
        "current_total_usd": summary["total_spend_usd"],
        "by_task": summary.get("by_task", {}),
        "by_agent": summary.get("by_agent", {}),
        "timestamp": datetime.now(UTC).isoformat(),
    }


def get_cost_breakdown(group_by: str = "agent") -> dict[str, Any]:
    """
    Get detailed cost breakdown grouped by agent or task.

    Args:
        group_by: How to group the breakdown - "agent" or "task"

    Returns:
        Dictionary with cost breakdown per group and total.
    """
    summary = tracker.get_summary()

    if group_by == "agent":
        breakdown = summary.get("by_agent", {})
        result_key = "breakdown_by_agent"
    else:
        breakdown = summary.get("by_task", {})
        result_key = "breakdown_by_task"

    logger.info(
        "Retrieved cost breakdown",
        extra={"group_by": group_by, "total_spend_usd": summary["total_spend_usd"]},
    )

    return {
        result_key: breakdown,
        "total_spend_usd": summary["total_spend_usd"],
        "timestamp": datetime.now(UTC).isoformat(),
    }


def estimate_task_cost(
    task_description: str,
    expected_agents: list[str],
    expected_complexity: str = "medium",  # "low", "medium", "high"
    estimated_tokens_per_call: int | None = None,
) -> dict[str, Any]:
    """
    Estimate costs before executing a task.

    Args:
        task_description: Description of the task to estimate
        expected_agents: List of agent names expected to participate
        expected_complexity: Complexity level ("low", "medium", "high")
        estimated_tokens_per_call: Optional custom token estimate, auto-calculated if None

    Returns:
        Cost estimate with confidence level and detailed breakdown.
    """
    # Base token estimates per complexity
    complexity_multipliers = {"low": 1.0, "medium": 2.5, "high": 5.0}
    base_tokens = estimated_tokens_per_call or 2000  # Default base
    multiplier = complexity_multipliers.get(expected_complexity, 2.5)

    # Calculate estimated tokens per agent
    tokens_per_agent = int(base_tokens * multiplier)

    breakdown = []
    total_cost = 0.0

    # Use average model cost for estimation
    avg_cost_per_1k = 0.005  # Average across typical models

    for agent in expected_agents:
        agent_cost = (tokens_per_agent / 1000) * avg_cost_per_1k
        total_cost += agent_cost

        breakdown.append(
            {
                "agent": agent,
                "estimated_tokens": tokens_per_agent,
                "estimated_cost_usd": round(agent_cost, 6),
            }
        )

    # Add margin for uncertainty
    confidence_multiplier = 1.0 - (0.1 * complexity_multipliers[expected_complexity])

    logger.info(
        "Estimated task cost",
        extra={
            "task_description_snippet": task_description[:50],
            "expected_agents": expected_agents,
            "estimated_cost_usd": round(total_cost, 6),
            "confidence": confidence_multiplier,
        },
    )

    return {
        "estimated_cost_usd": round(total_cost, 6),
        "confidence": round(confidence_multiplier, 2),
        "breakdown": breakdown,
        "total_estimated_tokens": tokens_per_agent * len(expected_agents),
        "complexity": expected_complexity,
        "timestamp": datetime.now(UTC).isoformat(),
    }


def check_budget_status() -> dict[str, Any]:
    """
    Compare current spend to budget limits and return status.

    Returns:
        Budget status with percent used and warnings if approaching/exceeded limits.
    """
    current_spend = tracker.get_total_spend()
    remaining = budget_usd - current_spend
    percent_used = (current_spend / budget_usd * 100) if budget_usd > 0 else 0

    if current_spend > budget_usd:
        status = "BUDGET_EXCEEDED"
        message = f"Budget exceeded! Spent ${current_spend:.2f} of ${budget_usd:.2f}"
        logger.warning(message, extra={"current_spend": current_spend, "budget": budget_usd})
    elif percent_used >= 90:
        status = "APPROACHING_LIMIT"
        message = (
            f"Budget alert: {percent_used:.1f}% used (${current_spend:.2f} / ${budget_usd:.2f})"
        )
        logger.warning(message, extra={"percent_used": percent_used})
    elif percent_used >= 75:
        status = "WARNING"
        message = f"Budget warning: {percent_used:.1f}% used"
        logger.info(message, extra={"percent_used": percent_used})
    else:
        status = "WITHIN_BUDGET"
        message = (
            f"Budget healthy: {percent_used:.1f}% used (${current_spend:.2f} / ${budget_usd:.2f})"
        )
        logger.info(message, extra={"percent_used": percent_used})

    return {
        "status": status,
        "current_spend_usd": current_spend,
        "budget_usd": budget_usd,
        "remaining_usd": round(remaining, 6),
        "percent_used": round(percent_used, 2),
        "message": message,
        "timestamp": datetime.now(UTC).isoformat(),
    }


# === Budget Management Tools ===


def set_budget_alert(
    threshold_amount: float,
    alert_type: str = "daily",  # "daily", "task", "total"
    task_id: str | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    """
    Set a spending threshold for budget alerts.

    Args:
        threshold_amount: Dollar amount to trigger the alert
        alert_type: Type of alert threshold ("daily", "task", or "total")
        task_id: Optional task ID for task-specific alerts
        message: Optional custom alert message

    Returns:
        Confirmation of alert creation with alert details.
    """
    current_spend = tracker.get_total_spend()
    is_triggered = current_spend >= threshold_amount

    alert = BudgetAlert(
        threshold_amount=threshold_amount,
        alert_type=alert_type,
        current_spend=current_spend,
        is_triggered=is_triggered,
        task_id=task_id,
        message=message
        or f"Alert: Spending has reached ${current_spend:.2f} (threshold: ${threshold_amount:.2f})",
        triggered_at=datetime.now(UTC) if is_triggered else None,
    )

    # Persist to file
    _append_to_jsonl(BUDGET_ALERTS_FILE, alert.to_dict())

    logger.info(
        "Budget alert set",
        extra={
            "threshold_amount": threshold_amount,
            "alert_type": alert_type,
            "is_triggered": is_triggered,
            "task_id": task_id,
        },
    )

    return {
        "created": True,
        "threshold_amount": threshold_amount,
        "alert_type": alert_type,
        "is_triggered": is_triggered,
        "task_id": task_id,
        "message": alert.message,
        "timestamp": datetime.now(UTC).isoformat(),
    }


def get_budget_recommendations() -> list[dict[str, Any]]:
    """
    Get cost optimization suggestions based on current usage patterns.

    Returns:
        List of recommendations with potential savings and implementation tips.
    """
    recommendations = []
    summary = tracker.get_summary()
    current_spend = summary["total_spend_usd"]
    by_agent = summary.get("by_agent", {})

    # Check overall budget utilization
    if budget_usd > 0:
        utilization = current_spend / budget_usd

        if utilization > 0.8:
            recommendations.append(
                {
                    "category": "cost_control",
                    "recommendation": "Budget utilization is high. Consider reviewing task complexity assignments.",
                    "priority": "high",
                    "potential_savings_percent": 15,
                    "action": "Review high-cost tasks and consider using simpler models for routine operations",
                }
            )

    # Agent-specific recommendations
    for agent, cost in by_agent.items():
        agent_percent = (cost / current_spend * 100) if current_spend > 0 else 0

        if agent_percent > 50:
            recommendations.append(
                {
                    "category": "agent_optimization",
                    "recommendation": f"{agent} accounts for {agent_percent:.1f}% of costs. Review its usage patterns.",
                    "priority": "medium",
                    "potential_savings_percent": 10,
                    "action": f"Consider using cheaper models for {agent} operations",
                }
            )

    # Model optimization recommendations
    recommendations.append(
        {
            "category": "model_selection",
            "recommendation": "Use 'suggest_cheaper_alternative' tool to find cost-effective model options",
            "priority": "low",
            "potential_savings_percent": 25,
            "action": "Replace premium models with economy models for non-critical tasks",
        }
    )

    # Caching recommendations
    recommendations.append(
        {
            "category": "caching",
            "recommendation": "Enable response caching for repeated API calls",
            "priority": "low",
            "potential_savings_percent": 20,
            "action": "Use the 'recommend_caching_strategy' tool to identify caching opportunities",
        }
    )

    logger.info(
        "Generated budget recommendations",
        extra={"recommendations_count": len(recommendations), "current_spend": current_spend},
    )

    return recommendations


def track_model_usage(
    model_name: str,
    agent_name: str,
    token_count: int,
    cost_usd: float,
) -> dict[str, Any]:
    """
    Track which models are being used by which agents.

    Args:
        model_name: Name of the LLM model used
        agent_name: Name of the agent that used the model
        token_count: Number of tokens processed
        cost_usd: Cost in USD

    Returns:
        Confirmation of tracking with usage details.
    """
    usage = ModelUsage(
        model_name=model_name,
        agent_name=agent_name,
        token_count=token_count,
        cost_usd=cost_usd,
    )

    # Persist to file
    _append_to_jsonl(MODEL_USAGE_FILE, usage.to_dict())

    # Also record in cost tracker
    tracker.record_cost(f"model_usage_{agent_name}", agent_name, cost_usd)

    logger.info(
        "Model usage tracked",
        extra={
            "model_name": model_name,
            "agent_name": agent_name,
            "token_count": token_count,
            "cost_usd": cost_usd,
        },
    )

    return {
        "recorded": True,
        "model_name": model_name,
        "agent_name": agent_name,
        "token_count": token_count,
        "cost_usd": cost_usd,
        "timestamp": datetime.now(UTC).isoformat(),
    }


# === Cost Optimization Tools ===


def suggest_cheaper_alternative(
    model_name: str,
    task_type: str = "general",  # "code_generation", "analysis", "simple", "general"
) -> dict[str, Any]:
    """
    Suggest cheaper model alternatives for a given model.

    Args:
        model_name: Current model being used
        task_type: Type of task to help determine appropriate alternatives

    Returns:
        List of suggested cheaper alternatives with tradeoffs.
    """
    current_cost = MODEL_COSTS.get(model_name, {}).get("category", "unknown")
    alternatives = CHEAPER_ALTERNATIVES.get(model_name, [])

    suggestions = []
    for alt_model in alternatives:
        alt_info = MODEL_COSTS.get(alt_model, {})
        if alt_info:
            # Calculate potential savings
            current_avg = (MODEL_COSTS[model_name]["input"] + MODEL_COSTS[model_name]["output"]) / 2
            alt_avg = (alt_info["input"] + alt_info["output"]) / 2
            savings_percent = (
                ((current_avg - alt_avg) / current_avg * 100) if current_avg > 0 else 0
            )

            # Determine tradeoffs based on task type
            tradeoffs = []
            if alt_info["category"] == "economy":
                tradeoffs.append("May have reduced capability for complex reasoning")
                tradeoffs.append("Faster response times")
            elif alt_info["category"] == "standard":
                tradeoffs.append("Good balance of cost and capability")

            suggestions.append(
                {
                    "model": alt_model,
                    "category": alt_info["category"],
                    "estimated_savings_percent": round(savings_percent, 1),
                    "tradeoffs": tradeoffs,
                    "best_for": ["batch processing", "routine operations", "high volume tasks"],
                }
            )

    logger.info(
        "Suggested cheaper alternatives",
        extra={
            "current_model": model_name,
            "alternatives_count": len(suggestions),
            "task_type": task_type,
        },
    )

    if not alternatives:
        return {
            "current_model": model_name,
            "current_category": current_cost,
            "suggested_alternatives": [],
            "message": f"{model_name} is already economical or no cheaper alternatives configured",
        }

    return {
        "current_model": model_name,
        "current_category": current_cost,
        "suggested_alternatives": suggestions,
        "recommendation": f"Consider {suggestions[0]['model']} for {suggestions[0]['estimated_savings_percent']:.0f}% savings",
        "timestamp": datetime.now(UTC).isoformat(),
    }


def flag_expensive_operation(
    operation_type: str,
    estimated_cost_usd: float,
    task_id: str | None = None,
) -> dict[str, Any]:
    """
    Flag expensive operations that exceed cost thresholds.

    Args:
        operation_type: Type of operation (e.g., "embedding", "llm_call", "api_request")
        estimated_cost_usd: Estimated cost of the operation
        task_id: Optional associated task ID

    Returns:
        Flag status with reason and recommendations.
    """
    is_flagged = False
    flag_reason = None

    if estimated_cost_usd >= HIGH_COST_THRESHOLD_USD:
        is_flagged = True
        flag_reason = f"Very high cost operation (${estimated_cost_usd:.2f}) exceeds threshold (${HIGH_COST_THRESHOLD_USD:.2f})"
        logger.warning(flag_reason, extra={"operation_type": operation_type, "task_id": task_id})
    elif estimated_cost_usd >= EXPENSIVE_OPERATION_THRESHOLD_USD:
        is_flagged = True
        flag_reason = f"Expensive operation (${estimated_cost_usd:.2f}) flagged for review"
        logger.info(flag_reason, extra={"operation_type": operation_type, "task_id": task_id})
    else:
        logger.debug(
            "Operation cost within normal range",
            extra={"operation_type": operation_type, "estimated_cost": estimated_cost_usd},
        )

    recommendations = []
    if is_flagged:
        recommendations.append("Consider batching operations to reduce costs")
        recommendations.append("Review if operation can use cheaper model alternatives")
        recommendations.append("Check if caching can be applied")

    return {
        "is_flagged": is_flagged,
        "flag_reason": flag_reason,
        "operation_type": operation_type,
        "estimated_cost_usd": estimated_cost_usd,
        "cost_threshold_usd": EXPENSIVE_OPERATION_THRESHOLD_USD,
        "high_cost_threshold_usd": HIGH_COST_THRESHOLD_USD,
        "task_id": task_id,
        "recommendations": recommendations,
        "timestamp": datetime.now(UTC).isoformat(),
    }


def recommend_caching_strategy(
    operation_type: str,
    repeat_frequency: str = "medium",  # "low", "medium", "high"
    data_size_mb: float = 0.0,
) -> dict[str, Any]:
    """
    Recommend caching strategies based on operation patterns.

    Args:
        operation_type: Type of operation (e.g., "api_response", "llm_embedding", "computation")
        repeat_frequency: How often this operation repeats
        data_size_mb: Size of data being processed

    Returns:
        Caching recommendation with estimated savings and implementation guidance.
    """
    # Determine caching viability based on frequency and size
    frequency_scores = {"low": 0.2, "medium": 0.6, "high": 0.9}
    score = frequency_scores.get(repeat_frequency, 0.5)

    # Adjust for data size (larger data = more benefit but also more storage cost)
    if data_size_mb > 100:
        score -= 0.2  # Large data might be expensive to cache
    elif data_size_mb < 1:
        score += 0.1  # Small data is cheap to cache

    if score >= 0.7:
        strategy = "strongly_recommended"
        estimated_savings = 20 + (score * 30)
        implementation = {
            "type": "persistent_cache",
            "ttl_hours": 24 if repeat_frequency == "high" else 168,
            "storage": "disk" if data_size_mb > 10 else "memory",
        }
    elif score >= 0.4:
        strategy = "recommended"
        estimated_savings = 10 + (score * 20)
        implementation = {
            "type": "ephemeral_cache",
            "ttl_hours": 4,
            "storage": "memory",
        }
    else:
        strategy = "not_recommended"
        estimated_savings = 0
        implementation = {
            "type": "none",
            "reason": "Low repeat frequency or high data size may not justify caching overhead",
        }

    logger.info(
        "Caching strategy recommendation",
        extra={
            "operation_type": operation_type,
            "strategy": strategy,
            "estimated_savings": estimated_savings,
        },
    )

    return {
        "strategy": strategy,
        "estimated_savings_percent": round(estimated_savings, 1),
        "implementation": implementation,
        "recommendation": "Implement caching" if score >= 0.5 else "Caching not beneficial",
        "operation_type": operation_type,
        "repeat_frequency": repeat_frequency,
        "data_size_mb": data_size_mb,
        "timestamp": datetime.now(UTC).isoformat(),
    }


# === Helper Functions ===


def _append_to_jsonl(filepath: str, data: dict[str, Any]) -> None:
    """Append a JSON line to a JSONL file."""
    with open(filepath, "a") as f:
        f.write(json.dumps(data) + "\n")


# === Legacy Tools (for backward compatibility) ===


def check_quota(task_id: str = "global", cost_usd: float = 0.0) -> dict[str, Any]:
    """
    Checks whether a task is within budget.

    Legacy tool - new code should use check_budget_status() or track_model_usage().

    Args:
        task_id: Identifier for the task.
        cost_usd: Cost of the task in USD.
    """
    tracker.record_cost(task_id, "system", cost_usd)
    total = tracker.get_total_spend()
    if total > budget_usd:
        return {
            "status": "BUDGET_EXCEEDED",
            "limit_usd": budget_usd,
            "current_usd": total,
        }
    return {
        "status": "OK",
        "current_usd": total,
        "budget_usd": budget_usd,
    }


def get_report() -> dict[str, Any]:
    """Returns a summary of current costs and budget usage."""
    return tracker.get_summary()


# === ADK Agent Definition (optional) ===

finops_agent = None

try:
    from google.adk.agents import Agent

    from src.config import Config

    if Config.TEST_MODE:
        from src.testing.mock_llm import MockLiteLlm as LiteLlm
    else:
        from google.adk.models.lite_llm import LiteLlm

    # General-purpose model for FinOps (simple reports, no function calling needed)
    report_model = LiteLlm(
        model=Config.LLM_MODEL,
        api_key=Config.LLM_API_KEY,
        api_base=Config.LLM_API_BASE,
    )

    # Build the tools list for the agent
    finops_tools = [
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
        check_quota,  # Legacy
        get_report,  # Legacy
    ]

    finops_agent = Agent(
        name="FinOps",
        model=report_model,
        description="Tracks costs, budgets, and token usage. Provides cost optimization recommendations.",
        instruction="""You are the FinOps agent of the Cognitive Foundry.
Your job is to track costs, budgets, and token usage during the OPERATE phase.

Available tools:
- get_current_costs: Get today's LLM costs and breakdowns
- get_cost_breakdown: Costs by agent/model
- estimate_task_cost: Estimate costs before execution
- check_budget_status: Compare spend to budget limits
- set_budget_alert: Set spending thresholds
- get_budget_recommendations: Suggest optimizations
- track_model_usage: Track which models are used
- suggest_cheaper_alternative: Suggest cheaper model options
- flag_expensive_operation: Flag expensive operations
- recommend_caching_strategy: Recommend caching strategies

Always monitor costs proactively and suggest optimizations when utilization is high.
Report budget status with clear warnings when approaching limits.""",
        tools=finops_tools,
    )
except ImportError as exc:
    logger.debug("ADK unavailable; finops_agent disabled: %s", exc)


__all__ = [
    "get_current_costs",
    "get_cost_breakdown",
    "estimate_task_cost",
    "check_budget_status",
    "set_budget_alert",
    "get_budget_recommendations",
    "track_model_usage",
    "suggest_cheaper_alternative",
    "flag_expensive_operation",
    "recommend_caching_strategy",
    "check_quota",
    "get_report",
    "BudgetAlert",
    "ModelUsage",
    "finops_agent",
    "tracker",
    "budget_usd",
]
