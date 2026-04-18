"""
Cognitive Foundry Swarm – Spark Analytics App
==============================================

Reads the three operational data files produced by the swarm runtime
(events.jsonl, state.json, metrics.jsonl) and analyses them with
Apache Spark DataFrames, then prints a formatted report to stdout.

Usage::

    python3 -m src.spark_app.swarm_analytics [--events PATH] [--state PATH] [--metrics PATH]

All path arguments are optional and default to the files that the
runtime writes in the project root (events.jsonl, state.json,
metrics.jsonl).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import IntegerType

from src.spark_app.schemas import EVENT_SCHEMA, METRIC_ENTRY_SCHEMA, TASK_SCHEMA

# ---------------------------------------------------------------------------
# Helper: load state.json and metrics.jsonl as plain Python dicts
# ---------------------------------------------------------------------------

def _load_json_file(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def load_events(spark: SparkSession, path: str):
    """Return a Spark DataFrame of swarm events from *events.jsonl*."""
    df = spark.read.json(path, schema=EVENT_SCHEMA, multiLine=False)
    # Parse ISO-8601 timestamp into a proper TimestampType for windowing
    df = df.withColumn(
        "event_time",
        F.to_timestamp("timestamp"),
    )
    return df


def load_tasks(spark: SparkSession, path: str):
    """Return a Spark DataFrame of tasks from *state.json*.

    state.json is a flat dict keyed by task_id.  We explode it into rows.
    """
    raw: dict = _load_json_file(path)
    rows = []
    for task_id, data in raw.items():
        rows.append(
            {
                "task_id": task_id,
                "status": data.get("status"),
                "source": data.get("source"),
                "title": data.get("title"),
                "priority": str(data.get("priority")) if data.get("priority") is not None else None,
            }
        )
    if not rows:
        return spark.createDataFrame([], schema=TASK_SCHEMA)
    return spark.createDataFrame(rows, schema=TASK_SCHEMA)


def load_metrics(spark: SparkSession, path: str):
    """Return a Spark DataFrame of agent/tool metrics from *metrics.jsonl*.

    Despite the ``.jsonl`` extension the runtime writes this file as a single
    JSON object (not line-delimited), re-serialising the entire registry on
    every update.  Rows are produced for every agent and tool entry found
    within the top-level ``"agents"`` and ``"tools"`` dicts.
    """
    raw: dict = _load_json_file(path)
    rows = []
    for kind, entries in (("agent", raw.get("agents", {})), ("tool", raw.get("tools", {}))):
        for name, m in entries.items():
            rows.append(
                {
                    "name": name,
                    "kind": kind,
                    "calls_total": int(m.get("calls_total", 0)),
                    "errors_total": int(m.get("errors_total", 0)),
                    "duration_seconds_sum": float(m.get("duration_seconds_sum", 0.0)),
                    "duration_seconds_count": int(m.get("duration_seconds_count", 0)),
                    "last_error": str(m.get("last_error", "")),
                }
            )
    if not rows:
        return spark.createDataFrame([], schema=METRIC_ENTRY_SCHEMA)
    return spark.createDataFrame(rows, schema=METRIC_ENTRY_SCHEMA)


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

def analyse_events(df_events):
    """Return a dict of pre-computed analytics DataFrames for events."""
    total = df_events.count()

    # Action distribution
    actions = (
        df_events.groupBy("action")
        .agg(F.count("*").alias("count"))
        .orderBy(F.desc("count"))
    )

    # Agent activity (filter out blank agent names)
    agent_activity = (
        df_events.filter(F.col("agent") != "")
        .groupBy("agent")
        .agg(F.count("*").alias("events"))
        .orderBy(F.desc("events"))
    )

    # Hourly event volume
    hourly = (
        df_events.withColumn("hour", F.date_format("event_time", "yyyy-MM-dd HH:00"))
        .groupBy("hour")
        .agg(F.count("*").alias("events"))
        .orderBy("hour")
    )

    # Most active task IDs
    top_tasks = (
        df_events.groupBy("task_id")
        .agg(F.count("*").alias("changes"))
        .orderBy(F.desc("changes"))
        .limit(10)
    )

    return {
        "total": total,
        "actions": actions,
        "agent_activity": agent_activity,
        "hourly": hourly,
        "top_tasks": top_tasks,
    }


def analyse_tasks(df_tasks):
    """Return a dict of pre-computed analytics DataFrames for tasks."""
    total = df_tasks.count()

    # Status distribution
    status_dist = (
        df_tasks.groupBy("status")
        .agg(F.count("*").alias("count"))
        .orderBy(F.desc("count"))
    )

    # Source (which agent created the task) distribution
    source_dist = (
        df_tasks.groupBy("source")
        .agg(F.count("*").alias("count"))
        .orderBy(F.desc("count"))
    )

    return {
        "total": total,
        "status_dist": status_dist,
        "source_dist": source_dist,
    }


def analyse_metrics(df_metrics):
    """Return a dict of pre-computed analytics DataFrames for metrics."""
    # Add derived columns
    df = df_metrics.withColumn(
        "avg_duration",
        F.when(
            F.col("duration_seconds_count") > 0,
            F.col("duration_seconds_sum") / F.col("duration_seconds_count"),
        ).otherwise(F.lit(0.0)),
    ).withColumn(
        "error_rate",
        F.when(
            F.col("calls_total") > 0,
            F.col("errors_total").cast("double") / F.col("calls_total"),
        ).otherwise(F.lit(0.0)),
    )

    agents = df.filter(F.col("kind") == "agent").orderBy(F.desc("calls_total"))
    tools = df.filter(F.col("kind") == "tool").orderBy(F.desc("calls_total"))

    return {"agents": agents, "tools": tools}


# ---------------------------------------------------------------------------
# Report printer
# ---------------------------------------------------------------------------

_SEP = "─" * 60


def _print_df(df, columns: list[str] | None = None, limit: int = 20) -> None:
    """Pretty-print a small Spark DataFrame as a plain text table."""
    rows = df.limit(limit).collect()
    col_names = columns or df.columns
    if not rows:
        print("  (no data)")
        return

    def _cell(row, col: str) -> str:
        return str(row[col]) if col in row.__fields__ else ""

    widths = [
        max(len(col), max((len(_cell(row, col)) for row in rows), default=0))
        for col in col_names
    ]
    fmt = "  " + "  ".join(f"{{:<{w}}}" for w in widths)
    print(fmt.format(*col_names))
    print("  " + "  ".join("-" * w for w in widths))
    for row in rows:
        print(fmt.format(*[_cell(row, col) for col in col_names]))


def print_report(event_stats, task_stats, metric_stats) -> None:
    print()
    print("=" * 60)
    print("  COGNITIVE FOUNDRY SWARM – SPARK ANALYTICS REPORT")
    print("=" * 60)

    # ── Events ──────────────────────────────────────────────────
    print(f"\n{_SEP}")
    print(f"  EVENTS  (total: {event_stats['total']})")
    print(_SEP)

    print("\n  Action distribution:")
    _print_df(event_stats["actions"])

    print("\n  Agent activity:")
    _print_df(event_stats["agent_activity"])

    print("\n  Hourly event volume:")
    _print_df(event_stats["hourly"])

    print("\n  Top 10 most-changed tasks:")
    _print_df(event_stats["top_tasks"])

    # ── Tasks ────────────────────────────────────────────────────
    print(f"\n{_SEP}")
    print(f"  TASKS  (total: {task_stats['total']})")
    print(_SEP)

    print("\n  Status distribution:")
    _print_df(task_stats["status_dist"])

    print("\n  Task source distribution:")
    _print_df(task_stats["source_dist"])

    # ── Metrics ──────────────────────────────────────────────────
    print(f"\n{_SEP}")
    print("  AGENT / TOOL METRICS")
    print(_SEP)

    print("\n  Agents:")
    _print_df(
        metric_stats["agents"],
        columns=["name", "calls_total", "errors_total", "avg_duration", "error_rate"],
    )

    print("\n  Tools:")
    _print_df(
        metric_stats["tools"],
        columns=["name", "calls_total", "errors_total", "avg_duration", "error_rate"],
    )

    print(f"\n{'=' * 60}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

# Maximum number of parent directories to search when locating project-root
# data files.  The spark_app package lives at src/spark_app/, so two levels up
# reaches the project root; six gives comfortable headroom for unusual layouts.
_MAX_DIR_LEVELS = 6


def _resolve_path(arg: str | None, default_name: str) -> str:
    """Resolve a data-file path, defaulting to project root."""
    if arg:
        return arg
    # Walk up from this file until we find the project root (contains src/)
    here = os.path.dirname(__file__)
    for _ in range(_MAX_DIR_LEVELS):
        candidate = os.path.join(here, default_name)
        if os.path.exists(candidate):
            return candidate
        here = os.path.dirname(here)
    return default_name  # fallback – will cause a clear FileNotFoundError


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Cognitive Foundry Swarm – Spark Analytics App"
    )
    parser.add_argument("--events", default=None, help="Path to events.jsonl")
    parser.add_argument("--state", default=None, help="Path to state.json")
    parser.add_argument("--metrics", default=None, help="Path to metrics.jsonl")
    parser.add_argument(
        "--master",
        default="local[*]",
        help="Spark master URL (default: local[*])",
    )
    args = parser.parse_args(argv)

    events_path = _resolve_path(args.events, "events.jsonl")
    state_path = _resolve_path(args.state, "state.json")
    metrics_path = _resolve_path(args.metrics, "metrics.jsonl")

    spark = (
        SparkSession.builder.master(args.master)
        .appName("CognitiveFoundrySwarmAnalytics")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")

    try:
        df_events = load_events(spark, events_path)
        df_tasks = load_tasks(spark, state_path)
        df_metrics = load_metrics(spark, metrics_path)

        event_stats = analyse_events(df_events)
        task_stats = analyse_tasks(df_tasks)
        metric_stats = analyse_metrics(df_metrics)

        print_report(event_stats, task_stats, metric_stats)
    finally:
        spark.stop()


if __name__ == "__main__":
    main(sys.argv[1:])
