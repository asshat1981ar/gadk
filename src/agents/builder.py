"""Builder agent — owner of the IMPLEMENT SDLC phase.

Responsibilities:
- Accept ArchitectureNote from Architect
- Break down into file-level changes
- Create feature branch
- Apply changes with validation
- Run local tests
- Create PR with description
- Transition to REVIEW phase

Design choices:
- Pure tool functions live at module scope so tests can import this module
  without google-adk present; the ``builder_agent`` ADK wrapper is gated
  on a successful ADK import.
- Uses src.tools.github_tool for branch/PR operations
- Uses src.tools.filesystem for local file operations
- Uses src.tools.sandbox_executor for test execution (when needed)
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.config import Config
from src.observability.logger import get_logger
from src.services.sdlc_phase import Phase

logger = get_logger("builder")

try:
    from src.tools.filesystem import write_file as fs_write_file
    from src.tools.github_tool import GitHubTool

    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False
    GitHubTool = None  # type: ignore
    fs_write_file = None  # type: ignore


# Project root is the directory containing this file's package (src/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class ImplementationPlan(BaseModel):
    """File-level implementation plan derived from ArchitectureNote."""

    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1)
    files: list[dict[str, str]] = Field(default_factory=list)
    # Each item: {"path": "src/x.py", "content": "...code..."}
    test_strategy: str = Field(default="")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class BuildResult(BaseModel):
    """Result of a build operation."""

    model_config = ConfigDict(extra="forbid")

    success: bool = Field(default=False)
    files_written: int = Field(default=0)
    results: list[str] = Field(default_factory=list)
    error: str | None = Field(default=None)


class TestResult(BaseModel):
    """Result of running tests."""

    model_config = ConfigDict(extra="forbid")

    success: bool = Field(default=False)
    stdout: str = Field(default="")
    stderr: str = Field(default="")
    returncode: int = Field(default=1)
    duration_ms: int = Field(default=0)


class PRResult(BaseModel):
    """Result of creating a pull request."""

    model_config = ConfigDict(extra="forbid")

    success: bool = Field(default=False)
    pr_url: str | None = Field(default=None)
    branch_name: str = Field(default="")
    pr_number: int | None = Field(default=None)
    error: str | None = Field(default=None)


class BranchResult(BaseModel):
    """Result of creating a branch."""

    model_config = ConfigDict(extra="forbid")

    success: bool = Field(default=False)
    branch_name: str = Field(default="")
    base: str = Field(default="main")
    error: str | None = Field(default=None)


# ---------------------------------------------------------------------------
# Pure tool functions — callable from the ADK agent OR directly by
# PhaseController / tests.
# ---------------------------------------------------------------------------


def generate_pr_title(architecture_note: dict[str, Any] | object) -> str:
    """Generate a concise PR title from an ArchitectureNote.

    Args:
        architecture_note: The architecture note as a dict or ArchitectureNote object

    Returns:
        PR title string (max 256 chars per GitHub limit)
    """
    # Handle both dict and Pydantic model
    if hasattr(architecture_note, "model_dump"):
        architecture_note = architecture_note.model_dump()

    title = architecture_note.get("title", "Untitled")
    task_id = architecture_note.get("task_id", "")

    # Format: [IMPLEMENT-{task_id}] {title}
    pr_title = f"[IMPLEMENT-{task_id}] {title}"

    # Truncate to 256 chars
    if len(pr_title) > 256:
        pr_title = pr_title[:253] + "..."

    return pr_title


def generate_pr_body(architecture_note: dict[str, Any] | object) -> str:
    """Generate a PR body from an ArchitectureNote.

    Args:
        architecture_note: The architecture note as a dict or ArchitectureNote object

    Returns:
        PR body as markdown string
    """
    # Handle both dict and Pydantic model
    if hasattr(architecture_note, "model_dump"):
        architecture_note = architecture_note.model_dump()

    title = architecture_note.get("title", "Untitled")
    context = architecture_note.get("context", "")
    decision = architecture_note.get("decision", "")
    consequences = architecture_note.get("consequences", [])
    alternatives = architecture_note.get("alternatives_considered", [])
    touched_paths = architecture_note.get("touched_paths", [])
    task_id = architecture_note.get("task_id", "")

    lines = [
        f"# {title}",
        "",
        f"> **Task:** `{task_id}`  ",
        "> **Phase:** IMPLEMENT → REVIEW",
        "",
        "## Description",
        f"{context}",
        "",
        "## Context",
        f"{context}",
        "",
        "## Decision",
        f"{decision}",
        "",
    ]

    if alternatives:
        lines.extend(
            ["## Alternatives Considered", ""] + [f"- {alt}" for alt in alternatives] + [""]
        )

    if consequences:
        lines.extend(["## Consequences", ""] + [f"- {c}" for c in consequences] + [""])

    if touched_paths:
        lines.extend(
            [
                "## Changes",
                "This PR modifies the following files:",
                "",
            ]
            + [f"- `{p}`" for p in touched_paths]
            + [""]
        )

    lines.extend(
        [
            "## Testing",
            "- [ ] Unit tests pass",
            "- [ ] Integration tests pass",
            "- [ ] Manual testing completed",
            "",
            "## Checklist",
            "- [ ] Code follows project style guidelines",
            "- [ ] Self-review completed",
            "- [ ] Documentation updated (if needed)",
        ]
    )

    return "\n".join(lines)


def implementation_gate_payload(plan: dict[str, Any]) -> dict[str, Any]:
    """Shape an ImplementationPlan payload for the IMPLEMENT-phase content gate.

    Returns dict with build results for quality gate inspection.
    """
    plan_obj = ImplementationPlan.model_validate(plan)
    return {
        "phase": Phase.IMPLEMENT.value,
        "task_id": plan_obj.task_id,
        "files_count": len(plan_obj.files),
        "has_test_strategy": bool(plan_obj.test_strategy),
    }


async def create_branch(
    task_id: str,
    base: str = "main",
) -> dict[str, Any]:
    """Create a feature branch for implementation.

    Args:
        task_id: The task identifier
        base: The base branch to branch from (default: main)

    Returns:
        BranchResult as dict
    """
    branch_name = f"feature/{task_id}"

    try:
        if GitHubTool is None:
            return BranchResult(
                success=False,
                branch_name=branch_name,
                base=base,
                error="GitHubTool not available",
            ).model_dump(mode="json")

        # Create branch via GitHub API
        gh = GitHubTool()

        # Get the latest commit SHA from base branch
        try:
            base_branch = gh.repo.get_branch(base)
        except Exception as exc:
            return BranchResult(
                success=False,
                branch_name=branch_name,
                base=base,
                error=f"Failed to get base branch: {exc}",
            ).model_dump(mode="json")

        # Create the new branch
        try:
            gh.repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=base_branch.commit.sha)
        except Exception as exc:
            # Branch might already exist
            logger.warning("Branch creation may have failed or branch exists: %s", exc)

        logger.info(
            "branch.created task=%s branch=%s base=%s",
            task_id,
            branch_name,
            base,
        )

        return BranchResult(
            success=True,
            branch_name=branch_name,
            base=base,
        ).model_dump(mode="json")

    except Exception as exc:
        logger.error("create_branch failed: %s", exc, exc_info=True)
        return BranchResult(
            success=False,
            branch_name=branch_name,
            base=base,
            error=str(exc),
        ).model_dump(mode="json")


async def apply_code_changes(
    changes: dict[str, str],
    branch_name: str | None = None,
) -> dict[str, Any]:
    """Apply multi-file code changes atomically.

    Args:
        changes: Dict mapping file paths to content {path: content}
        branch_name: Optional branch name (for tracking only, writes to working dir)

    Returns:
        BuildResult with file write status
    """
    if not changes:
        return BuildResult(success=False, error="No changes provided").model_dump(mode="json")

    results = []
    files_written = 0

    for path, content in changes.items():
        try:
            # Resolve path relative to project root
            resolved = _PROJECT_ROOT / path

            # Security check: ensure path is within project root
            try:
                resolved.relative_to(_PROJECT_ROOT)
            except ValueError:
                results.append(f"Error: Path {path} outside project root")
                continue

            # Create parent directories
            resolved.parent.mkdir(parents=True, exist_ok=True)

            # Write the file
            resolved.write_text(content, encoding="utf-8")

            results.append(f"Wrote {path}")
            files_written += 1

        except Exception as exc:
            results.append(f"Error writing {path}: {exc}")

    success = files_written > 0 and files_written == len(changes)

    logger.info(
        "code_changes.applied files=%d success=%s branch=%s",
        files_written,
        success,
        branch_name or "unknown",
    )

    return BuildResult(
        success=success,
        files_written=files_written,
        results=results,
    ).model_dump(mode="json")


async def run_tests_locally(
    test_paths: list[str] | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    """Run tests before pushing.

    Args:
        test_paths: List of paths to test (e.g., ["tests/"])
        timeout: Maximum time to wait for tests

    Returns:
        TestResult with execution status
    """
    if test_paths is None:
        test_paths = ["tests/"]

    # Default to system pytest
    cmd = [sys.executable, "-m", "pytest"] + test_paths

    start_time = datetime.now(UTC)

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=_PROJECT_ROOT,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

            duration = datetime.now(UTC) - start_time
            duration_ms = int(duration.total_seconds() * 1000)

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            success = proc.returncode == 0

            logger.info(
                "tests.completed success=%s duration_ms=%d",
                success,
                duration_ms,
            )

            return TestResult(
                success=success,
                stdout=stdout_str,
                stderr=stderr_str,
                returncode=proc.returncode,
                duration_ms=duration_ms,
            ).model_dump(mode="json")

        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass

            duration = datetime.now(UTC) - start_time
            duration_ms = int(duration.total_seconds() * 1000)

            return TestResult(
                success=False,
                stderr="Error: Test execution timed out",
                duration_ms=duration_ms,
            ).model_dump(mode="json")

    except Exception as exc:
        duration = datetime.now(UTC) - start_time
        duration_ms = int(duration.total_seconds() * 1000)

        logger.error("run_tests_locally failed: %s", exc, exc_info=True)
        return TestResult(
            success=False,
            stderr=f"Error: {exc}",
            duration_ms=duration_ms,
        ).model_dump(mode="json")


async def create_builder_pr(
    note: dict[str, Any] | object,
    branch_name: str,
    base: str = "main",
) -> dict[str, Any]:
    """Create PRs with proper templates.

    Args:
        note: ArchitectureNote as dict or Pydantic model
        branch_name: The branch name to create PR from
        base: The base branch (default: main)

    Returns:
        PRResult with created PR info
    """
    # Handle both dict and Pydantic model
    if hasattr(note, "model_dump"):
        note_dict = note.model_dump()
    elif hasattr(note, "dict"):
        note_dict = note.dict()
    else:
        note_dict = dict(note)

    try:
        if GitHubTool is None:
            return PRResult(
                success=False,
                branch_name=branch_name,
                error="GitHubTool not available",
            ).model_dump(mode="json")

        gh = GitHubTool()

        title = generate_pr_title(note_dict)
        body = generate_pr_body(note_dict)

        pr_url = await gh.create_pull_request(
            title=title,
            body=body,
            head=branch_name,
            base=base,
        )

        # Extract PR number from URL
        pr_number = None
        if pr_url and "/pull/" in pr_url:
            try:
                pr_number = int(pr_url.split("/pull/")[-1].rstrip("/"))
            except (ValueError, IndexError):
                pass

        # Check for errors in the response
        if pr_url and pr_url.startswith("Error"):
            return PRResult(
                success=False,
                branch_name=branch_name,
                error=pr_url,
            ).model_dump(mode="json")

        logger.info(
            "pr.created task=%s branch=%s url=%s",
            note_dict.get("task_id", ""),
            branch_name,
            pr_url,
        )

        return PRResult(
            success=pr_url is not None and not pr_url.startswith("Error"),
            pr_url=pr_url,
            branch_name=branch_name,
            pr_number=pr_number,
        ).model_dump(mode="json")

    except Exception as exc:
        logger.error("create_builder_pr failed: %s", exc, exc_info=True)
        return PRResult(
            success=False,
            branch_name=branch_name,
            error=str(exc),
        ).model_dump(mode="json")


# ---------------------------------------------------------------------------
# Workflow functions
# ---------------------------------------------------------------------------


async def implement_from_architecture_note(
    note: dict[str, Any] | object,
    changes: dict[str, str],
    base: str = "main",
) -> dict[str, Any]:
    """Complete implementation workflow from ArchitectureNote.

    Workflow:
    1. Create feature branch
    2. Apply code changes
    3. Run local tests
    4. Create PR with description

    Args:
        note: ArchitectureNote as dict or Pydantic model
        changes: Dict of file changes {path: content}
        base: Base branch

    Returns:
        Complete workflow result
    """
    # Handle both dict and Pydantic model
    if hasattr(note, "model_dump"):
        note_dict = note.model_dump()
    elif hasattr(note, "dict"):
        note_dict = note.dict()
    else:
        note_dict = dict(note)

    task_id = note_dict.get("task_id", "unknown")

    logger.info(
        "implementation.start task=%s files=%d",
        task_id,
        len(changes),
    )

    # Step 1: Create feature branch
    branch_result = await create_branch(task_id, base)
    if not branch_result.get("success"):
        return {
            "phase": Phase.IMPLEMENT.value,
            "success": False,
            "error": f"Failed to create branch: {branch_result.get('error')}",
            "step": "create_branch",
        }

    branch_name = branch_result["branch_name"]

    # Step 2: Apply code changes
    build_result = await apply_code_changes(changes, branch_name)
    if not build_result.get("success"):
        return {
            "phase": Phase.IMPLEMENT.value,
            "success": False,
            "error": f"Failed to apply changes: {build_result.get('error')}",
            "step": "apply_code_changes",
            "branch_result": branch_result,
        }

    # Step 3: Run local tests
    test_result = await run_tests_locally()

    # Step 4: Create PR even if tests fail (allows for review of failing code)
    pr_result = await create_builder_pr(note_dict, branch_name, base)

    success = pr_result.get("success", False)

    logger.info(
        "implementation.complete task=%s success=%s pr_url=%s",
        task_id,
        success,
        pr_result.get("pr_url", "none"),
    )

    return {
        "phase": Phase.IMPLEMENT.value,
        "success": success,
        "next_phase": Phase.REVIEW.value,
        "task_id": task_id,
        "branch_result": branch_result,
        "build_result": build_result,
        "test_result": test_result,
        "pr_result": pr_result,
    }


# ---------------------------------------------------------------------------
# Optional ADK wiring — only activates when google-adk is present so the
# module stays importable in pure-Python test environments.
# ---------------------------------------------------------------------------

try:
    from src.agents.architect import ArchitectureNote
except ImportError:
    ArchitectureNote = None

builder_agent: Any = None

try:  # pragma: no cover — ADK wiring is exercised by integration tests
    from google.adk.agents import Agent

    from src.tools.filesystem import list_directory, read_file, write_file

    if Config.TEST_MODE:
        from src.testing.mock_llm import MockLiteLlm as LiteLlm
    else:
        from google.adk.models.lite_llm import LiteLlm

    _model = LiteLlm(
        model=Config.OPENROUTER_MODEL,
        api_key=Config.OPENROUTER_API_KEY,
        api_base=Config.OPENROUTER_API_BASE,
    )

    builder_agent = Agent(
        name="Builder",
        model=_model,
        description="Owns IMPLEMENT phase: creates branches, applies code, and opens PRs.",
        instruction="""You are the Builder of the Cognitive Foundry.

Your job is to implement code changes based on ArchitectureNotes.

When you receive an ArchitectureNote (as JSON), use the workflow:
1. Call `create_branch` to create a feature branch
2. Call `apply_code_changes` to write the code files
3. Call `run_tests_locally` to validate the changes
4. Call `create_builder_pr` to open a pull request

You can also use individual tools as needed:
- `create_branch(task_id, base)`: Create a feature branch
- `apply_code_changes(changes, branch_name)`: Write code to files
- `run_tests_locally(test_paths)`: Run pytest
- `create_builder_pr(note, branch_name, base)`: Create a PR
- `implement_from_architecture_note(note, changes)`: Complete workflow

Use `read_file` and `list_directory` to explore the codebase.
Use `write_file` to make individual file edits.

All tool results include a `success` field. Check it before proceeding.
""",
        tools=[
            create_branch,
            create_builder_pr,
            apply_code_changes,
            run_tests_locally,
            implement_from_architecture_note,
            read_file,
            write_file,
            list_directory,
        ],
    )
except ImportError as exc:
    logger.debug("ADK unavailable; builder_agent disabled: %s", exc)


__all__ = [
    "ImplementationPlan",
    "BuildResult",
    "TestResult",
    "PRResult",
    "BranchResult",
    "generate_pr_title",
    "generate_pr_body",
    "implementation_gate_payload",
    "create_branch",
    "apply_code_changes",
    "run_tests_locally",
    "create_builder_pr",
    "implement_from_architecture_note",
    "builder_agent",
]
