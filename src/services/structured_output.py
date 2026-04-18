from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from types import SimpleNamespace
from typing import Any, Literal, TypeVar

from json_repair import repair_json
from litellm import acompletion
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.observability.logger import get_logger
from src.services.agent_contracts import ReviewVerdict, TaskProposal

try:
    import instructor
except ImportError:  # pragma: no cover - exercised through fallback path
    instructor = None

logger = get_logger("structured_output")

ModelT = TypeVar("ModelT", bound=BaseModel)
CompletionFn = Callable[..., Awaitable[Any]]


class StructuredOutputError(ValueError):
    """Raised when a structured response cannot be validated."""


class DiscoveryTask(BaseModel):
    """Structured discovery task payload for autonomous SDLC scans."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    priority: Literal["HIGH", "MEDIUM", "LOW"]
    description: str = Field(min_length=1)
    file_hint: str = Field(min_length=1)


def _extract_response_content(response: Any) -> str:
    """Normalize a LiteLLM-style response object into text content."""
    message = response.choices[0].message
    content = getattr(message, "content", None)
    if content is not None:
        return content

    tool_calls = getattr(message, "tool_calls", None)
    return str(tool_calls) if tool_calls else ""


def _parse_json_candidate(candidate: str) -> Any | None:
    """Attempt to repair and parse a JSON candidate string."""
    try:
        return json.loads(repair_json(candidate))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _extract_json_payload(text: str) -> Any | None:
    """Extract a JSON payload from raw text or fenced code blocks."""
    candidates = [text.strip()]
    candidates.extend(
        match.group(1).strip()
        for match in re.finditer(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    )

    for candidate in candidates:
        if not candidate:
            continue
        parsed = _parse_json_candidate(candidate)
        if parsed is not None:
            return parsed
    return None


def _coerce_payload(payload: Any) -> Any:
    """Convert dicts, models, or JSON text into a validation payload."""
    if isinstance(payload, BaseModel):
        return payload.model_dump()
    if isinstance(payload, (dict, list)):
        return payload
    if isinstance(payload, str):
        parsed = _extract_json_payload(payload)
        if parsed is not None:
            return parsed
    raise StructuredOutputError("Could not extract structured payload")


def _validate_payload(payload: Any, model_type: type[ModelT]) -> ModelT:
    """Validate a payload against a Pydantic model."""
    try:
        return model_type.model_validate(_coerce_payload(payload))
    except (StructuredOutputError, ValidationError) as exc:
        raise StructuredOutputError(str(exc)) from exc


def parse_task_proposal(payload: Any) -> TaskProposal:
    """Validate a task proposal payload."""
    return _validate_payload(payload, TaskProposal)


def parse_review_verdict(payload: Any) -> ReviewVerdict:
    """Validate a review verdict payload."""
    return _validate_payload(payload, ReviewVerdict)


def _extract_discovery_task_blocks(text: str) -> list[dict[str, Any]]:
    """Parse legacy TASK blocks into structured discovery-task payloads."""
    blocks: list[dict[str, Any]] = []
    for block in re.split(r"\nTASK \d+:\n", text):
        if "Title:" not in block:
            continue
        try:
            title_match = re.search(r"Title:\s*(.*)", block)
            priority_match = re.search(r"Priority:\s*(HIGH|MEDIUM|LOW)", block)
            description_match = re.search(r"Description:\s*(.*)", block, re.DOTALL)
            hint_match = re.search(r"File hint:\s*(.*)", block)
            if not (title_match and priority_match and description_match and hint_match):
                continue

            description = description_match.group(1).split("File hint:")[0].strip()
            blocks.append(
                {
                    "title": title_match.group(1).strip(),
                    "priority": priority_match.group(1).strip(),
                    "description": description,
                    "file_hint": hint_match.group(1).strip(),
                }
            )
        except AttributeError:
            continue
    return blocks


def parse_discovery_tasks(payload: Any) -> list[DiscoveryTask]:
    """Validate discovery-task payloads from JSON or legacy TASK blocks."""
    try:
        data = _coerce_payload(payload)
    except StructuredOutputError:
        if isinstance(payload, str):
            data = _extract_discovery_task_blocks(payload)
        else:
            raise

    if isinstance(data, dict):
        items = data.get("tasks", [data])
    elif isinstance(data, list):
        items = data
    else:
        raise StructuredOutputError("Discovery payload must be an object or list")

    try:
        return [DiscoveryTask.model_validate(item) for item in items]
    except ValidationError as exc:
        raise StructuredOutputError(str(exc)) from exc


def format_review_verdict(verdict: ReviewVerdict) -> str:
    """Render a structured review verdict into the legacy text summary shape."""
    lines = [f"Status: {verdict.status}", f"Summary: {verdict.summary}"]
    if verdict.concerns:
        lines.append("Concerns:")
        lines.extend(f"- {concern}" for concern in verdict.concerns)
    if verdict.retry_reason:
        lines.append(f"Retry reason: {verdict.retry_reason}")
    if verdict.recommended_actions:
        lines.append("Recommended actions:")
        lines.extend(f"- {action}" for action in verdict.recommended_actions)
    return "\n".join(lines)


def _select_instructor_mode(model: str):
    """Choose the safest Instructor mode for the current LiteLLM model."""
    if instructor is None:  # pragma: no cover - depends on optional dependency
        raise StructuredOutputError("Instructor is not installed")
    if model.startswith("openrouter/"):
        return instructor.Mode.OPENROUTER_STRUCTURED_OUTPUTS
    return instructor.Mode.MD_JSON


def build_instructor_client(
    completion: CompletionFn = acompletion,
    *,
    model: str,
):
    """Build an Instructor client around LiteLLM's async completion API."""
    if instructor is None:  # pragma: no cover - depends on optional dependency
        raise StructuredOutputError("Instructor is not installed")
    return instructor.from_litellm(completion, mode=_select_instructor_mode(model))


async def request_structured_output(
    *,
    messages: list[dict[str, str]],
    response_model: type[ModelT],
    model: str,
    api_key: str | None,
    api_base: str | None,
    timeout: int,
    max_retries: int,
    completion: CompletionFn = acompletion,
) -> ModelT:
    """Request a structured output through Instructor, with JSON fallback."""
    try:
        client = build_instructor_client(completion, model=model)
        parsed, _ = await client.chat.completions.create_with_completion(
            model=model,
            response_model=response_model,
            messages=messages,
            api_key=api_key,
            api_base=api_base,
            timeout=timeout,
            max_retries=max_retries,
        )
        return parsed
    except Exception as exc:  # pragma: no cover - fallback path is tested instead
        logger.warning(
            "Structured output bridge fell back to local validation: %s",
            exc,
        )

    response = await completion(
        model=model,
        api_key=api_key,
        api_base=api_base,
        messages=messages,
        timeout=timeout,
    )
    return _validate_payload(_extract_response_content(response), response_model)


def mock_litellm_response(content: str) -> Any:
    """Create a lightweight LiteLLM-style response object for tests."""
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=content,
                    tool_calls=None,
                )
            )
        ]
    )


__all__ = [
    "DiscoveryTask",
    "StructuredOutputError",
    "build_instructor_client",
    "format_review_verdict",
    "mock_litellm_response",
    "parse_discovery_tasks",
    "parse_review_verdict",
    "parse_task_proposal",
    "request_structured_output",
]
