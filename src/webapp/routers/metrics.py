"""Metrics REST API router.

Exposes MetricsRegistry and CostTracker data via HTTP endpoints.
"""
from __future__ import annotations

import json
import os
from typing import Any

from fastapi import APIRouter, HTTPException

from src.observability.cost_tracker import CostTracker
from src.observability.metrics import registry

router = APIRouter(prefix="/api/metrics", tags=["metrics"])

# Cost tracker instance — same filename used by the swarm runtime
_cost_tracker = CostTracker()


def _load_cost_events() -> list[dict[str, Any]]:
    """Load cost events from costs.jsonl if present."""
    filename = _cost_tracker.filename
    if not os.path.exists(filename):
        return []
    events: list[dict[str, Any]] = []
    try:
        with open(filename) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return events


@router.get("/summary")
def get_metrics_summary() -> dict[str, Any]:
    """Agent and tool call metrics summary from MetricsRegistry."""
    return registry.get_summary()


@router.get("/costs")
def get_cost_summary() -> dict[str, Any]:
    """Cost tracking summary (total cost, cost by agent, cost by model)."""
    # Primary source: CostTracker aggregated state
    tracker_summary = _cost_tracker.get_summary()

    # Enrich with per-entry data from costs.jsonl if available
    events = _load_cost_events()

    # Aggregate by model if model field is present in events
    by_model: dict[str, float] = {}
    total_cost = tracker_summary.get("total_spend_usd", 0.0)
    for event in events:
        cost = event.get("cost", 0.0)
        model = event.get("model", "unknown")
        by_model[model] = by_model.get(model, 0.0) + cost

    # If no events with model field, try to infer from by_agent
    # CostTracker only tracks by_agent, so by_model may be empty
    if not by_model:
        by_model = {"default": total_cost}

    return {
        "total_spend_usd": total_cost,
        "by_agent": tracker_summary.get("by_agent", {}),
        "by_model": by_model,
        "by_task": tracker_summary.get("by_task", {}),
    }


@router.get("/tokens")
def get_token_summary() -> dict[str, Any]:
    """Token usage by agent and model."""
    summary = registry.get_summary()
    token_usage = summary.get("token_usage", {})

    # Also parse costs.jsonl for token counts if available
    events = _load_cost_events()
    tokens_by_agent: dict[str, int] = {}
    tokens_by_model: dict[str, int] = {}

    for event in events:
        agent = event.get("agent", "unknown")
        model = event.get("model", "unknown")
        input_tokens = event.get("input_tokens", 0)
        output_tokens = event.get("output_tokens", 0)
        total_tokens = input_tokens + output_tokens

        tokens_by_agent[agent] = tokens_by_agent.get(agent, 0) + total_tokens
        tokens_by_model[model] = tokens_by_model.get(model, 0) + total_tokens

    # Merge with registry token data
    for agent, tokens in token_usage.items():
        tokens_by_agent[agent] = tokens_by_agent.get(agent, 0) + tokens

    return {
        "by_agent": tokens_by_agent,
        "by_model": tokens_by_model,
    }
