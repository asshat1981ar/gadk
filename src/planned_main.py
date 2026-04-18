"""Planned execution entry point — uses TextToolParser for elephant-alpha compatibility."""

import asyncio
import json
import os

from src.config import Config
from src.observability.logger import configure_logging, get_logger, set_session_id, set_trace_id
from src.planner import run_planner, run_planner_structured
from src.services.agent_contracts import ReviewVerdict
from src.services.structured_output import format_review_verdict, parse_task_proposal
from src.state import StateManager
from src.tools.dispatcher import register_tool
from src.tools.filesystem import read_file, write_file, list_directory
from src.tools.github_tool import read_repo_file, list_repo_contents
from src.tools.sandbox_executor import execute_python_code
from src.tools.web_search import search_web

# Register all tools so the planner can discover them
register_tool("search_web", search_web)
register_tool("execute_python_code", execute_python_code)
register_tool("read_file", read_file)
register_tool("write_file", write_file)
register_tool("list_directory", list_directory)
register_tool("read_repo_file", read_repo_file)
register_tool("list_repo_contents", list_repo_contents)

configure_logging(level=os.getenv("LOG_LEVEL", "INFO").upper(), json_format=False)
logger = get_logger("planned_main")


async def main():
    trace_id = os.getenv("TRACE_ID") or "planned-trace-001"
    set_trace_id(trace_id)
    set_session_id("planned-session-001")
    logger.info("=== Cognitive Foundry — Planned Execution Mode ===")

    sm = StateManager()

    # Phase 1: Ideator scans the codebase
    logger.info("=== PHASE 1: IDEATOR SCANS CODEBASE ===")
    ideator_system = (
        "You are the Ideator of the Cognitive Foundry. "
        "Your goal is to analyze the codebase, identify gaps, and create actionable tasks. "
        "ALWAYS respond with text. If you need to use a tool, include the JSON block in your response. "
        "Never return an empty response."
    )
    ideator_prompt = (
        "Scan the Cognitive Foundry codebase in three steps:\n"
        "1. Read src/main.py\n"
        "2. List the src/ directory structure\n" 
        "3. Identify ONE specific missing feature that would improve the swarm\n\n"
        "After your analysis, create a task by calling write_file to save a task spec "
        "to docs/suggested_task.md as JSON with keys: title, summary, description, "
        "acceptance_criteria, and recommended_agent. "
        "Then say DONE: <summary>"
    )

    ideator_result = await run_planner(
        user_prompt=ideator_prompt,
        system_prompt=ideator_system,
        max_iterations=5,
    )
    logger.info(f"Ideator finished. Final response:\n{ideator_result[:500]}")

    # Phase 2: Read the task spec the Ideator wrote
    logger.info("=== PHASE 2: READ TASK SPEC ===")
    task_spec_path = "docs/suggested_task.md"
    task_spec_payload: str | dict[str, object]
    if os.path.exists(task_spec_path):
        task_spec = read_file(task_spec_path)
        try:
            task_spec_payload = parse_task_proposal(task_spec).model_dump()
            logger.info(f"Task spec found:\n{json.dumps(task_spec_payload)[:500]}")
        except ValueError:
            task_spec_payload = task_spec
            logger.info(f"Task spec found:\n{task_spec[:500]}")
    else:
        task_spec_payload = "No task spec written by Ideator."
        logger.warning(task_spec_payload)

    # Phase 3: Builder implements the feature
    logger.info("=== PHASE 3: BUILDER IMPLEMENTS FEATURE ===")
    
    # Pre-read context so Builder doesn't waste iterations exploring
    try:
        main_py = read_file("src/main.py")
        config_py = read_file("src/config.py")
        existing_staged = list_directory("src/staged_agents")
        context = f"src/main.py:\n{main_py[:800]}\n\nsrc/config.py:\n{config_py[:800]}\n\nExisting staged agents: {[f['name'] for f in existing_staged]}"
    except Exception as e:
        context = f"Could not read context: {e}"
    
    builder_system = (
        "You are the Builder of the Cognitive Foundry. "
        "Your ONLY job is to write Python code using write_file. "
        "You have ALL the context you need in the prompt. "
        "DO NOT read files. DO NOT list directories. "
        "JUST write the implementation and say DONE."
    )
    builder_prompt = (
        f"Task spec:\n{json.dumps(task_spec_payload, indent=2) if isinstance(task_spec_payload, dict) else task_spec_payload}\n\n"
        f"Codebase context:\n{context}\n\n"
        "Write the implementation to src/staged_agents/ using write_file. "
        "Use a descriptive filename. Include docstrings, type hints, and a __main__ example. "
        "Then say DONE: <summary>"
    )

    builder_result = await run_planner(
        user_prompt=builder_prompt,
        system_prompt=builder_system,
        max_iterations=5,
    )
    logger.info(f"Builder finished. Final response:\n{builder_result[:500]}")

    # Phase 4: Critic reviews the staged code
    logger.info("=== PHASE 4: CRITIC REVIEWS ===")
    critic_system = (
        "You are the Critic of the Cognitive Foundry. "
        "Review staged code for safety, style, and correctness. "
        "Never return an empty response."
    )

    staged_files = [f for f in os.listdir("src/staged_agents") if f.endswith(".py")]
    if staged_files:
        latest = sorted(staged_files)[-1]
        staged_code = read_file(f"src/staged_agents/{latest}")
        critic_prompt = (
            f"Review this staged tool:\n\n```python\n{staged_code}\n```\n\n"
            "Return a structured review with status (pass/retry/block), summary, concerns, "
            "optional retry_reason, and recommended_actions."
        )
        if Config.INSTRUCTOR_ENABLED:
            verdict = await run_planner_structured(
                user_prompt=critic_prompt,
                system_prompt=critic_system,
                response_model=ReviewVerdict,
            )
            critic_result = format_review_verdict(verdict)
        else:
            critic_result = await run_planner(
                user_prompt=critic_prompt,
                system_prompt=critic_system,
                max_iterations=3,
            )
        logger.info(f"Critic finished. Review:\n{critic_result[:500]}")
    else:
        logger.warning("No staged files found for Critic to review.")
        critic_result = "No staged files to review."

    # Record task in state
    sm.set_task(
        "planned-task-001",
        {
            "title": "Planned pipeline execution",
            "status": "COMPLETED",
            "source": "PlannedMain",
            "description": (
                json.dumps(task_spec_payload)[:200]
                if isinstance(task_spec_payload, dict)
                else task_spec_payload[:200]
            ),
            "review": critic_result[:200],
        },
        agent="Builder",
    )

    logger.info("=== Planned Execution Complete ===")
    print("\n--- Results ---")
    print(f"Task spec: {task_spec_path if os.path.exists(task_spec_path) else 'NOT FOUND'}")
    print(f"Staged files: {staged_files}")
    print(f"State task: planned-task-001 → COMPLETED")


if __name__ == "__main__":
    asyncio.run(main())
