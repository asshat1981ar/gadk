"""
Content guards for agent-generated artifacts before they reach GitHub.

These guards stop three classes of garbage that the swarm has been producing:

1. **Critic parser leakage** — the Critic's LLM occasionally returns raw
   tool-call JSON (``[{"action": "list_repo_contents", ...}]``) instead of
   narrative review text. That JSON currently ends up verbatim in PR bodies
   and tracking issues.

2. **Low-value / empty artifacts** — Builder sometimes produces an empty
   Kotlin file or a single-line stub and the pipeline still opens a PR of it
   (see project-chimera PR #159 "Turn-Based Combat System" whose own body
   reads ``"the code snippet is empty. Let me first check..."``).

3. **Duplicate issues** — ``create_issue`` has no dedup; seven identical
   "[SWARM TASK] Implement Property-Based Testing" tickets can be filed in
   60 seconds (see project-chimera #127–#133).

Everything here is a pure function with no I/O, so it's trivially unit-
testable and safe to call on every agent output.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable

# ---------------------------------------------------------------------------
# 1. Sanitize agent review text (strip tool-call JSON leakage)
# ---------------------------------------------------------------------------

#: Marker inserted when the review is discarded. Callers can grep for this
#: in logs and metrics to count how often the bug is firing.
LEAKED_REVIEW_PLACEHOLDER = (
    "_(review suppressed: critic returned tool-call JSON instead of prose; "
    "rerun critic with stricter system prompt)_"
)

_STUB_THINKING_FRAGMENTS = (
    "the code snippet is empty",
    "let me first check if there are any files",
    "i'll review the kotlin",  # partial — caught in normalized lowercase
    "review completed and saved to",  # the agent's "I saved the review elsewhere" sidestep
)

_TOOL_CALL_KEYS = ("action", "tool_name", "tool_args", "arguments")


def _strip_code_fence(text: str) -> str:
    """Remove a single leading/trailing ``` fence if the entire text is one fenced block."""
    t = text.strip()
    if t.startswith("```"):
        # drop first line (``` or ```json etc.) and trailing fence if present
        first_nl = t.find("\n")
        if first_nl != -1:
            t = t[first_nl + 1 :]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3].rstrip()
    return t.strip()


def _looks_like_tool_call_json(text: str) -> bool:
    """True iff ``text`` parses as JSON and contains tool-call shaped keys."""
    stripped = _strip_code_fence(text)
    if not stripped or stripped[0] not in "[{":
        return False
    try:
        parsed = json.loads(stripped)
    except (ValueError, TypeError):
        return False

    def _has_tool_call_keys(obj) -> bool:
        if isinstance(obj, dict):
            return any(k in obj for k in _TOOL_CALL_KEYS)
        if isinstance(obj, list):
            return any(_has_tool_call_keys(item) for item in obj)
        return False

    return _has_tool_call_keys(parsed)


def sanitize_review(text: str | None) -> str:
    """Return narrative review text, or a placeholder if the input is leakage.

    Specifically we replace the review when:

    * the whole payload is tool-call-shaped JSON (possibly fenced with ```),
    * the payload is only a thinking-fragment like "the code snippet is empty",
    * the payload is empty / whitespace only.

    We do NOT try to extract "partial prose" from a mixed leak — if the
    critic produced something we can't trust, we'd rather lose the review
    than ship JSON into an issue body.
    """
    if text is None:
        return LEAKED_REVIEW_PLACEHOLDER

    stripped = text.strip()
    if not stripped:
        return LEAKED_REVIEW_PLACEHOLDER

    if _looks_like_tool_call_json(stripped):
        return LEAKED_REVIEW_PLACEHOLDER

    lowered = stripped.lower()
    if any(frag in lowered for frag in _STUB_THINKING_FRAGMENTS):
        return LEAKED_REVIEW_PLACEHOLDER

    return stripped


# ---------------------------------------------------------------------------
# 2. Detect low-value / empty Builder artifacts before they reach a PR
# ---------------------------------------------------------------------------

#: Default minimum bytes of non-trivial content before an artifact is allowed
#: to become a PR. Kotlin stubs like ``class X {}\n`` are ~14 bytes, so 80 is
#: a deliberate floor — any real implementation clears it.
DEFAULT_MIN_BYTES = 80

# Patterns that mean "the generator gave up and emitted a placeholder"
_STUB_BODY_PATTERNS = (
    re.compile(r"^\s*(//|#)\s*todo\s*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*pass\s*$", re.MULTILINE),
)


def _strip_comments_and_blanks(text: str) -> str:
    """Remove // and # line comments plus blank lines, for content-size scoring."""
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("//") or line.startswith("#"):
            continue
        lines.append(line)
    return "\n".join(lines)


def is_low_value_content(text: str | None, *, min_bytes: int = DEFAULT_MIN_BYTES) -> bool:
    """True if ``text`` is too empty / stubby / placeholder-only to ship.

    Used by the SDLC pipelines to bail out before committing code and opening
    a PR. The test strips comments and blanks first so ``"// TODO\\nclass X\\n"``
    is still caught as low-value.
    """
    if text is None:
        return True
    if len(text.strip()) == 0:
        return True

    # Catch the "// TODO" / "pass" sole-content case explicitly even if
    # padded out with comments.
    stripped_body = _strip_comments_and_blanks(text)
    if len(stripped_body) < min_bytes:
        return True

    for pat in _STUB_BODY_PATTERNS:
        # If the body (after comment/blank strip) is just a stub statement, kill it.
        if pat.search(stripped_body) and len(stripped_body) < min_bytes * 2:
            return True

    return False


# ---------------------------------------------------------------------------
# 3. Dedup signature for "have we already filed this issue?"
# ---------------------------------------------------------------------------

_WHITESPACE_RUN = re.compile(r"\s+")


def _normalize_title(title: str) -> str:
    """Lowercase + collapse whitespace so trivial drift doesn't defeat dedup."""
    return _WHITESPACE_RUN.sub(" ", title.strip().lower())


def issue_signature(title: str, body: str | None = None) -> str:
    """Stable SHA-256 of the normalized title (and optional body prefix).

    We dedup primarily on title because the body carries volatile junk like
    timestamps, review snippets, and PR URLs. When title alone feels too
    coarse, pass a short stable prefix of the body (e.g. the task description
    before any generated sections).
    """
    normalized = _normalize_title(title)
    if body:
        normalized += "|" + _normalize_title(body)[:200]
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def is_duplicate_title(new_title: str, existing_titles: Iterable[str]) -> bool:
    """True if ``new_title`` normalizes to the same string as any existing title."""
    target = _normalize_title(new_title)
    return any(_normalize_title(t) == target for t in existing_titles)
