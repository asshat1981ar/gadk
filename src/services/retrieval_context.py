from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from src.config import Config
from src.observability.logger import get_logger
from src.services.vector_index import (
    SearchHit,
    VectorBackendUnavailable,
    VectorIndex,
    resolve_vector_backend,
)

logger = get_logger("retrieval_context")

APPROVED_CORPORA = ("specs", "plans", "history")
DEFAULT_CORPUS = list(APPROVED_CORPORA)
PLANNING_RETRIEVAL_CAPABILITY = "planning.retrieve_context"


class RetrievalQuery(BaseModel):
    """Validated retrieval request limited to the approved planning corpus."""

    query: str = Field(min_length=1)
    corpus: list[str] = Field(default_factory=lambda: list(DEFAULT_CORPUS))
    top_k: int = Field(default=3, ge=1, le=10)

    @field_validator("corpus")
    @classmethod
    def validate_corpus(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for item in value:
            corpus_name = item.strip().lower()
            if corpus_name not in APPROVED_CORPORA:
                msg = f"Unsupported retrieval corpus: {item}"
                raise ValueError(msg)
            if corpus_name not in normalized:
                normalized.append(corpus_name)
        return normalized


def _repo_root(repo_root: Path | None = None) -> Path:
    return (repo_root or Path.cwd()).resolve()


def _collect_corpus_files(repo_root: Path, corpus: list[str]) -> list[tuple[str, Path]]:
    files: list[tuple[str, Path]] = []
    for corpus_name in corpus:
        if corpus_name == "specs":
            files.extend(
                (corpus_name, path)
                for path in sorted((repo_root / "docs/superpowers/specs").glob("**/*.md"))
                if path.is_file()
            )
        elif corpus_name == "plans":
            files.extend(
                (corpus_name, path)
                for path in sorted((repo_root / "docs/superpowers/plans").glob("**/*.md"))
                if path.is_file()
            )
        elif corpus_name == "history":
            history_path = repo_root / ".swarm_history"
            if history_path.is_file():
                files.append((corpus_name, history_path))
    return files


def _load_documents(repo_root: Path, corpus: list[str]) -> list[Any]:
    try:
        from llama_index.core import Document
    except ImportError as exc:  # pragma: no cover - guarded by environment setup
        msg = "llama-index is required for retrieval context support"
        raise RuntimeError(msg) from exc

    documents: list[Any] = []
    for corpus_name, path in _collect_corpus_files(repo_root, corpus):
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            continue
        documents.append(
            Document(
                text=content,
                metadata={
                    "path": str(path.relative_to(repo_root)),
                    "corpus": corpus_name,
                },
            )
        )
    return documents


def _build_snippet(text: str, query: str, limit: int = 240) -> str:
    collapsed = re.sub(r"\s+", " ", text).strip()
    if len(collapsed) <= limit:
        return collapsed

    for token in [part for part in re.split(r"\W+", query.lower()) if part]:
        location = collapsed.lower().find(token)
        if location >= 0:
            start = max(location - limit // 3, 0)
            end = min(start + limit, len(collapsed))
            snippet = collapsed[start:end]
            return snippet if start == 0 else f"...{snippet}"

    return f"{collapsed[:limit].rstrip()}..."


def _keyword_retrieve(
    request: RetrievalQuery,
    resolved_root: Path,
) -> list[dict[str, Any]]:
    """Existing LlamaIndex keyword path — extracted so the vector branch
    can reuse it as a fallback without duplicating the loader + snippet
    logic."""
    documents = _load_documents(resolved_root, request.corpus)
    if not documents:
        return []

    from llama_index.core import KeywordTableIndex
    from llama_index.core.llms.mock import MockLLM

    index = KeywordTableIndex.from_documents(documents, llm=MockLLM())
    retriever = index.as_retriever()
    retrieved_nodes = retriever.retrieve(request.query)[: request.top_k]

    sources: list[dict[str, Any]] = []
    for retrieved in retrieved_nodes:
        node = getattr(retrieved, "node", retrieved)
        metadata = getattr(node, "metadata", {})
        text = node.get_content()
        sources.append(
            {
                "path": metadata.get("path"),
                "corpus": metadata.get("corpus"),
                "score": getattr(retrieved, "score", None),
                "snippet": _build_snippet(text, request.query),
            }
        )
    return sources


#: Override hook for tests and callers that want to inject a custom
#: embedder (e.g., deterministic fakes). ``None`` means "use the
#: default embedder from :func:`src.services.embedder.build_default_embedder`".
_embedder_override: Any = None


def set_embedder(embedder: Any) -> None:
    """Install a custom :data:`Embedder` for the next vector-retrieve calls.

    Primarily used by tests; production code should rely on the
    Config-driven default from ``build_default_embedder``.
    """
    global _embedder_override
    _embedder_override = embedder


def _resolve_embedder():
    if _embedder_override is not None:
        return _embedder_override
    # Late import to break a potential cycle during module bootstrap.
    from src.services.embedder import build_default_embedder

    return build_default_embedder()


#: Content-hash cache keyed by ``doc_id`` so we only re-embed files whose
#: content has actually changed between calls. Process-local — safe for the
#: swarm's single-writer model; Phase 3d may move it into the backend's
#: meta table so it survives restarts.
_doc_hashes: dict[str, str] = {}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sync_corpus_to_backend(
    backend: VectorIndex,
    resolved_root: Path,
    corpus: list[str],
) -> int:
    """Bring the backend in line with the on-disk corpus.

    - Upserts only docs whose SHA-256 content hash changed.
    - Removes docs that were previously indexed but are no longer on disk.
    - Returns the number of documents currently present after sync.
    """
    seen_ids: set[str] = set()
    for corpus_name, path in _collect_corpus_files(resolved_root, corpus):
        try:
            text = path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError) as exc:
            logger.debug("vector.upsert: skipping %s (%s)", path, exc)
            continue
        if not text:
            continue
        doc_id = str(path.relative_to(resolved_root))
        seen_ids.add(doc_id)
        sha = _sha(text)
        if _doc_hashes.get(doc_id) == sha:
            # Unchanged since last call — skip the (costly) embed.
            continue
        backend.upsert(
            doc_id=doc_id,
            text=text,
            metadata={"corpus": corpus_name, "path": doc_id},
        )
        _doc_hashes[doc_id] = sha

    # Drop backend rows + cache entries whose source file disappeared so
    # stale embeddings don't get served in future queries. Only supported
    # on backends that expose `known_doc_ids` / `delete` (SqliteVecBackend);
    # the NullVectorIndex no-ops both.
    if hasattr(backend, "known_doc_ids") and hasattr(backend, "delete"):
        for stale_id in backend.known_doc_ids() - seen_ids:
            backend.delete(stale_id)
            _doc_hashes.pop(stale_id, None)

    return len(seen_ids)


def _vector_retrieve(
    request: RetrievalQuery,
    resolved_root: Path,
) -> list[dict[str, Any]]:
    """Vector-backed retrieval path.

    When no embedder is available (test mode, missing API key, or no
    override installed) ``resolve_vector_backend`` returns a
    :class:`NullVectorIndex` and the caller falls back to keyword
    retrieval with a ``retrieval.degraded`` log line.
    """
    embedder = _resolve_embedder()
    backend = resolve_vector_backend(embedder=embedder)

    # Ensure backend connections (e.g., SqliteVecBackend) are released
    # even if upsert/query raises. The NullVectorIndex has no close().
    try:
        any_docs = _sync_corpus_to_backend(backend, resolved_root, request.corpus) > 0
        if not any_docs:
            # Match the keyword path: empty corpus returns no sources rather
            # than provoking a backend.query() that would raise on some
            # implementations.
            return []

        hits: list[SearchHit] = backend.query(request.query, top_k=request.top_k)
        return [
            {
                "path": h.metadata.get("path", h.doc_id),
                "corpus": h.metadata.get("corpus"),
                "score": h.score,
                "snippet": _build_snippet(h.text, request.query),
            }
            for h in hits
        ]
    finally:
        if hasattr(backend, "close"):
            backend.close()


def retrieve_context(
    request: RetrievalQuery,
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Retrieve opt-in planning context from the approved corpus only.

    Routes through the configured retrieval backend (``Config.RETRIEVAL_BACKEND``).
    When the vector backend is requested but unavailable, emits a structured
    ``retrieval.degraded`` log line and falls back to keyword retrieval so
    callers always get a best-effort result.
    """

    resolved_root = _repo_root(repo_root)
    backend_name = (Config.RETRIEVAL_BACKEND or "keyword").strip().lower()

    sources: list[dict[str, Any]] = []
    if backend_name in {"vector", "sqlite-vec", "sqlitevec"}:
        try:
            sources = _vector_retrieve(request, resolved_root)
        except VectorBackendUnavailable as exc:
            logger.warning(
                "retrieval.degraded backend=%s reason=%s falling_back=keyword",
                backend_name,
                exc,
            )
            sources = _keyword_retrieve(request, resolved_root)
        except Exception as exc:  # noqa: BLE001
            # Broader safety net: sqlite-vec extension misconfigured,
            # schema migration failures, OpenRouter transport errors, etc.
            # The documented contract is best-effort fallback to keyword;
            # surface the actual exception on the same `retrieval.degraded`
            # channel so it's still visible in logs.
            logger.warning(
                "retrieval.degraded backend=%s unexpected_error=%s:%s falling_back=keyword",
                backend_name,
                type(exc).__name__,
                exc,
            )
            sources = _keyword_retrieve(request, resolved_root)
    else:
        sources = _keyword_retrieve(request, resolved_root)

    return {
        "query": request.query,
        "corpus": request.corpus,
        "sources": sources,
    }


async def retrieve_planning_context(
    query: str,
    corpus: list[str] | None = None,
    top_k: int = 3,
) -> dict[str, Any]:
    """Execute planning retrieval through the shared capability layer."""

    from src.tools.dispatcher import execute_capability

    return await execute_capability(
        PLANNING_RETRIEVAL_CAPABILITY,
        query=query,
        corpus=corpus or list(DEFAULT_CORPUS),
        top_k=top_k,
    )


__all__ = [
    "APPROVED_CORPORA",
    "DEFAULT_CORPUS",
    "PLANNING_RETRIEVAL_CAPABILITY",
    "RetrievalQuery",
    "retrieve_context",
    "retrieve_planning_context",
]
