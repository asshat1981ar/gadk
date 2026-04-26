"""Architect agent — owner of the ARCHITECT SDLC phase.

Responsibilities:
- Turn an Ideator proposal (PLAN artifact) into a concrete architecture note
  (ADR-style) and a bounded task plan that Builder can implement.
- Enforce the ARCHITECT quality gate (content-guard + shape check) before
  a work item is allowed to advance into IMPLEMENT.

Design choices:
- Pure tool functions live at module scope so tests can import this module
  without google-adk present; the ``architect_agent`` ADK wrapper is gated
  on a successful ADK import.
- Delegates to existing ``src.services.structured_output`` for JSON shape
  coercion and ``src.planner.TOOL_PROMPT_SUFFIX`` so the architect speaks
  the same tool-call dialect as the rest of the swarm.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.observability.logger import get_logger
from src.services.sdlc_phase import Phase

logger = get_logger("architect")


class ArchitectureNote(BaseModel):
    """ADR-lite payload produced by the Architect at the ARCHITECT phase."""

    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1)
    context: str = Field(min_length=1)
    decision: str = Field(min_length=1)
    consequences: list[str] = Field(default_factory=list)
    alternatives_considered: list[str] = Field(default_factory=list)
    touched_paths: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def as_markdown(self) -> str:
        """Render this note as the ADR body stored in GitHub / docs."""
        lines = [
            f"# {self.title}",
            "",
            f"_Task: `{self.task_id}` · Created: {self.created_at.isoformat()}_",
            "",
            "## Context",
            self.context,
            "",
            "## Decision",
            self.decision,
            "",
        ]
        if self.alternatives_considered:
            lines.append("## Alternatives considered")
            lines.extend(f"- {alt}" for alt in self.alternatives_considered)
            lines.append("")
        if self.consequences:
            lines.append("## Consequences")
            lines.extend(f"- {c}" for c in self.consequences)
            lines.append("")
        if self.touched_paths:
            lines.append("## Touched paths")
            lines.extend(f"- `{p}`" for p in self.touched_paths)
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Pure tool functions — callable from the ADK agent OR directly by
# PhaseController / tests.
# ---------------------------------------------------------------------------


def draft_architecture_note(
    task_id: str,
    title: str,
    context: str,
    decision: str,
    *,
    consequences: list[str] | None = None,
    alternatives: list[str] | None = None,
    touched_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Validate architect input and return a serializable ADR payload.

    Raises ``pydantic.ValidationError`` on invalid input so the caller can
    surface the error through the quality-gate evidence channel.
    """
    note = ArchitectureNote(
        task_id=task_id,
        title=title,
        context=context,
        decision=decision,
        consequences=list(consequences or []),
        alternatives_considered=list(alternatives or []),
        touched_paths=list(touched_paths or []),
    )
    logger.info(
        "architecture.note task=%s touched=%d consequences=%d",
        note.task_id,
        len(note.touched_paths),
        len(note.consequences),
    )
    return note.model_dump(mode="json")


def architecture_gate_payload(note: dict[str, Any]) -> dict[str, Any]:
    """Shape an ADR payload for the ARCHITECT-phase content gate.

    Returns ``{"body": <markdown>}`` so ``ContentGuardGate`` (which
    inspects ``payload["body"]``) can decide whether the note is
    substantial enough to let the work item advance.
    """
    validated = ArchitectureNote.model_validate(note)
    return {"body": validated.as_markdown(), "phase": Phase.ARCHITECT.value}


# ---------------------------------------------------------------------------
# Optional ADK wiring — only activates when google-adk is present so the
# module stays importable in pure-Python test environments.
# ---------------------------------------------------------------------------

architect_agent: Any = None

try:  # pragma: no cover — ADK wiring is exercised by integration tests
    from google.adk.agents import Agent

    from src.config import Config
    from src.tools.dispatcher import batch_execute
    from src.tools.filesystem import list_directory, read_file
    from src.tools.github_tool import list_repo_contents, read_repo_file

    if Config.TEST_MODE:
        from src.testing.mock_llm import MockLiteLlm as LiteLlm
    else:
        from google.adk.models.lite_llm import LiteLlm

    _model = LiteLlm(
        model=Config.LLM_TOOL_MODEL,
        api_key=Config.LLM_API_KEY,
        api_base=Config.LLM_API_BASE,
    )

    architect_agent = Agent(
        name="Architect",
        model=_model,
        description="Owns ARCHITECT phase: produces ADR-style notes before IMPLEMENT.",
        instruction="""You are the Architect of the Cognitive Foundry.

Given an Ideator proposal, your job is to produce one architecture note per
task using `draft_architecture_note`:
- Keep context and decision crisp (a few sentences each).
- List every path you expect Builder to touch.
- Call out at least one alternative you considered and why you rejected it.
- Consequences must include both the upside and the tradeoffs.

Use `read_repo_file` / `list_repo_contents` / `read_file` / `list_directory`
to ground your note in real files before drafting. Use `batch_execute` to
parallelize multiple reads.
""",
        tools=[
            batch_execute,
            draft_architecture_note,
            architecture_gate_payload,
            read_file,
            list_directory,
            read_repo_file,
            list_repo_contents,
        ],
    )
except ImportError as exc:
    logger.debug("ADK unavailable; architect_agent disabled: %s", exc)


__all__ = [
    "ArchitectureNote",
    "architect_agent",
    "architecture_gate_payload",
    "draft_architecture_note",
]
