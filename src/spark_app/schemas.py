"""PySpark schema definitions for Cognitive Foundry swarm data."""

from pyspark.sql.types import (
    DoubleType,
    IntegerType,
    LongType,
    MapType,
    StringType,
    StructField,
    StructType,
)

# Schema for each line in events.jsonl
# {"timestamp": "...", "task_id": "...", "agent": "...", "action": "...", "diff": {...}}
EVENT_SCHEMA = StructType(
    [
        StructField("timestamp", StringType(), nullable=True),
        StructField("task_id", StringType(), nullable=True),
        StructField("agent", StringType(), nullable=True),
        StructField("action", StringType(), nullable=True),
        # diff is a free-form nested object; read as a JSON string via get_json_object later
        StructField("diff", StringType(), nullable=True),
    ]
)

# Schema for agent/tool metric entries extracted from metrics.jsonl
METRIC_ENTRY_SCHEMA = StructType(
    [
        StructField("name", StringType(), nullable=False),
        StructField("kind", StringType(), nullable=False),  # "agent" | "tool"
        StructField("calls_total", IntegerType(), nullable=True),
        StructField("errors_total", IntegerType(), nullable=True),
        StructField("duration_seconds_sum", DoubleType(), nullable=True),
        StructField("duration_seconds_count", IntegerType(), nullable=True),
        StructField("last_error", StringType(), nullable=True),
    ]
)

# Schema for task rows extracted from state.json
TASK_SCHEMA = StructType(
    [
        StructField("task_id", StringType(), nullable=False),
        StructField("status", StringType(), nullable=True),
        StructField("source", StringType(), nullable=True),
        StructField("title", StringType(), nullable=True),
        StructField("priority", StringType(), nullable=True),
    ]
)
