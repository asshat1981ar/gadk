"""Tests for the LiteLLM-backed embedder with quota enforcement."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from src.config import Config
from src.services.embed_quota import EmbedQuota
from src.services.embedder import LiteLLMEmbedder, build_default_embedder
from src.services.vector_index import VectorBackendUnavailable
from src.state import StateManager


@pytest.fixture
def sm(tmp_path: Path) -> StateManager:
    return StateManager(
        storage_type="json",
        filename=str(tmp_path / "state.json"),
        event_filename=str(tmp_path / "events.jsonl"),
    )


def _install_fake_litellm(
    monkeypatch: pytest.MonkeyPatch,
    *,
    vectors: list[list[float]] | None = None,
    total_tokens: int | None = None,
    raise_on_call: Exception | None = None,
    malformed: bool = False,
) -> list[dict]:
    """Install a fake ``litellm`` module; return a list that captures calls.

    Stubs both ``embedding`` (sync) and ``aembedding`` (async) so the
    same fake works for both ``__call__`` and ``aembed`` tests.
    """
    calls: list[dict] = []

    def _build_payload(model: str, input_: list[str]):
        if raise_on_call is not None:
            raise raise_on_call
        if malformed:
            return {"unexpected": "shape"}
        vecs = vectors if vectors is not None else [[0.1, 0.2, 0.3] for _ in input_]
        payload: dict = {"data": [{"embedding": v} for v in vecs]}
        if total_tokens is not None:
            payload["usage"] = {"total_tokens": total_tokens}
        return payload

    def _embedding(*, model: str, input: list[str]):  # noqa: A002 — match SDK
        calls.append({"mode": "sync", "model": model, "input": list(input)})
        return _build_payload(model, list(input))

    async def _aembedding(*, model: str, input: list[str]):  # noqa: A002
        calls.append({"mode": "async", "model": model, "input": list(input)})
        return _build_payload(model, list(input))

    fake = types.ModuleType("litellm")
    fake.embedding = _embedding  # type: ignore[attr-defined]
    fake.aembedding = _aembedding  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "litellm", fake)
    return calls


def test_embedder_returns_vectors_and_records_tokens(
    sm: StateManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _install_fake_litellm(
        monkeypatch,
        vectors=[[1.0, 0.0], [0.0, 1.0]],
        total_tokens=42,
    )
    quota = EmbedQuota(sm, daily_cap=1000)
    embedder = LiteLLMEmbedder(model="test/model", quota=quota)

    out = embedder(["hello", "world"])

    assert out == [[1.0, 0.0], [0.0, 1.0]]
    assert len(calls) == 1
    assert calls[0]["model"] == "test/model"
    assert calls[0]["input"] == ["hello", "world"]
    # Actual usage from the response supersedes the pre-call estimate.
    assert quota.used_today() == 42


def test_embedder_falls_back_to_estimate_without_usage(
    sm: StateManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_litellm(monkeypatch, vectors=[[0.1, 0.2]])  # no usage block
    quota = EmbedQuota(sm, daily_cap=1000)
    embedder = LiteLLMEmbedder(model="m", quota=quota)
    embedder(["abcd" * 8])  # 32 chars → estimate 8 tokens
    assert quota.used_today() == 8


def test_embedder_empty_batch_short_circuits(
    sm: StateManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _install_fake_litellm(monkeypatch)
    embedder = LiteLLMEmbedder(model="m", quota=EmbedQuota(sm, daily_cap=10))
    assert embedder([]) == []
    assert calls == []


def test_embedder_quota_check_rejects_before_calling_litellm(
    sm: StateManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _install_fake_litellm(monkeypatch)
    quota = EmbedQuota(sm, daily_cap=5)
    quota.record(5)  # fully consumed
    embedder = LiteLLMEmbedder(model="m", quota=quota)
    with pytest.raises(VectorBackendUnavailable, match="embed quota exceeded"):
        embedder(["big text that would cost more than the cap"])
    assert calls == [], "litellm must not be called once quota is blown"


def test_embedder_surfaces_litellm_error_as_unavailable(
    sm: StateManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_litellm(monkeypatch, raise_on_call=RuntimeError("upstream 503"))
    embedder = LiteLLMEmbedder(model="m", quota=EmbedQuota(sm, daily_cap=1000))
    with pytest.raises(VectorBackendUnavailable, match="embedding call failed"):
        embedder(["anything"])


def test_embedder_rejects_malformed_response(
    sm: StateManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_litellm(monkeypatch, malformed=True)
    embedder = LiteLLMEmbedder(model="m", quota=EmbedQuota(sm, daily_cap=1000))
    with pytest.raises(VectorBackendUnavailable, match="malformed embedding response"):
        embedder(["anything"])


def test_embedder_rejects_construction_without_quota_or_sm() -> None:
    """Reviewer feedback on #11: auto-constructing a fresh StateManager
    risks racing with the swarm's writers. Enforce that callers supply
    one of the two."""
    with pytest.raises(ValueError, match="shared EmbedQuota or"):
        LiteLLMEmbedder(model="m")


def test_build_default_embedder_skips_in_test_mode(
    sm: StateManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Config, "TEST_MODE", True)
    monkeypatch.setattr(Config, "OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setattr(Config, "RETRIEVAL_BACKEND", "vector")
    assert build_default_embedder(state_manager=sm) is None


def test_build_default_embedder_skips_without_api_key(
    sm: StateManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Config, "TEST_MODE", False)
    monkeypatch.setattr(Config, "OPENROUTER_API_KEY", None)
    monkeypatch.setattr(Config, "RETRIEVAL_BACKEND", "vector")
    assert build_default_embedder(state_manager=sm) is None


def test_build_default_embedder_skips_for_keyword_backend(
    sm: StateManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Config, "TEST_MODE", False)
    monkeypatch.setattr(Config, "OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setattr(Config, "RETRIEVAL_BACKEND", "keyword")
    assert build_default_embedder(state_manager=sm) is None


def test_build_default_embedder_builds_when_conditions_met(
    sm: StateManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Config, "TEST_MODE", False)
    monkeypatch.setattr(Config, "OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setattr(Config, "RETRIEVAL_BACKEND", "vector")
    monkeypatch.setattr(Config, "EMBED_MODEL", "openrouter/openai/text-embedding-3-small")
    built = build_default_embedder(state_manager=sm)
    assert isinstance(built, LiteLLMEmbedder)
    assert built.model == "openrouter/openai/text-embedding-3-small"


# ---------------------------------------------------------------------------
# Async embed path — mirrors the sync tests against ``LiteLLMEmbedder.aembed``.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aembed_returns_vectors_and_records_tokens(
    sm: StateManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _install_fake_litellm(
        monkeypatch,
        vectors=[[1.0, 0.0], [0.0, 1.0]],
        total_tokens=42,
    )
    quota = EmbedQuota(sm, daily_cap=1000)
    embedder = LiteLLMEmbedder(model="test/model", quota=quota)

    out = await embedder.aembed(["hello", "world"])

    assert out == [[1.0, 0.0], [0.0, 1.0]]
    assert len(calls) == 1
    assert calls[0]["mode"] == "async"
    assert calls[0]["model"] == "test/model"
    assert calls[0]["input"] == ["hello", "world"]
    assert quota.used_today() == 42


@pytest.mark.asyncio
async def test_aembed_falls_back_to_estimate_without_usage(
    sm: StateManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_litellm(monkeypatch, vectors=[[0.1, 0.2]])
    quota = EmbedQuota(sm, daily_cap=1000)
    embedder = LiteLLMEmbedder(model="m", quota=quota)
    await embedder.aembed(["abcd" * 8])  # 32 chars → estimate 8 tokens
    assert quota.used_today() == 8


@pytest.mark.asyncio
async def test_aembed_empty_batch_short_circuits(
    sm: StateManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _install_fake_litellm(monkeypatch)
    embedder = LiteLLMEmbedder(model="m", quota=EmbedQuota(sm, daily_cap=10))
    assert await embedder.aembed([]) == []
    assert calls == []


@pytest.mark.asyncio
async def test_aembed_quota_check_rejects_before_calling_litellm(
    sm: StateManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _install_fake_litellm(monkeypatch)
    quota = EmbedQuota(sm, daily_cap=5)
    quota.record(5)
    embedder = LiteLLMEmbedder(model="m", quota=quota)
    with pytest.raises(VectorBackendUnavailable, match="embed quota exceeded"):
        await embedder.aembed(["big text that would cost more than the cap"])
    assert calls == [], "litellm.aembedding must not be called once quota is blown"


@pytest.mark.asyncio
async def test_aembed_surfaces_litellm_error_as_unavailable(
    sm: StateManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_litellm(monkeypatch, raise_on_call=RuntimeError("upstream 503"))
    embedder = LiteLLMEmbedder(model="m", quota=EmbedQuota(sm, daily_cap=1000))
    with pytest.raises(VectorBackendUnavailable, match="embedding call failed"):
        await embedder.aembed(["anything"])


@pytest.mark.asyncio
async def test_aembed_rejects_malformed_response(
    sm: StateManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_litellm(monkeypatch, malformed=True)
    embedder = LiteLLMEmbedder(model="m", quota=EmbedQuota(sm, daily_cap=1000))
    with pytest.raises(VectorBackendUnavailable, match="malformed embedding response"):
        await embedder.aembed(["anything"])


@pytest.mark.asyncio
async def test_sync_and_async_produce_identical_output(
    sm: StateManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Shared _parse_and_record ensures the two paths can't drift."""
    vectors = [[0.5, -0.5, 0.25]]
    _install_fake_litellm(monkeypatch, vectors=vectors, total_tokens=11)
    quota = EmbedQuota(sm, daily_cap=1000)
    embedder = LiteLLMEmbedder(model="m", quota=quota)

    sync_out = embedder(["same text"])
    async_out = await embedder.aembed(["same text"])

    assert sync_out == async_out == vectors
    # Both calls recorded against the same quota.
    assert quota.used_today() == 22
