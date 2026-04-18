"""Autonomous SDLC engine for project-chimera.

Runs a continuous loop:
  1. DISCOVER — scan repo for issues via GitHub API
  2. PLAN     — pick highest-priority task not already in-flight
  3. BUILD    — Builder agent implements fix in Kotlin
  4. REVIEW   — Critic reviews implementation
  5. DELIVER  — push branch, open PR, and autonomously MERGE
"""

import asyncio
import os
import re
import time

# Allowed characters in generated task IDs. Collisions after slugification are
# broader than the prefix alone implies, but this regex at least rejects
# control chars, path separators, and other nasties before they reach the
# state file / event log.
_TASK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{0,62}$")


def _slugify_task_id(prefix: str, title: str, max_len: int = 40) -> str:
    """Derive a deterministic, path-safe task_id from a title.

    Validates the produced ID against ``_TASK_ID_RE``; raises ValueError
    for titles that would yield an unsafe identifier so the caller can
    log and skip.
    """
    raw = title.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")[:max_len] or "untitled"
    task_id = f"{prefix}-{slug}"
    if not _TASK_ID_RE.match(task_id):
        raise ValueError(f"rejected unsafe task_id derived from title: {title!r}")
    return task_id


from src.agents.architect import draft_architecture_note
from src.agents.governor import register_external_gate
from src.config import Config
from src.observability.logger import configure_logging, get_logger, set_trace_id
from src.observability.metrics import registry
from src.planner import run_planner, run_planner_structured
from src.services.agent_contracts import ReviewVerdict
from src.services.phase_controller import PhaseController
from src.services.phase_store import ensure_work_item, save_work_item
from src.services.sdlc_phase import Phase, WorkItem
from src.services.structured_output import (
    format_review_verdict,
    parse_discovery_tasks,
)
from src.services.workflow_graphs import (
    AutonomousRetryState,
    run_autonomous_retry,
)
from src.state import StateManager
from src.tools.content_guards import is_low_value_content
from src.tools.filesystem import read_file, write_file
from src.tools.github_tool import GitHubTool

configure_logging(level=os.getenv("LOG_LEVEL", "INFO").upper(), json_format=False)
logger = get_logger("autonomous_sdlc")

REPO = Config.REPO_NAME
MAX_CYCLES = int(os.getenv("MAX_CYCLES", "10"))
CYCLE_SLEEP_SEC = int(os.getenv("CYCLE_SLEEP_SEC", "30"))
SHUTDOWN_FILE = os.getenv("SHUTDOWN_FILE", ".shutdown_sdlc")
TASKS_FILE = "docs/sdlc_tasks.json"
MAX_REVIEW_RETRIES = int(os.getenv("MAX_REVIEW_RETRIES", "2"))


def _architecture_note_from_task(task: dict) -> dict | None:
    """Synthesize a minimal ADR payload from an Ideator-produced task.

    No LLM call — the ADR is derived from task fields already in hand.
    Captures the Ideator→Builder handoff in structured form so
    ``events.jsonl`` carries an auditable rationale for every
    ARCHITECT transition. A future iteration can swap this for a real
    Architect-agent LLM roundtrip; the `draft_architecture_note`
    signature already matches.

    Returns ``None`` if validation fails (e.g., missing required
    fields) so the caller can degrade to a forced-skip rather than
    halting the cycle.
    """
    try:
        title = (task.get("title") or "").strip()
        description = (task.get("description") or "").strip()
        priority = (task.get("priority") or "MEDIUM").strip().upper()
        file_hint = (task.get("file_hint") or "").strip()

        if not title or not description:
            return None

        touched = [file_hint] if file_hint else []
        consequences = [
            f"Priority: {priority}",
            "Implemented by the Builder agent; delivered through the autonomous SDLC loop.",
        ]

        return draft_architecture_note(
            task_id=task["task_id"],
            title=title,
            context=description,
            decision="Implement as specified by the Ideator; no additional architectural divergence.",
            consequences=consequences,
            alternatives=["Defer: leave the gap unaddressed for the next discovery cycle."],
            touched_paths=touched,
        )
    except Exception as exc:  # pydantic.ValidationError + anything else
        logger.warning(
            "architecture.note.degraded task=%s reason=%s",
            task.get("task_id"),
            exc,
        )
        return None


def _extract_review_status(review_text: str) -> str:
    """Extract a ReviewVerdict status keyword from a formatted review string.

    Looks for the canonical ``Status: <keyword>`` line emitted by
    ``format_review_verdict``.  Falls back to simple keyword scanning for
    unstructured critic responses so the workflow graph always receives a
    recognised status token.

    Returns one of ``"pass"``, ``"retry"``, or ``"block"``.
    """
    import re  # local import: re is stdlib, kept here to avoid module-level noise

    match = re.search(r"Status:\s*(pass|retry|block)", review_text, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    lower = review_text.lower()
    if "block" in lower:
        return "block"
    if "retry" in lower or "fail" in lower or "issue" in lower or "concern" in lower:
        return "retry"
    return "pass"


class AutonomousSDLCEngine:
    """Autonomous SDLC engine — now phase-gated.

    Each cycle routes the selected task through a ``WorkItem`` advancing
    PLAN → ARCHITECT → IMPLEMENT → REVIEW → GOVERN → OPERATE via
    :class:`PhaseController`, so every transition emits a
    ``phase.transition`` event in ``events.jsonl`` that operators can
    audit. The discovery + delivery logic is unchanged; only the
    orchestration around it is now observable.

    The `ARCHITECT` phase produces a minimal ADR from task fields via
    :func:`_architecture_note_from_task` — no extra LLM call. The ADR
    captures the Ideator→Builder handoff in structured form so every
    transition in ``events.jsonl`` carries an auditable rationale. If
    the ADR synthesis fails (missing task fields, pydantic validation
    error), the transition degrades to a forced-skip with a structured
    warning; the cycle continues rather than halting on the audit
    surface. A future iteration can replace the synthesis with a real
    Architect-agent LLM call; the signature already matches
    :func:`src.agents.architect.draft_architecture_note`.
    """

    def __init__(
        self,
        *,
        state_manager: StateManager | None = None,
        github_tool: GitHubTool | None = None,
        phase_controller: PhaseController | None = None,
    ) -> None:
        self.sm = state_manager or StateManager()
        self.gh = github_tool or GitHubTool()
        self.controller = phase_controller or PhaseController(state_manager=self.sm)
        self.cycle = 0
        self.tasks_completed = 0
        self.tasks_failed = 0

    def _should_shutdown(self) -> bool:
        return os.path.exists(SHUTDOWN_FILE)

    def _shutdown(self):
        if os.path.exists(SHUTDOWN_FILE):
            os.remove(SHUTDOWN_FILE)
            logger.info("Shutdown sentinel removed.")

    async def _discover(self) -> list:
        """Return list of task dicts from repo scan — focused on comprehensive codebase analysis."""
        logger.info("=== DISCOVER: Codebase analysis & gap detection ===")
        prompt = (
            f"You are a Principal Engineer analyzing the GitHub repository '{REPO}'.\n"
            "Your goal is to identify ONE critical gap or refactor opportunity and output a task for it.\n\n"
            "DECISIVENESS RULES:\n"
            "1. Run 3-5 tool calls to explore the repo (list_repo_contents, read_repo_file).\n"
            "2. Once you see ANY gap (missing documentation, inconsistent naming, missing validation, unfinished feature), STOP EXPLORING.\n"
            "3. Immediately output your findings as JSON with keys title, priority, description, and file_hint.\n\n"
            "DO NOT keep exploring. Be decisive. Output the task JSON as soon as you find one issue."
        )
        system = (
            "You are the Discovery & Ideation agent. Your primary metric is DECISIVENESS. "
            "Find one issue, brainstorm a fix, and output task JSON. Never return empty."
        )
        result = await run_planner(
            user_prompt=prompt,
            system_prompt=system,
            max_iterations=25,
        )
        try:
            tasks = [task.model_dump() for task in parse_discovery_tasks(result)]
        except ValueError:
            tasks = []

        if tasks:
            logger.info(f"Discovered {len(tasks)} feature gaps")
            return tasks

        logger.warning("Could not parse discovered tasks; using fallback")
        # Fallback tasks if discovery fails
        fallback_tasks = [
            {
                "title": "Add Architectural Documentation to Core Modules",
                "priority": "MEDIUM",
                "description": "The project lacks high-level README files in the core modules explaining the architectural patterns and state management flow.",
                "file_hint": "src/staged_agents/README_ARCHITECTURE.md",
            }
        ]
        # Pick fallback not recently done
        for fb in fallback_tasks:
            try:
                tid = _slugify_task_id("sdlc", fb["title"])
            except ValueError as exc:
                logger.warning("skipping fallback task with unsafe title: %s", exc)
                continue
            existing = self.sm.get_task(tid)
            if not existing or existing.get("status") not in ("COMPLETED", "MERGED", "DELIVERED"):
                return [fb]
        return [fallback_tasks[0]]

    async def _plan(self, tasks: list) -> dict | None:
        """Pick highest-priority task not already in-flight."""
        logger.info("=== PLAN: selecting next task ===")
        priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        tasks.sort(key=lambda t: priority_order.get(t.get("priority", "LOW"), 2))

        # Check existing open PRs to avoid duplicates
        try:
            open_prs = await self.gh.list_pull_requests(state="open")
            open_titles = {p["title"].lower() for p in open_prs}
        except (ConnectionError, TimeoutError, KeyError, TypeError) as exc:
            logger.warning("open-PR scan failed; proceeding without dedup: %s", exc)
            open_titles = set()

        for task in tasks:
            title = task.get("title", "").strip()
            if not title:
                continue
            try:
                task_id = _slugify_task_id("sdlc", title)
            except ValueError as exc:
                logger.warning("skipping task with unsafe title: %s", exc)
                continue
            existing = self.sm.get_task(task_id)
            if existing and existing.get("status") in ("COMPLETED", "MERGED"):
                continue
            # Check if there's already a PR with similar title
            if any(title.lower() in pt or pt in title.lower() for pt in open_titles):
                logger.info(f"Skipping '{title}' — similar PR already open")
                continue
            task["task_id"] = task_id
            logger.info(f"Selected task: {title} ({task.get('priority')})")
            return task
        logger.info("No new tasks to work on")
        return None

    async def _build(self, task: dict) -> str | None:
        """Builder implements fix. Returns staged file path or None."""
        logger.info("=== BUILD: implementing fix ===")
        task_id = task["task_id"]
        self.sm.set_task(
            task_id, {**task, "status": "IN_PROGRESS", "agent": "Builder"}, agent="Builder"
        )

        # Pre-read repo context (increased scope)
        context_parts = []
        # Try to read the specific file mentioned in the task or discovery
        file_hint = task.get("file_hint", "")
        if file_hint:
            content = await self.gh.read_repo_file(file_hint)
            if not content.startswith("Error"):
                context_parts.append(f"--- {file_hint} (CURRENT CONTENT) ---\n{content}")

        # Fallback to general context if specific file not read
        if not context_parts:
            for path in ["README.md", "build.gradle.kts"]:
                content = await self.gh.read_repo_file(path)
                if not content.startswith("Error"):
                    context_parts.append(f"--- {path} ---\n{content[:1000]}")

        context = "\n\n".join(context_parts)

        builder_prompt = (
            f"Task: {task['title']}\n"
            f"Description: {task['description']}\n"
            f"File to create/modify: {task.get('file_hint', 'N/A')}\n\n"
            f"Repository Context:\n{context}\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. You are in a RESTRICTED ENVIRONMENT. You ONLY have the 'write_file' tool.\n"
            "2. DO NOT attempt to list directories or read other files. You have all the context you need above.\n"
            "3. Write the FULL Kotlin implementation (.kt) to fix the task.\n"
            "4. Use 'write_file' with path starting with 'src/staged_agents/'.\n"
            "5. After writing the file, immediately say DONE: <summary>.\n\n"
            "Kotlin Template:\n"
            "package com.chimera.tools\n"
            "// ... implementation ...\n"
        )
        builder_system = (
            "You are a Senior Kotlin Engineer. Your ONLY allowed action is calling 'write_file'. "
            "You MUST NOT ask for more context or try to use other tools. "
            "Implement the fix in Kotlin and write it to src/staged_agents/."
        )
        # Use GPT-4o for Builder since it follows language instructions reliably
        build_start = time.time()
        result = await run_planner(
            user_prompt=builder_prompt,
            system_prompt=builder_system,
            max_iterations=6,
            allowed_tools={"write_file"},
            model=Config.OPENROUTER_TOOL_MODEL,
        )

        # Check if file was written via tool call DURING this build
        staged = [
            f
            for f in os.listdir("src/staged_agents")
            if (f.endswith(".kt") or f.endswith(".py") or f.endswith(".md"))
            and os.path.getmtime(f"src/staged_agents/{f}") > build_start
        ]
        if staged:
            paths = [f"src/staged_agents/{f}" for f in staged]
            paths.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            latest = paths[0]
            logger.info(f"Builder produced: {latest}")
            self.sm.set_task(task_id, {"status": "BUILT", "artifact": latest}, agent="Builder")
            return latest

        # Post-process: extract code block if present
        import re

        kt_block = re.search(r"```kotlin\n(.*?)\n```", result, re.DOTALL)
        py_block = re.search(r"```python\n(.*?)\n```", result, re.DOTALL)
        md_block = re.search(r"```markdown\n(.*?)\n```", result, re.DOTALL)
        code_block = kt_block or py_block or md_block
        if code_block:
            code = code_block.group(1)
            ext = ".kt" if kt_block else (".py" if py_block else ".md")
            fname = f"{task_id}{ext}"
            fpath = f"src/staged_agents/{fname}"
            write_file(fpath, code)
            logger.info(f"Post-processed Builder output → {fpath}")
            self.sm.set_task(task_id, {"status": "BUILT", "artifact": fpath}, agent="Builder")
            return fpath

        logger.warning("Builder produced no artifact")
        self.sm.set_task(task_id, {"status": "FAILED", "reason": "no artifact"}, agent="Builder")
        return None

    async def _review(self, artifact_path: str, task: dict) -> str:
        """Critic reviews staged code."""
        logger.info("=== REVIEW: critic check ===")
        code = read_file(artifact_path)
        critic_prompt = (
            f"Review this tool for task: {task['title']}\n\n"
            f"```python\n{code}\n```\n\n"
            "Return a structured review with status (pass/retry/block), summary, concerns, "
            "optional retry_reason, and recommended_actions."
        )
        critic_system = (
            "You are the Critic. Review code for safety, style, and correctness. "
            "Never return empty."
        )
        if Config.INSTRUCTOR_ENABLED:
            verdict = await run_planner_structured(
                user_prompt=critic_prompt,
                system_prompt=critic_system,
                response_model=ReviewVerdict,
            )
            review = format_review_verdict(verdict)
        else:
            review = await run_planner(
                user_prompt=critic_prompt,
                system_prompt=critic_system,
                max_iterations=3,
            )
        logger.info(f"Critic review ({len(review)} chars)")
        return review

    async def _deliver(self, artifact_path: str, task: dict, review: str) -> str:
        """Commit to branch, open PR, create issue."""
        logger.info("=== DELIVER: pushing to repo ===")
        task_id = task["task_id"]
        code = read_file(artifact_path)

        # Empty-content guard: don't open a PR for a stub or empty file.
        # This stops the "Turn-Based Combat System" pattern where an empty
        # .kt gets committed and a PR is raised whose own body admits
        # "the code snippet is empty".
        if is_low_value_content(code):
            logger.warning(
                "_deliver: skipping low-value artifact %s (%d bytes)",
                artifact_path,
                len(code or ""),
            )
            self.sm.set_task(
                task_id,
                {"status": "SKIPPED_LOW_VALUE", "artifact": artifact_path},
                agent="Builder",
            )
            return None

        # Use unique branch name with timestamp to avoid collisions
        branch = f"bot/{task_id}-{int(time.time())}"
        filename = os.path.basename(artifact_path)
        # Place files in appropriate project structure
        if filename.endswith(".kt"):
            remote_path = f"src/main/java/com/chimera/tools/{filename}"
        elif filename.endswith(".md") and "README" in filename:
            # Try to find a logical path for documentation
            remote_path = f"docs/{filename}"
        else:
            remote_path = f"tools/{filename}"

        # Commit file to branch
        commit_result = await self.gh.create_or_update_file(
            path=remote_path,
            content=code,
            message=f"[FeatureBot] {task['title']}\n\n{task['description'][:200]}",
            branch=branch,
        )
        logger.info(f"Commit result: {commit_result}")

        # Create PR
        pr_url = await self.gh.create_pull_request(
            title=f"[FeatureBot] {task['title']}",
            body=f"## 🤖 Automated Kotlin Feature Implementation\n\n**Task:** {task['title']}\n**Priority:** {task.get('priority', 'N/A')}\n**Language:** Kotlin\n\n**Description:**\n{task['description']}\n\n**Gap Analysis:**\nThis Kotlin feature was identified as missing during automated feature scanning of the Android codebase.\n\n**Critic Review:**\n{review[:800]}\n\n---\n*Generated by Cognitive Foundry Feature Discovery Engine*",
            head=branch,
        )
        logger.info(f"PR created: {pr_url}")

        # Merge PR (Autonomous Delivery)
        try:
            pr_number = int(pr_url.split("/")[-1])
            logger.info(f"=== MERGING PR #{pr_number} ===")
            merge_result = await self.gh.merge_pull_request(
                pr_number=pr_number,
                commit_message=f"Autonomous Merge: {task['title']}\n\n{task['description'][:200]}",
            )
            logger.info(f"Merge result: {merge_result}")
        except Exception as e:
            logger.error(f"Autonomous merge failed: {e}")

        # Create issue for tracking
        issue_url = await self.gh.create_issue(
            title=f"[SDLCBot] {task['title']}",
            body=f"**Priority:** {task.get('priority', 'N/A')}\n\n**Description:**\n{task['description']}\n\n**PR:** {pr_url}\n\n**Critic Review:**\n{review[:500]}",
        )
        logger.info(f"Issue created: {issue_url}")

        self.sm.set_task(
            task_id,
            {
                "status": "DELIVERED",
                "artifact": artifact_path,
                "branch": branch,
                "pr_url": pr_url,
                "issue_url": issue_url,
                "review": review[:200],
            },
            agent="Builder",
        )
        return pr_url

    async def run_cycle(self) -> bool:
        """Run one full SDLC cycle. Returns True if work was done.

        The cycle drives a :class:`WorkItem` through the canonical phase
        ladder; every transition writes a ``phase.transition`` event so
        operators can reconstruct the exact path a task took from
        ``events.jsonl``.
        """
        self.cycle += 1
        cycle_id = f"sdlc-cycle-{self.cycle}"
        set_trace_id(cycle_id)
        logger.info(
            "cycle.start",
            extra={"cycle_id": cycle_id, "trace_id": cycle_id, "max_cycles": MAX_CYCLES},
        )
        logger.info(f"========== CYCLE {self.cycle}/{MAX_CYCLES or '∞'} ==========")

        # Discover — precedes PLAN; produces the backlog selection feeds.
        tasks = await self._discover()
        if not tasks:
            logger.info("No tasks discovered. Cycle complete.")
            return False

        # Plan — select one task and open its WorkItem at phase=PLAN.
        task = await self._plan(tasks)
        if not task:
            logger.info("No actionable tasks. Cycle complete.")
            return False

        item: WorkItem = ensure_work_item(self.sm, task["task_id"], phase=Phase.PLAN)
        item.payload["task"] = task

        # PLAN → ARCHITECT. Build a minimal ADR from task fields (no
        # extra LLM call) so every autonomous transition carries a
        # structured rationale. If synthesis fails (malformed task,
        # missing fields) we degrade to a forced skip with a
        # `architecture.note.degraded` warning — the cycle continues
        # rather than halting on what is meant to be an audit surface.
        adr = _architecture_note_from_task(task)
        if adr is not None:
            item.payload["architecture"] = adr
            self.controller.advance(item, Phase.ARCHITECT, reason=f"ADR drafted: {adr['title']}")
        else:
            self.controller.advance(
                item,
                Phase.ARCHITECT,
                reason="auto-skip: ADR synthesis unavailable",
                force=True,
            )

        # ARCHITECT → IMPLEMENT (build).
        artifact = await self._build(task)
        if not artifact:
            self.tasks_failed += 1
            save_work_item(self.sm, item, agent="Builder")
            return False
        item.payload["artifact"] = artifact
        self.controller.advance(item, Phase.IMPLEMENT, reason="builder produced artifact")

        # IMPLEMENT → REVIEW with bounded rework. The `decide_rework`
        # helper wraps `run_review_rework_cycle` and emits its decision
        # as a `phase.review.decision` event.
        review = await self._review(artifact, task)
        item.payload["review"] = review
        review_status = _extract_review_status(review)
        builder_attempts = 1

        while True:
            next_step = self.controller.decide_rework(
                item,
                builder_attempts=builder_attempts,
                review_status=review_status,
                latest_summary=review[:200],
                max_retries=MAX_REVIEW_RETRIES,
            )
            if next_step == "stop":
                break  # review passed
            if next_step == "critic_stop":
                logger.warning(
                    "cycle.review_blocked attempts=%d status=%s",
                    builder_attempts,
                    review_status,
                )
                self.tasks_failed += 1
                self.sm.set_task(
                    task["task_id"],
                    {"status": "REVIEW_BLOCKED", "reason": f"critic_stop after {builder_attempts}"},
                    agent="Critic",
                )
                save_work_item(self.sm, item, agent="Critic")
                return False

            # next_step == "builder" — rework
            logger.info(f"Rework loop: attempt {builder_attempts + 1}/{MAX_REVIEW_RETRIES}")
            builder_attempts += 1
            rebuilt = await self._build(task)
            if rebuilt:
                artifact = rebuilt
                item.payload["artifact"] = artifact
            review = await self._review(artifact, task)
            item.payload["review"] = review
            review_status = _extract_review_status(review)

        # REVIEW passed → advance to GOVERN.
        self.controller.advance(item, Phase.REVIEW, reason="review passed")

        # GOVERN — dormant unless Config.SDLC_MCP_ENABLED. The helper
        # returns a status dict either way; we stash it on the item so
        # the event log carries the verdict alongside the transition.
        gate_result = register_external_gate(
            task_id=item.id,
            verdict={"review": review, "ready": True, "attempts": builder_attempts},
        )
        item.payload["governance"] = gate_result
        self.controller.advance(item, Phase.GOVERN, reason="governance gate recorded")

        # GOVERN → OPERATE (delivery).
        try:
            pr_url = await self._deliver(artifact, task, review)
            item.payload["pr_url"] = pr_url
            self.controller.advance(item, Phase.OPERATE, reason=f"PR opened: {pr_url}")
            self.tasks_completed += 1
            logger.info(f"Cycle {self.cycle} complete. PR: {pr_url}")
            save_work_item(self.sm, item, agent="Builder")
            return True
        except Exception as e:
            logger.exception("Delivery failed")
            self.tasks_failed += 1
            self.sm.set_task(
                task["task_id"], {"status": "FAILED", "reason": str(e)}, agent="Builder"
            )
            save_work_item(self.sm, item, agent="Builder")
            return False

    async def run(self):
        logger.info("=== Autonomous SDLC Engine Starting ===")
        logger.info(
            f"Repo: {REPO} | Max cycles: {MAX_CYCLES or 'infinite'} | Sleep: {CYCLE_SLEEP_SEC}s"
        )

        while True:
            if self._should_shutdown():
                logger.info("Shutdown sentinel detected. Exiting.")
                self._shutdown()
                break

            if MAX_CYCLES > 0 and self.cycle >= MAX_CYCLES:
                logger.info(f"Max cycles ({MAX_CYCLES}) reached. Exiting.")
                break

            failed_before = self.tasks_failed
            try:
                await self.run_cycle()
            except Exception:
                logger.exception(f"Cycle {self.cycle} crashed")
                self.tasks_failed += 1

            # Metrics summary
            registry.record_tool_call("sdlc.cycle", 0.0)
            logger.info(
                f"Stats: cycles={self.cycle}, completed={self.tasks_completed}, failed={self.tasks_failed}"
            )

            if MAX_CYCLES > 0 and self.tasks_failed > failed_before:
                retry_decision = run_autonomous_retry(
                    AutonomousRetryState(
                        cycle_attempts=self.cycle,
                        last_status="retry",
                        failure_reason="cycle ended without successful delivery",
                    ),
                    max_cycles=MAX_CYCLES,
                )
                if retry_decision.next_step == "stop":
                    logger.warning(
                        "Autonomous retry sequence stopped: %s",
                        retry_decision.reason,
                    )
                    break

            if MAX_CYCLES == 0 or self.cycle < MAX_CYCLES:
                logger.info(f"Sleeping {CYCLE_SLEEP_SEC}s until next cycle...")
                for _ in range(CYCLE_SLEEP_SEC):
                    if self._should_shutdown():
                        break
                    await asyncio.sleep(1)

        logger.info("=== Autonomous SDLC Engine Stopped ===")


async def main():
    engine = AutonomousSDLCEngine()
    await engine.run()


if __name__ == "__main__":
    asyncio.run(main())
