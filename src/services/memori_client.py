"""Memori memory integration for GADK — lightweight REST client.

Uses Memori Cloud for structured memory persistence and recall.

*   **persist** → ``POST /v1/sdk/augmentation`` (direct REST — proved 200/422 OK)
*   **recall**  → SDK ``Memori.recall()`` (proper auth chain, 200 OK)

No heavy ML deps — just ``requests`` + SDK for recall auth.

External docs: https://memorilabs.ai/docs/memori-cloud/
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

_PUBLIC_SDK_KEY = "96a7ea3e-11c2-428c-b9ae-5a168363dc80"
_DEFAULT_BASE = "https://api.memorilabs.ai"


class MemoriCloudClient:
    """Thin wrapper around Memori Cloud.

    Usage
    -----
    >>> client = MemoriCloudClient()
    >>> client.attribution("gadk-builder", "project-chimera")
    >>> client.persist(messages=[{"role": "user", "content": "Use TDD"}])
    >>> facts = client.recall("What style did I prefer?")
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: int = 30,
    ) -> None:
        self.api_key = api_key or os.getenv("MEMORI_API_KEY", "")
        self.base_url = base_url or _DEFAULT_BASE
        self.timeout = timeout
        self._entity_id: str | None = None
        self._process_id: str | None = None
        self._session_id = str(uuid.uuid4())

        self._session = requests.Session()
        adapter = HTTPAdapter(
            max_retries=Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["GET", "POST", "PATCH", "DELETE"],
            )
        )
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)
        logger.info("MemoriCloudClient ready (base=%s)", self.base_url)

    # ── attribution / session ─────────────────────────────────────────

    def attribution(self, entity_id: str, process_id: str | None = None) -> MemoriCloudClient:
        """Set attribution (chainable)."""
        self._entity_id = entity_id
        self._process_id = process_id
        logger.debug("attribution: entity=%s process=%s", entity_id, process_id)
        return self

    def new_session(self) -> MemoriCloudClient:
        """Start a new session (chainable)."""
        self._session_id = str(uuid.uuid4())
        logger.debug("new session: %s", self._session_id)
        return self

    def set_session(self, session_id: str) -> MemoriCloudClient:
        """Override the current session (chainable)."""
        self._session_id = session_id
        logger.debug("session: %s", session_id)
        return self

    @property
    def configured(self) -> bool:
        """True when attribution is set."""
        return self._entity_id is not None

    # ── core API ──────────────────────────────────────────────────────

    def persist(self, messages: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
        """Persist a conversation turn to Memori Cloud.

        *messages* – list of ``{"role": "user|assistant", "content": str}``.
        Returns the JSON response dict or ``{}`` on non-fatal error.
        """
        if not self.configured:
            logger.warning("persist() called without attribution — skipping")
            return {}

        payload = {
            "conversation": {
                "messages": [
                    {"role": m["role"], "content": str(m.get("content", ""))} for m in messages
                ],
                "summary": extra.pop("__summary__", None),
            },
            "meta": {
                "attribution": {
                    "entity": {"id": self._entity_id},
                    "process": {"id": self._process_id or ""} or None,
                },
                "framework": {"provider": None},
                "llm": {
                    "model": {
                        "provider": None,
                        "sdk": {"version": ""},
                        "version": extra.pop("model", "unknown"),
                    }
                },
                "platform": {"provider": None},
                "sdk": {"lang": "python", "version": "0.1.0"},
                "storage": {"cockroachdb": False, "dialect": extra.pop("dialect", "sqlite")},
            },
        }
        # prune nulls
        _prune_none(payload)

        try:
            response = self._session.post(
                f"{self.base_url}/v1/sdk/augmentation",
                headers=self._headers(),
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            logger.debug("persist OK — %d messages", len(messages))
            return data
        except requests.exceptions.HTTPError as exc:
            logger.warning(
                "Memori persist error %s: %s",
                exc.response.status_code if exc.response else "?",
                exc,
            )
            return {}
        except requests.exceptions.RequestException as exc:
            logger.warning("Memori persist network error: %s", exc)
            return {}

    def recall(
        self,
        query: str,
        *,
        limit: int = 5,
        threshold: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Recall relevant memories for *query*."""
        if not self.configured:
            logger.warning("recall() called without attribution — skipping")
            return []

        try:
            # Use Memori SDK for recall — proper auth chain
            from memori import Memori

            _set_env_key = self.api_key and os.environ.get("MEMORI_API_KEY") != self.api_key
            if _set_env_key:
                os.environ["MEMORI_API_KEY"] = self.api_key

            m = Memori()
            m.attribution(self._entity_id, self._process_id)
            m.set_session(self._session_id)

            result = m.recall(query, limit=limit)
            facts: list[dict] = result.get("facts", []) if isinstance(result, dict) else []
            logger.debug("recall OK — %d facts for %r", len(facts), query)
            return facts
        except Exception as exc:
            logger.warning("Memori recall error: %s", exc)
            return []

    def delete_entity_memories(self, entity_id: str | None = None) -> bool:
        """Delete all memories for the given entity."""
        target = entity_id or self._entity_id
        if not target:
            logger.warning("delete called without entity_id")
            return False

        try:
            from memori import Memori

            m = Memori()
            m.attribution(target, self._process_id)
            m.delete_entity_memories(target)
            logger.info("Deleted memories for entity=%s", target)
            return True
        except Exception as exc:
            logger.warning("Memori delete error: %s", exc)
            return False

    # ── internal ──────────────────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "X-Memori-API-Key": _PUBLIC_SDK_KEY}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers


# ── helpers ────────────────────────────────────────────────────────


def _prune_none(obj: dict | list | None) -> None:
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            if v is None:
                del obj[k]
            else:
                _prune_none(v)
    elif isinstance(obj, list):
        for item in obj:
            _prune_none(item)
