"""Daily embedding-token quota tracker persisted via StateManager.

Keeps a rolling per-UTC-day counter of embedding tokens spent and refuses
requests that would push the day's total over ``Config.EMBED_DAILY_TOKEN_CAP``.
Counters are stored under the ``embed_quota`` key in ``state.json`` so the
cap survives restarts; entries older than ``_RETAIN_DAYS`` are pruned on
every read to keep the state file small.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from src.config import Config
from src.observability.logger import get_logger
from src.state import StateManager

logger = get_logger("embed_quota")

_STATE_KEY = "embed_quota"
_RETAIN_DAYS = 7


class EmbedQuotaExceeded(RuntimeError):
    """Raised when the day's embedding token budget is exhausted."""


class EmbedQuota:
    """Token-bucket keyed by UTC date."""

    def __init__(self, sm: StateManager, *, daily_cap: int | None = None) -> None:
        self._sm = sm
        self._cap = int(daily_cap if daily_cap is not None else Config.EMBED_DAILY_TOKEN_CAP)

    # -- internals --------------------------------------------------------

    def _today_key(self) -> str:
        return datetime.now(UTC).date().isoformat()

    def _bucket(self) -> dict[str, int]:
        raw = self._sm.data.get(_STATE_KEY, {})
        if not isinstance(raw, dict):
            raw = {}
        return {k: int(v) for k, v in raw.items()}

    def _save(self, bucket: dict[str, int]) -> None:
        # Prune stale entries in the same pass so the state file doesn't grow
        # unboundedly.
        cutoff = date.today() - timedelta(days=_RETAIN_DAYS)
        pruned: dict[str, int] = {}
        for k, v in bucket.items():
            try:
                if date.fromisoformat(k) >= cutoff:
                    pruned[k] = v
            except ValueError:
                # Malformed key — drop silently rather than crash.
                continue
        self._sm.data[_STATE_KEY] = pruned
        # Atomic write via the existing StateManager helper (added in
        # PR #7). Falls back to a plain write on older StateManager builds.
        if hasattr(self._sm, "_atomic_write_json"):
            self._sm._atomic_write_json(self._sm.filename, self._sm.data)
        elif self._sm.storage_type == "json":
            import json

            with open(self._sm.filename, "w") as f:
                json.dump(self._sm.data, f, indent=2)

    # -- public API -------------------------------------------------------

    def used_today(self) -> int:
        return self._bucket().get(self._today_key(), 0)

    def remaining_today(self) -> int:
        return max(0, self._cap - self.used_today())

    def check(self, requested_tokens: int) -> None:
        """Raise :class:`EmbedQuotaExceeded` if ``requested_tokens`` would
        push today's total over the cap."""
        if requested_tokens <= 0:
            return
        if self.used_today() + requested_tokens > self._cap:
            raise EmbedQuotaExceeded(
                f"daily embed cap {self._cap} would be exceeded "
                f"(used={self.used_today()}, requested={requested_tokens})"
            )

    def record(self, tokens: int) -> int:
        """Record ``tokens`` against today's budget and return the new total."""
        if tokens <= 0:
            return self.used_today()
        bucket = self._bucket()
        key = self._today_key()
        bucket[key] = bucket.get(key, 0) + int(tokens)
        self._save(bucket)
        return bucket[key]


def estimate_tokens(texts) -> int:  # noqa: ANN001 — accept any iterable
    """Rough pre-call estimate: 1 token per 4 characters.

    Good enough for quota gating; actual consumption comes from the
    embedding response and supersedes this estimate.
    """
    total = 0
    for text in texts or ():
        total += max(1, len(str(text)) // 4)
    return total


__all__ = ["EmbedQuota", "EmbedQuotaExceeded", "estimate_tokens"]
