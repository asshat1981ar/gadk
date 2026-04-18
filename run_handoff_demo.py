"""Manual handoff demo: scan -> ideate -> build -> review."""

import time

from src.observability.logger import get_logger, set_trace_id, set_session_id
from src.observability.metrics import registry
from src.state import StateManager
from src.tools.filesystem import read_file, list_directory, write_file

logger = get_logger("handoff_trace")
set_trace_id("handoff-demo-001")
set_session_id("session-handoff-001")

sm = StateManager()

# Phase 1: Orchestrator receives prompt
print("=== PHASE 1: ORCHESTRATOR ===")
logger.info("Orchestrator received prompt: scan codebase and ideate", extra={"agent": "Orchestrator"})
registry.record_agent_call("Orchestrator", 0.05)

# Phase 2: Orchestrator -> Ideator
print("=== PHASE 2: ORCHESTRATOR -> IDEATOR (transfer_to_agent) ===")
logger.info("Orchestrator delegating to Ideator for codebase scan", extra={"agent": "Orchestrator"})

# Phase 3: Ideator executes tools
print("=== PHASE 3: IDEATOR EXECUTES TOOLS ===")
t0 = time.perf_counter()
main_py = read_file("src/main.py")
registry.record_tool_call("read_file", time.perf_counter() - t0)
logger.info("Ideator read src/main.py", extra={"agent": "Ideator", "tool": "read_file"})

t0 = time.perf_counter()
src_dir = list_directory("src")
registry.record_tool_call("list_directory", time.perf_counter() - t0)
logger.info("Ideator listed src/ directory", extra={"agent": "Ideator", "tool": "list_directory"})

# Phase 4: Ideator creates task
print("=== PHASE 4: IDEATOR CREATES TASK ===")
task_id = "handoff-task-config-validator"
sm.set_task(
    task_id,
    {
        "title": "Add configuration validation tool",
        "status": "PLANNED",
        "source": "Ideator",
        "description": "The Cognitive Foundry lacks a tool to validate required env vars before startup.",
        "acceptance_criteria": [
            "Create src/tools/config_validator.py",
            "Check OPENROUTER_API_KEY, GITHUB_TOKEN, REPO_NAME",
            "Return clear error messages for missing vars",
            "Integrate into src/main.py startup",
            "Add tests",
        ],
        "priority": 2,
        "complexity": "small",
        "suggested_agent": "Builder",
    },
    agent="Ideator",
)
logger.info(f"Ideator created task: {task_id}", extra={"agent": "Ideator"})
registry.record_agent_call("Ideator", 0.5)

# Phase 5: Ideator -> Builder
print("=== PHASE 5: IDEATOR -> BUILDER (transfer_to_agent) ===")
logger.info("Ideator delegating to Builder for implementation", extra={"agent": "Ideator"})

# Phase 6: Builder writes code
print("=== PHASE 6: BUILDER IMPLEMENTS FEATURE ===")
code = '''"""Configuration validation tool for the Cognitive Foundry."""
import os
from typing import List, Dict, Any

REQUIRED_ENV_VARS = [
    "OPENROUTER_API_KEY",
    "GITHUB_TOKEN",
    "REPO_NAME",
]


def validate_required_env() -> Dict[str, Any]:
    """
    Validates that all required environment variables are present.
    Returns a result dict with 'ok', 'missing', and 'messages' keys.
    """
    missing = []
    for var in REQUIRED_ENV_VARS:
        if not os.getenv(var):
            missing.append(var)

    if missing:
        return {
            "ok": False,
            "missing": missing,
            "messages": [f"Missing required env var: {v}" for v in missing],
        }

    return {
        "ok": True,
        "missing": [],
        "messages": ["All required environment variables are present."],
    }


def validate_config(strict: bool = False) -> bool:
    """
    Validates configuration. If strict is True, raises EnvironmentError on failure.
    Otherwise returns a boolean indicating success.
    """
    result = validate_required_env()
    if not result["ok"]:
        if strict:
            raise EnvironmentError("\\n".join(result["messages"]))
        return False
    return True
'''

t0 = time.perf_counter()
write_file("src/staged_agents/config_validator.py", code)
registry.record_tool_call("write_file", time.perf_counter() - t0)
logger.info("Builder wrote config_validator.py to staged_agents", extra={"agent": "Builder", "tool": "write_file"})
registry.record_agent_call("Builder", 1.2)

# Phase 7: Builder -> Critic
print("=== PHASE 7: BUILDER -> CRITIC (transfer_to_agent) ===")
logger.info("Builder requesting Critic review", extra={"agent": "Builder"})

# Phase 8: Critic evaluates
print("=== PHASE 8: CRITIC EVALUATES ===")
t0 = time.perf_counter()
staged = read_file("src/staged_agents/config_validator.py")
registry.record_tool_call("read_file", time.perf_counter() - t0)
logger.info("Critic reviewed staged code", extra={"agent": "Critic", "tool": "read_file"})
registry.record_agent_call("Critic", 0.3)

# Phase 9: Critic marks task complete
sm.set_task(
    task_id,
    {
        "title": "Add configuration validation tool",
        "status": "COMPLETED",
        "source": "Ideator",
        "description": "Implemented config_validator.py in src/staged_agents/.",
        "acceptance_criteria": ["Tool written", "Staged for review"],
        "priority": 2,
        "complexity": "small",
        "suggested_agent": "Builder",
    },
    agent="Critic",
)
logger.info("Critic approved task completion", extra={"agent": "Critic"})

print("\n=== HANDOFF COMPLETE ===")
print(f"Tasks in state: {len(sm.get_all_tasks())}")
summary = registry.get_summary()
print(f"Agent calls: {summary['agents']}")
print(f"Tool calls: {summary['tools']}")
