"""Gap-driven self-prompting research / development loop.

.. deprecated::
    This module is superseded by :class:`src.orchestration.reflection_node.ReflectionNode`.
    All gap-collection functions (``collect_coverage_signals``,
    ``collect_event_log_signals``, ``collect_backlog_signals``, ``run_once``,
    ``synthesize``, ``dispatch``) now emit ``DeprecationWarning`` on every call.
    Migrate callers to ``ReflectionNode`` which provides MCP-native reflection
    with rule-based fallback — no gap-collection boilerplate needed.

Scans a set of cheap signals (coverage gaps, unresolved event-log items,
open GitHub issues, stalled backlog entries) and synthesizes them into
structured prompts written to the existing ``prompt_queue.jsonl``. The
swarm's normal prompt-consumer then picks those up.

Design guarantees:
- **Bounded**: token-bucket rate limiter (default 6/hour) persisted in
  ``state.json`` under ``self_prompt.budget`` so restarts don't reset it.
- **Deduplicated**: SHA-256 of ``(phase, intent_normalized)`` kept in a
  sliding window of the last N entries.
- **Generation-tagged**: every prompt is stamped with a ``generation``
  counter. The synthesizer refuses to synthesize a child prompt from a
  parent whose generation is already >= ``MAX_GENERATION``.
- **Off switch**: ``.swarm_shutdown`` (existing) or ``.swarm_self_prompt_off``
  (new, soft) stop the loop between iterations.
"""

from __future__ import annotations

import hashlib
import json
import os
import warnings
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from src.config import Config
from src.observability.logger import get_logger
from src.services.sdlc_phase import Phase
from src.state import StateManager

logger = get_logger("self_prompt")

#: Hard ceiling on prompts generated from self-prompts themselves.
MAX_GENERATION = 2

#: Name of the soft off-switch sentinel — complements ``.swarm_shutdown``.
SELF_PROMPT_OFF_SENTINEL = ".swarm_self_prompt_off"


class SelfPrompt(BaseModel):
    """Structured payload written into ``prompt_queue.jsonl``."""

    model_config = ConfigDict(extra="forbid")

    phase: Phase
    intent: str = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)
    priority: int = Field(ge=1, le=5, default=3)
    generation: int = Field(ge=0, default=0)

    def hash_key(self) -> str:
        normalized = (self.phase.value + "|" + self.intent.strip().lower()).encode()
        return hashlib.sha256(normalized).hexdigest()


@dataclass
class GapSignal:
    """One raw gap observation."""

    source: str
    intent: str
    phase: Phase
    evidence: list[str] = field(default_factory=list)
    priority: int = 3


# ---------------------------------------------------------------------------
# Signal collectors — cheap, deterministic, no LLM calls.
# ---------------------------------------------------------------------------


def collect_coverage_signals(coverage_xml: Path) -> list[GapSignal]:
    """Flag modules below a per-file coverage threshold."""
    warnings.warn(
        "collect_coverage_signals is deprecated. Use ReflectionNode instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    if not coverage_xml.exists():
        return []
    try:
        import xml.etree.ElementTree as ET

        root = ET.parse(coverage_xml).getroot()  # nosec B314 — coverage.xml is generated locally by our own CI, not untrusted input
    except ET.ParseError as exc:
        logger.warning("coverage.xml parse failed: %s", exc)
        return []

    signals: list[GapSignal] = []
    for cls in root.iter("class"):
        rate = float(cls.attrib.get("line-rate", 1.0))
        filename = cls.attrib.get("filename", "")
        if rate < 0.5 and filename:
            signals.append(
                GapSignal(
                    source="coverage",
                    intent=f"raise coverage in {filename} (currently {rate:.0%})",
                    phase=Phase.IMPLEMENT,
                    evidence=[filename],
                    priority=2 if rate < 0.25 else 3,
                )
            )
    return signals


def collect_event_log_signals(sm: StateManager, *, limit: int = 50) -> list[GapSignal]:
    """Turn recent blocked phase transitions into REVIEW-phase prompts."""
    warnings.warn(
        "collect_event_log_signals is deprecated. Use ReflectionNode instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    events = sm.get_all_events()[-limit:]
    signals: list[GapSignal] = []
    for ev in events:
        if ev.get("action") != "phase.transition.blocked":
            continue
        task_id = ev.get("task_id", "unknown")
        reason = ev.get("reason", "blocked")
        signals.append(
            GapSignal(
                source="events",
                intent=f"resolve blocked transition for {task_id}: {reason}",
                phase=Phase.REVIEW,
                evidence=[task_id],
                priority=2,
            )
        )
    return signals


def collect_backlog_signals(queue_path: Path, *, max_age_hours: float = 12.0) -> list[GapSignal]:
    """Surface stale prompts in the queue so the swarm notices its own backlog."""
    warnings.warn(
        "collect_backlog_signals is deprecated. Use ReflectionNode instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    if not queue_path.exists():
        return []
    now = datetime.now(UTC)
    signals: list[GapSignal] = []
    for line in queue_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = entry.get("timestamp")
        if not ts:
            continue
        try:
            age_h = (now - datetime.fromisoformat(ts)).total_seconds() / 3600.0
        except ValueError:
            continue
        if age_h <= max_age_hours:
            continue
        signals.append(
            GapSignal(
                source="backlog",
                intent=f"drain stale prompt queued {age_h:.1f}h ago by {entry.get('user_id', 'unknown')}",
                phase=Phase.PLAN,
                evidence=[entry.get("prompt", "")[:80]],
                priority=3,
            )
        )
    return signals


# ---------------------------------------------------------------------------
# Synthesizer + dispatcher
# ---------------------------------------------------------------------------


class RateLimiter:
    """Simple hour-window token bucket persisted in ``state.json``."""

    def __init__(self, sm: StateManager, *, max_per_hour: int) -> None:
        self._sm = sm
        self._max = max_per_hour
        self._window: deque[datetime] = deque()
        self._load()

    def _load(self) -> None:
        bucket = self._sm.data.get("self_prompt", {}).get("window", [])
        for ts in bucket:
            try:
                self._window.append(datetime.fromisoformat(ts))
            except (TypeError, ValueError):
                continue

    def _save(self) -> None:
        self._sm.data.setdefault("self_prompt", {})["window"] = [
            ts.isoformat() for ts in self._window
        ]
        if self._sm.storage_type == "json":
            with open(self._sm.filename, "w") as f:
                json.dump(self._sm.data, f, indent=2)

    def try_consume(self) -> bool:
        now = datetime.now(UTC)
        while self._window and (now - self._window[0]).total_seconds() > 3600:
            self._window.popleft()
        if len(self._window) >= self._max:
            return False
        self._window.append(now)
        self._save()
        return True


def synthesize(
    signals: Iterable[GapSignal],
    *,
    dedup: set[str] | None = None,
    parent_generation: int = 0,
) -> list[SelfPrompt]:
    """Convert raw gap signals into validated :class:`SelfPrompt` objects."""
    warnings.warn(
        "synthesize is deprecated. Use ReflectionNode instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    if parent_generation >= MAX_GENERATION:
        logger.info("self_prompt: generation cap hit at %d; skipping", parent_generation)
        return []
    seen = set(dedup or ())
    prompts: list[SelfPrompt] = []
    for sig in signals:
        prompt = SelfPrompt(
            phase=sig.phase,
            intent=sig.intent,
            evidence_refs=list(sig.evidence),
            priority=sig.priority,
            generation=parent_generation + 1,
        )
        key = prompt.hash_key()
        if key in seen:
            continue
        seen.add(key)
        prompts.append(prompt)
    return prompts


def dispatch(
    prompts: list[SelfPrompt],
    *,
    queue_path: Path,
    rate_limiter: RateLimiter,
    user_id: str = "self_prompt",
) -> list[SelfPrompt]:
    """Write accepted prompts to ``prompt_queue.jsonl``.

    Returns the subset that were actually written (bounded by the rate
    limiter). Uses append-mode; atomicity is sufficient for single-writer
    usage — multi-writer access is out of scope for Phase 4.
    """
    warnings.warn(
        "dispatch is deprecated. Use ReflectionNode instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    accepted: list[SelfPrompt] = []
    # Append under the shared file lock (src.utils.file_lock) so the
    # background self-prompt thread can't race with the main loop's
    # dequeue read-then-unlink in swarm_ctl.
    from src.utils.file_lock import locked_append

    for prompt in prompts:
        if not rate_limiter.try_consume():
            logger.info(
                "self_prompt: rate cap reached; deferring %d prompts", len(prompts) - len(accepted)
            )
            break
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "user_id": user_id,
            "prompt": f"[{prompt.phase.value}] {prompt.intent}",
            "self_prompt": prompt.model_dump(mode="json"),
        }
        locked_append(str(queue_path), json.dumps(entry))
        accepted.append(prompt)
    return accepted


def off_switch_active() -> bool:
    """True if any off-switch sentinel is present in the working directory."""
    return os.path.exists(".swarm_shutdown") or os.path.exists(SELF_PROMPT_OFF_SENTINEL)


def run_once(
    *,
    sm: StateManager,
    coverage_xml: Path = Path("coverage.xml"),
    queue_path: Path = Path("prompt_queue.jsonl"),
) -> list[SelfPrompt]:
    """Single pass — collect → synthesize → dispatch.

    Respects ``Config.SELF_PROMPT_ENABLED`` (default False) and the off-switch.
    Safe to invoke from both CLI dry-runs and the main loop.
    """
    warnings.warn(
        "run_once is deprecated. Use ReflectionNode instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    if not getattr(Config, "SELF_PROMPT_ENABLED", False):
        logger.info("self_prompt: disabled via Config.SELF_PROMPT_ENABLED")
        return []
    if off_switch_active():
        logger.info("self_prompt: off-switch sentinel present; skipping pass")
        return []

    signals: list[GapSignal] = []
    signals.extend(collect_coverage_signals(coverage_xml))
    signals.extend(collect_event_log_signals(sm))
    signals.extend(collect_backlog_signals(queue_path))

    # Load existing dedup window from state.
    dedup_window: set[str] = set(sm.data.get("self_prompt", {}).get("dedup", []))

    prompts = synthesize(signals, dedup=dedup_window)

    limiter = RateLimiter(
        sm,
        max_per_hour=getattr(Config, "SELF_PROMPT_MAX_PER_HOUR", 6),
    )
    written = dispatch(prompts, queue_path=queue_path, rate_limiter=limiter)

    # Update dedup window (keep last 200 hashes).
    dedup_list = list(dedup_window) + [p.hash_key() for p in written]
    sm.data.setdefault("self_prompt", {})["dedup"] = dedup_list[-200:]
    if sm.storage_type == "json":
        with open(sm.filename, "w") as f:
            json.dump(sm.data, f, indent=2)

    logger.info(
        "self_prompt: signals=%d synthesized=%d written=%d",
        len(signals),
        len(prompts),
        len(written),
    )
    return written


__all__ = [
    "MAX_GENERATION",
    "SELF_PROMPT_OFF_SENTINEL",
    "GapSignal",
    "RateLimiter",
    "SelfPrompt",
    "collect_backlog_signals",
    "collect_coverage_signals",
    "collect_event_log_signals",
    "dispatch",
    "off_switch_active",
    "run_once",
    "synthesize",
]
