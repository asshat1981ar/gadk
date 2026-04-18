"""Scan project-chimera codebase and run ideation/build pipeline."""

import asyncio
import os

from src.config import Config
from src.observability.logger import configure_logging, get_logger, set_session_id, set_trace_id
from src.planner import run_planner
from src.state import StateManager
from src.tools.dispatcher import register_tool
from src.tools.filesystem import read_file, write_file, list_directory
from src.tools.github_tool import read_repo_file, list_repo_contents
from src.tools.web_search import search_web

register_tool("search_web", search_web)
register_tool("read_file", read_file)
register_tool("write_file", write_file)
register_tool("list_directory", list_directory)
register_tool("read_repo_file", read_repo_file)
register_tool("list_repo_contents", list_repo_contents)

configure_logging(level=os.getenv("LOG_LEVEL", "INFO").upper(), json_format=False)
logger = get_logger("chimera_ideation")

REPO = Config.REPO_NAME or "asshat1981ar/project-chimera"


async def main():
    trace_id = f"chimera-ideation-{int(os.time())}" if hasattr(os, 'time') else "chimera-ideation-001"
    # os.time doesn't exist, use a simpler approach
    import time
    trace_id = f"chimera-ideation-{int(time.time())}"
    set_trace_id(trace_id)
    set_session_id("chimera-session-001")
    logger.info(f"=== Chimera Ideation Pipeline ===")
    logger.info(f"Target repo: {REPO}")

    sm = StateManager()

    # Phase 1: Ideator scans project-chimera remotely
    logger.info("=== PHASE 1: IDEATOR SCANS PROJECT-CHIMERA ===")
    ideator_system = (
        "You are the Ideator of the Cognitive Foundry. "
        "Your goal is to analyze a remote GitHub codebase, identify security issues, "
        "code quality problems, and missing features, then create actionable tasks. "
        "ALWAYS respond with text. Never return an empty response."
    )
    ideator_prompt = (
        f"Scan the GitHub repository '{REPO}' in three steps:\n"
        "1. List the root directory contents using list_repo_contents with path=''\n"
        "2. Read the build.gradle file (or build.gradle.kts) using read_repo_file\n"
        "3. Read the README.md using read_repo_file\n"
        "4. List the src/ directory using list_repo_contents\n\n"
        "After your analysis, identify the TOP 3 issues (security, quality, or missing features). "
        "Create a task by calling write_file to save a task spec "
        "to docs/chimera_tasks.md with: title, description, priority (HIGH/MEDIUM/LOW), and acceptance criteria for each issue. "
        "Then say DONE: <summary>"
    )

    ideator_result = await run_planner(
        user_prompt=ideator_prompt,
        system_prompt=ideator_system,
        max_iterations=8,
    )
    logger.info(f"Ideator finished. Final response:\n{ideator_result[:800]}")

    # Phase 2: Read the task spec
    logger.info("=== PHASE 2: READ TASK SPEC ===")
    task_spec_path = "docs/chimera_tasks.md"
    if os.path.exists(task_spec_path):
        task_spec = read_file(task_spec_path)
        logger.info(f"Task spec found ({len(task_spec)} chars)")
    else:
        task_spec = "No task spec written by Ideator."
        logger.warning(task_spec)

    # Phase 3: Builder implements a fix for the highest priority issue
    logger.info("=== PHASE 3: BUILDER IMPLEMENTS FIX ===")
    
    builder_system = (
        "You are the Builder of the Cognitive Foundry. "
        "Your ONLY job is to write Python code using write_file. "
        "You have ALL the context you need in the prompt. "
        "DO NOT read files. DO NOT list directories. "
        "JUST write the implementation and say DONE."
    )
    builder_prompt = (
        f"Task spec for project-chimera:\n{task_spec[:2000]}\n\n"
        "Pick the HIGHEST priority issue and implement a Python tool that could help detect or fix it. "
        "Write the implementation to src/staged_agents/ using write_file. "
        "Use a descriptive filename like 'chimera_<issue>_scanner.py'. "
        "Include docstrings, type hints, and a __main__ example. "
        "Then say DONE: <summary>"
    )

    builder_result = await run_planner(
        user_prompt=builder_prompt,
        system_prompt=builder_system,
        max_iterations=5,
    )
    logger.info(f"Builder finished. Final response:\n{builder_result[:500]}")

    # Post-process: if Builder returned a ```python block but no tool call was executed,
    # extract the code and write it directly.
    if not any(f.startswith("chimera") for f in os.listdir("src/staged_agents")):
        import re
        py_block = re.search(r"```python\n(.*?)\n```", builder_result, re.DOTALL)
        if py_block:
            code = py_block.group(1)
            # Infer filename from first line comment or docstring
            fname_match = re.search(r'"""\n?(\S+\.py)', code) or re.search(r'#\s*(\S+\.py)', code)
            fname = fname_match.group(1) if fname_match else "chimera_fix.py"
            if not fname.startswith("chimera"):
                fname = f"chimera_{fname}"
            fpath = f"src/staged_agents/{fname}"
            try:
                write_file(fpath, code)
                logger.info(f"Post-processed Builder output → {fpath}")
            except Exception as e:
                logger.warning(f"Failed to write post-processed file: {e}")

    # Phase 4: Critic reviews
    logger.info("=== PHASE 4: CRITIC REVIEWS ===")
    critic_system = (
        "You are the Critic of the Cognitive Foundry. "
        "Review staged code for safety, style, and correctness. "
        "ALWAYS provide a text review. Never return an empty response."
    )

    staged_files = [f for f in os.listdir("src/staged_agents") if f.startswith("chimera") and f.endswith(".py")]
    if staged_files:
        latest = sorted(staged_files)[-1]
        staged_code = read_file(f"src/staged_agents/{latest}")
        critic_prompt = (
            f"Review this staged tool for project-chimera:\n\n```python\n{staged_code}\n```\n\n"
            "Provide a concise review: what's good, what's missing, any safety concerns."
        )
        critic_result = await run_planner(
            user_prompt=critic_prompt,
            system_prompt=critic_system,
            max_iterations=3,
        )
        logger.info(f"Critic finished. Review:\n{critic_result[:500]}")
    else:
        logger.warning("No chimera staged files found for Critic to review.")
        critic_result = "No staged files to review."

    # Record task in state
    sm.set_task(
        f"chimera-ideation-{int(time.time())}",
        {
            "title": "Chimera codebase ideation",
            "status": "COMPLETED",
            "source": "ChimeraIdeation",
            "description": task_spec[:200] if task_spec else "No spec",
            "review": critic_result[:200],
        },
        agent="Ideator",
    )

    logger.info("=== Chimera Ideation Complete ===")
    print("\n--- Results ---")
    print(f"Task spec: {task_spec_path if os.path.exists(task_spec_path) else 'NOT FOUND'}")
    print(f"Chimera staged files: {staged_files}")


if __name__ == "__main__":
    asyncio.run(main())
